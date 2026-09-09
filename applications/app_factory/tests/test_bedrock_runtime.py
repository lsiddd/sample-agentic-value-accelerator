import asyncio
from pathlib import Path

import pytest

from applications.app_factory.bedrock_runtime import (
    AgentDefinition, AgentOptions, BedrockExecutor, BuildError, HookMatcher,
    ResultMessage, query,
)
from applications.app_factory.hooks import enforce_builder_rules


def response(text="done", calls=(), stop=None):
    return {"stopReason": stop or ("tool_use" if calls else "end_turn"),
            "output": {"message": {"role": "assistant", "content":
                       ([{"text": text}] if text else []) + [{"toolUse": c} for c in calls]}},
            "usage": {"inputTokens": 10, "outputTokens": 5}}


def call(name, args, id="t1"):
    return {"toolUseId": id, "name": name, "input": args}


class Client:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    def converse(self, **kwargs):
        self.requests.append(kwargs)
        return next(self.responses)


def options(tmp_path, **kwargs):
    return AgentOptions(system_prompt="Build", cwd=str(tmp_path), model="zai.glm-4.7",
                        allowed_tools=["Read", "Write", "Edit"], **kwargs)


def collect(opts, client):
    async def run():
        return [message async for message in query(prompt="Build", options=opts, client=client)]
    return asyncio.run(run())


def test_converse_executes_file_tool_and_returns_matching_result(tmp_path):
    client = Client(response(calls=[call("Write", {"file_path": "out.py", "content": "x = 1\n"})]), response())
    messages = collect(options(tmp_path), client)
    assert (tmp_path / "out.py").read_text() == "x = 1\n"
    assert isinstance(messages[-1], ResultMessage) and not messages[-1].is_error
    assert messages[-1].usage["inputTokens"] == 20
    result = client.requests[-1]["messages"][-2]["content"][0]["toolResult"]
    assert result["toolUseId"] == "t1" and result["status"] == "success"
    assert client.requests[0]["modelId"] == "zai.glm-4.7"


@pytest.mark.parametrize("path", ["../outside.py", ".git/config", ".env"])
def test_file_paths_are_confined(tmp_path, path):
    runtime = BedrockExecutor(options(tmp_path), Client())
    with pytest.raises(BuildError):
        runtime.path(path, write=True)


def test_symlink_cannot_escape_write_root(tmp_path):
    (tmp_path / "escape").symlink_to(tmp_path.parent, target_is_directory=True)
    runtime = BedrockExecutor(options(tmp_path), Client())
    with pytest.raises(BuildError):
        runtime.path("escape/elsewhere.py", write=True)


def test_write_allowlist(tmp_path):
    runtime = BedrockExecutor(options(tmp_path, writable_paths=(str(tmp_path / "generated"),)), Client())
    with pytest.raises(BuildError):
        runtime.path("reference.py", write=True)


def test_existing_write_rule_blocks_invalid_document(tmp_path):
    opts = options(tmp_path, hooks={"PreToolUse": [HookMatcher("Write|Edit", [enforce_builder_rules])]})
    client = Client(response(calls=[call("Write", {"file_path": "samples/documents/tax.json", "content": "{}"})]), response())
    collect(opts, client)
    assert not (tmp_path / "samples/documents/tax.json").exists()
    assert client.requests[-1]["messages"][-2]["content"][0]["toolResult"]["status"] == "error"


def test_edit_hook_checks_complete_result_and_preserves_original(tmp_path):
    path = tmp_path / "out.py"
    path.write_text("safe = 1\n")
    seen = []
    async def deny(event, *_):
        seen.append(event)
        return {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "invalid"}}
    opts = options(tmp_path, hooks={"PreToolUse": [HookMatcher("Write", [deny])]})
    client = Client(response(calls=[call("Edit", {"file_path": "out.py", "old_string": "1", "new_string": "2"})]), response())
    collect(opts, client)
    assert path.read_text() == "safe = 1\n"
    assert seen[0]["tool_input"]["content"] == "safe = 2\n"


def test_subagent_uses_its_model_and_runs_post_hook(tmp_path):
    seen = []
    async def hook(event, *_):
        seen.append(event["tool_input"]["subagent_type"])
        return {}
    opts = options(tmp_path, agents={"data-builder": AgentDefinition("Data", "Write data", ["Write"], "zai.glm-4.7-flash")},
                   hooks={"PostToolUse": [HookMatcher("Agent", [hook])]}, required_agents=("data-builder",))
    opts.allowed_tools = ["Agent"]
    client = Client(response(calls=[call("Agent", {"subagent_type": "data-builder", "prompt": "Generate"})]),
                    response(calls=[call("Write", {"file_path": "profile.json", "content": "{}"}, "sub1")]),
                    response("data done"), response("all done"))
    messages = collect(opts, client)
    assert not messages[-1].is_error
    assert [r["modelId"] for r in client.requests] == [opts.model, "zai.glm-4.7-flash", "zai.glm-4.7-flash", opts.model]
    assert seen == ["data-builder"]
    assert any(getattr(m, "parent_tool_use_id", None) == "t1" for m in messages)


def test_required_agents_cannot_be_skipped(tmp_path):
    opts = options(tmp_path, required_agents=("validator",), max_turns=2)
    messages = collect(opts, Client(response(), response()))
    assert messages[-1].is_error


@pytest.mark.parametrize("stop", ["max_tokens", "guardrail_intervened", "content_filtered"])
def test_incomplete_or_blocked_output_does_not_execute_tools(tmp_path, stop):
    client = Client(response(calls=[call("Write", {"file_path": "out.py", "content": "bad"})], stop=stop))
    messages = collect(options(tmp_path), client)
    assert messages[-1].is_error and not (tmp_path / "out.py").exists()


def test_shared_call_budget_stops_infinite_tools(tmp_path):
    client = Client(response(calls=[call("Read", {"file_path": "missing"})]))
    messages = collect(options(tmp_path, max_calls=1), client)
    assert messages[-1].is_error and len(client.requests) == 1


def test_bash_nonzero_exit_is_tool_error(tmp_path):
    runtime = BedrockExecutor(options(tmp_path), Client())
    result = asyncio.run(runtime.tool(call("Bash", {"command": "exit 7"}), ["Bash"]))
    assert result["toolResult"]["status"] == "error"
    assert "7" in result["toolResult"]["content"][0]["text"]


def test_bash_timeout_terminates_process(tmp_path):
    runtime = BedrockExecutor(options(tmp_path, shell_timeout_seconds=1), Client())
    result = asyncio.run(runtime.tool(call("Bash", {"command": "sleep 10"}), ["Bash"]))
    assert result["toolResult"]["status"] == "error"


@pytest.mark.parametrize('limit,should_fail', [(0, False), (10, True)])
def test_token_cap_can_be_disabled_explicitly(tmp_path, limit, should_fail):
    client = Client(response(calls=[call('Write', {'file_path': 'out.py', 'content': 'x=1'})]), response())
    messages = collect(options(tmp_path, max_total_tokens=limit), client)
    assert messages[-1].is_error == should_fail
    assert len(client.requests) == (1 if should_fail else 2)


def test_disabling_token_cap_keeps_call_cap(tmp_path):
    client = Client(response(calls=[call('Read', {'file_path': 'missing'})]))
    messages = collect(options(tmp_path, max_total_tokens=0, max_calls=1), client)
    assert messages[-1].is_error
    assert len(client.requests) == 1


def test_all_run_limits_can_be_disabled(tmp_path):
    client = Client(response(calls=[call('Write', {'file_path': 'out.py', 'content': 'x=1'})]), response())
    messages = collect(options(tmp_path, max_turns=0, max_calls=0, max_total_tokens=0,
                               timeout_seconds=0, shell_timeout_seconds=0), client)
    assert not messages[-1].is_error
    assert len(client.requests) == 2


def test_shell_workdir_selects_project_and_does_not_persist(tmp_path):
    (tmp_path / 'ui').mkdir()
    (tmp_path / 'ui' / 'marker').write_text('UI project')
    runtime = BedrockExecutor(options(tmp_path), Client())
    assert asyncio.run(runtime.shell('cat marker', 'ui')) == 'UI project'
    assert asyncio.run(runtime.shell('pwd')).strip() == str(tmp_path)
    with pytest.raises(BuildError):
        asyncio.run(runtime.shell('pwd', '..'))


@pytest.mark.parametrize("content,expected", [(None, "error"), ("{broken", "error"), ('{"ticket_id":"TKT001"}', "success")])
def test_data_specialist_completion_requires_valid_domain_samples(tmp_path, content, expected):
    sample = tmp_path / "samples/TKT001/ticket.json"
    sample.parent.mkdir(parents=True)
    if content is not None:
        sample.write_text(content)
    opts = options(tmp_path, agents={"data-builder": AgentDefinition(
        "Data", "Generate", [], "zai.glm-4.7-flash", required_json_dirs=("samples",))})
    executor = BedrockExecutor(opts, Client(response("Generated")))
    result = asyncio.run(executor.tool(call("Agent", {"subagent_type": "data-builder", "prompt": "Generate"}), ["Agent"]))
    assert result["toolResult"]["status"] == expected
    assert ("data-builder" in executor.completed) == (expected == "success")
