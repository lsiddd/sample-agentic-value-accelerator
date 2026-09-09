"""Bedrock Converse executor for the factory's coding agents and existing hooks.

No Claude CLI, Anthropic API, or vendor-specific message transport is required.
Shell tools run in the build workspace, like any build script; use an isolated
build worker for generation. File tools restrict paths to the configured roots.
"""
from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import signal
import time
from typing import Callable

import boto3
from botocore.config import Config


@dataclass
class AgentDefinition:
    description: str
    prompt: str
    tools: list[str]
    model: str
    max_turns: int = 30
    required_files: tuple[str, ...] = ()


@dataclass
class HookMatcher:
    matcher: str
    hooks: list[Callable]


@dataclass
class AgentOptions:
    system_prompt: str
    cwd: str
    model: str
    allowed_tools: list[str]
    agents: dict[str, AgentDefinition] = field(default_factory=dict)
    hooks: dict[str, list[HookMatcher]] = field(default_factory=dict)
    required_agents: tuple[str, ...] = ()
    writable_paths: tuple[str, ...] = ()
    max_turns: int = 60
    max_tokens: int = 8192
    max_calls: int = 160
    max_total_tokens: int = 500_000  # Zero explicitly disables the aggregate token cap.
    timeout_seconds: int = 1200
    shell_timeout_seconds: int = 120
    region: str = "us-east-1"


@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    name: str
    input: dict
    id: str


@dataclass
class AssistantMessage:
    content: list[TextBlock | ToolUseBlock]
    parent_tool_use_id: str | None = None


@dataclass
class ResultMessage:
    is_error: bool = False
    errors: list[str] = field(default_factory=list)
    total_cost_usd: float | None = None
    usage: dict = field(default_factory=dict)


class BuildError(RuntimeError):
    pass


def spec(name, description, properties, required):
    return {"toolSpec": {"name": name, "description": description,
                        "inputSchema": {"json": {"type": "object", "properties": properties,
                                                   "required": required, "additionalProperties": False}}}}


STRING = {"type": "string"}
TOOL_SPECS = {
    "Read": spec("Read", "Read a UTF-8 file in the workspace. offset is a 1-based line number.",
                 {"file_path": STRING, "offset": {"type": "integer", "minimum": 1},
                  "limit": {"type": "integer", "minimum": 1, "maximum": 800}}, ["file_path"]),
    "Write": spec("Write", "Create or overwrite a UTF-8 file. Parent directories are created automatically.",
                  {"file_path": STRING, "content": STRING}, ["file_path", "content"]),
    "Edit": spec("Edit", "Replace one exact, unique string in an existing file.",
                 {"file_path": STRING, "old_string": STRING, "new_string": STRING},
                 ["file_path", "old_string", "new_string"]),
    "Glob": spec("Glob", "List matching workspace files. Use ** for recursive matching.",
                 {"pattern": STRING, "path": STRING}, ["pattern"]),
    "Grep": spec("Grep", "Search workspace text files with a Python regular expression.",
                 {"pattern": STRING, "path": STRING, "glob": STRING}, ["pattern"]),
    "Bash": spec("Bash", "Run a command. Each call starts fresh: cd does NOT persist. Set workdir to the project directory for npm/build commands. Do not deploy resources.",
                 {"command": STRING, "workdir": STRING}, ["command"]),
}


class BedrockExecutor:
    def __init__(self, options: AgentOptions, client=None):
        self.options = options
        if options.max_tokens <= 0:
            raise ValueError("Per-response token limit must be positive")
        for value in (options.max_turns, options.max_calls, options.max_total_tokens,
                      options.timeout_seconds, options.shell_timeout_seconds):
            if value < 0:
                raise ValueError("Limits must be nonnegative; zero disables a limit")
        self.root = Path(options.cwd).resolve()
        self.writable = tuple(Path(p).resolve() for p in options.writable_paths) or (self.root,)
        self.client = client or boto3.client("bedrock-runtime", region_name=options.region,
                                            config=Config(connect_timeout=10, read_timeout=120,
                                                          retries={"total_max_attempts": 2}))
        self.events: asyncio.Queue = asyncio.Queue()
        self.calls = 0
        self.usage = {"inputTokens": 0, "outputTokens": 0}
        self.model_usage: dict[str, dict] = {}
        self.completed: set[str] = set()
        self.revision = 0
        self.validated_revision = -1
        self.deadline = time.monotonic() + options.timeout_seconds if options.timeout_seconds else None

    def path(self, value: str, write=False) -> Path:
        p = Path(value)
        p = (self.root / p).resolve() if not p.is_absolute() else p.resolve()
        if not p.is_relative_to(self.root) or any(part in (".git", ".aws", ".ssh", ".codex", ".env") for part in p.relative_to(self.root).parts):
            raise BuildError("Path is outside the build workspace or is a private configuration path")
        if write and not any(p == allowed or p.is_relative_to(allowed) for allowed in self.writable):
            raise BuildError("Writes must stay in the generated application's output paths")
        return p

    async def hooks(self, event, tool, args, tool_id):
        for matcher in self.options.hooks.get(event, []):
            if re.fullmatch(matcher.matcher, tool):
                for hook in matcher.hooks:
                    output = await hook({"hook_event_name": event, "tool_name": tool,
                                         "tool_input": args}, tool_id, {})
                    decision = (output or {}).get("hookSpecificOutput", {})
                    if decision.get("permissionDecision") == "deny":
                        raise BuildError(decision.get("permissionDecisionReason", "Tool denied by build rule"))

    async def shell(self, command, workdir=None):
        cwd = self.path(workdir) if workdir else self.root
        if not cwd.is_dir():
            raise BuildError(f"Working directory does not exist: {cwd}")
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", command, cwd=cwd, start_new_session=True,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            output, _ = await asyncio.wait_for(proc.communicate(), self.options.shell_timeout_seconds or None)
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await proc.wait()
            raise
        if proc.returncode:
            raise BuildError(f"Command exited {proc.returncode} in {cwd}. Each Bash call starts fresh; set workdir explicitly. Diagnose the error before retrying: {output.decode(errors='replace')[-16000:]}")
        return output.decode(errors="replace")[-16000:] or "Command completed"

    async def tool(self, call, allowed):
        name, args, tool_id = call["name"], call["input"], call["toolUseId"]
        try:
            if name not in allowed:
                raise BuildError(f"Tool {name} is not allowed for this agent")
            if name in ("Write", "Edit"):
                path = self.path(args["file_path"], write=True)
                args = {**args, "file_path": str(path)}
            # Edit hooks inspect the complete prospective file, not only a fragment.
            if name == "Edit":
                current = path.read_text()
                old = args["old_string"]
                if not old or current.count(old) != 1:
                    raise BuildError("old_string must occur exactly once; read the file before editing")
                content = current.replace(old, args["new_string"], 1)
                await self.hooks("PreToolUse", "Write", {"file_path": str(path), "content": content}, tool_id)
            await self.hooks("PreToolUse", name, args, tool_id)
            if name == "Read":
                lines = self.path(args["file_path"]).read_text().splitlines()
                offset = max(1, args.get("offset", 1)) - 1
                count = min(800, max(1, args.get("limit", 400)))
                result = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines[offset:offset+count], offset))[:32000]
            elif name in ("Write", "Edit"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(args["content"] if name == "Write" else content)
                self.revision += 1
                result = f"Wrote {path.relative_to(self.root)}"
            elif name in ("Glob", "Grep"):
                base = self.path(args.get("path", "."))
                pattern = args.get("glob", "**/*") if name == "Grep" else args["pattern"]
                if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                    raise BuildError("Use a relative glob inside path")
                files = [base] if base.is_file() else base.glob(pattern)
                matches = []
                regex = re.compile(args["pattern"]) if name == "Grep" else None
                for candidate in files:
                    if len(matches) >= 200:
                        break
                    if not candidate.is_file() or any(x in candidate.parts for x in ("node_modules", ".git", ".venv", "__pycache__")):
                        continue
                    try:
                        p = self.path(str(candidate))
                        if regex:
                            if p.stat().st_size > 1_000_000:
                                continue
                            for n, line in enumerate(p.read_text().splitlines(), 1):
                                if regex.search(line):
                                    matches.append(f"{p.relative_to(self.root)}:{n}:{line[:500]}")
                                    if len(matches) >= 200:
                                        break
                        else:
                            matches.append(str(p.relative_to(self.root)))
                    except (UnicodeError, OSError, BuildError):
                        continue
                result = "\n".join(matches)[:32000] or "No matches"
            elif name == "Bash":
                result = await self.shell(args["command"], args.get("workdir"))
                self.revision += 1
            elif name == "Agent":
                agent_name = args["subagent_type"]
                definition = self.options.agents[agent_name]
                specialist_prompt = definition.prompt
                if definition.required_files:
                    specialist_prompt += "\nCompletion requires these exact files: " + ", ".join(definition.required_files)
                result = await self.loop(args["prompt"], specialist_prompt, definition.model,
                                         definition.tools, definition.max_turns, tool_id)
                missing_files = [p for p in definition.required_files if not self.path(p).is_file()]
                if missing_files:
                    raise BuildError("Specialist did not produce required files: " + ", ".join(missing_files))
                await self.hooks("PostToolUse", name, args, tool_id)
                if agent_name == "validator" and re.search(r"(?im)^\s*(?:[-*#]\s*|\*\*)*(?:FAIL|FAILED)\b", result):
                    raise BuildError(result)
                self.completed.add(agent_name)
                if agent_name == "validator":
                    self.validated_revision = self.revision
                return {"toolResult": {"toolUseId": tool_id, "content": [{"text": result[:32000]}], "status": "success"}}
            else:
                raise BuildError(f"Unknown tool: {name}")
            await self.hooks("PostToolUse", name, args, tool_id)
            return {"toolResult": {"toolUseId": tool_id, "content": [{"text": result}], "status": "success"}}
        except (BuildError, KeyError, ValueError, OSError, asyncio.TimeoutError) as exc:
            if name == "Agent":
                self.completed.discard(args.get("subagent_type", ""))
            reason = str(exc) or type(exc).__name__
            return {"toolResult": {"toolUseId": tool_id, "content": [{"text": reason[:16000]}], "status": "error"}}

    async def loop(self, prompt, system, model, allowed, turns, parent=None):
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        specs = [TOOL_SPECS[name] for name in allowed if name != "Agent"]
        if "Agent" in allowed:
            specs.append(spec("Agent", "Delegate a task to a specialist. Available specialists: " +
                              "; ".join(f"{n}: {a.description}" for n, a in self.options.agents.items()),
                              {"subagent_type": {"type": "string", "enum": list(self.options.agents)},
                               "prompt": STRING, "description": STRING}, ["subagent_type", "prompt"]))
        system += "\nUse only the provided tools. Write files with Write/Edit so build rules are checked. Report failures honestly. Do not deploy AWS resources."
        system += "\nAfter your required files and relevant checks pass, return a concise final summary immediately. Do not repeat successful checks, re-read unchanged files, or run shell commands just to print summaries."
        for _ in (range(turns) if turns else itertools.count()):
            if (self.options.max_calls and self.calls >= self.options.max_calls) or (
                self.options.max_total_tokens > 0
                and sum(self.usage.values()) >= self.options.max_total_tokens
            ):
                raise BuildError("Shared model-call/token budget exhausted")
            remaining = self.deadline - time.monotonic() if self.deadline is not None else None
            if remaining is not None and remaining <= 0:
                raise BuildError("Builder deadline exceeded")
            self.calls += 1
            request = dict(modelId=model, system=[{"text": system}], messages=messages,
                           inferenceConfig={"maxTokens": self.options.max_tokens, "temperature": 0})
            if specs:
                request["toolConfig"] = {"tools": specs}
            response = await asyncio.wait_for(asyncio.to_thread(self.client.converse, **request), remaining)
            usage = response.get("usage", {})
            per_model = self.model_usage.setdefault(model, {"inputTokens": 0, "outputTokens": 0})
            for key in self.usage:
                self.usage[key] += usage.get(key, 0)
                per_model[key] += usage.get(key, 0)
            if response["stopReason"] not in ("end_turn", "tool_use", "stop_sequence"):
                raise BuildError(f"Model stopped with {response['stopReason']}; incomplete output was not executed")
            message = response["output"]["message"]
            messages.append(message)
            blocks = [TextBlock(b["text"]) if "text" in b else
                      ToolUseBlock(b["toolUse"]["name"], b["toolUse"]["input"], b["toolUse"]["toolUseId"])
                      for b in message["content"] if "text" in b or "toolUse" in b]
            await self.events.put(AssistantMessage(blocks, parent))
            calls = [b["toolUse"] for b in message["content"] if "toolUse" in b]
            if not calls:
                if parent is None:
                    missing = set(self.options.required_agents) - self.completed
                    if "validator" in self.options.required_agents and self.validated_revision != self.revision:
                        missing.add("validator")
                    if missing:
                        messages.append({"role": "user", "content": [{"text": "Build incomplete. Invoke these specialists successfully before finishing: " + ", ".join(sorted(missing))} ]})
                        continue
                return "\n".join(b.text for b in blocks if isinstance(b, TextBlock))
            # Agent tool calls have independent conversations. File mutations stay ordered.
            if all(c["name"] == "Agent" and c["input"].get("subagent_type") != "validator" for c in calls):
                tasks = [asyncio.create_task(self.tool(c, allowed)) for c in calls]
                try:
                    results = await asyncio.gather(*tasks)
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
            else:
                results = [await self.tool(c, allowed) for c in calls]
            messages.append({"role": "user", "content": results})
        raise BuildError("Agent turn budget exhausted before completion")

    async def run(self, prompt):
        try:
            async with asyncio.timeout(self.options.timeout_seconds or None):
                await self.loop(prompt, self.options.system_prompt, self.options.model,
                                self.options.allowed_tools, self.options.max_turns)
            result = ResultMessage(usage={**self.usage, "calls": self.calls, "models": self.model_usage})
        except Exception as exc:
            result = ResultMessage(is_error=True, errors=[str(exc) or type(exc).__name__],
                                   usage={**self.usage, "calls": self.calls, "models": self.model_usage})
        await self.events.put(result)


async def query(*, prompt, options, client=None):
    executor = BedrockExecutor(options, client)
    task = asyncio.create_task(executor.run(prompt))
    try:
        while True:
            message = await executor.events.get()
            yield message
            if isinstance(message, ResultMessage):
                break
        await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
