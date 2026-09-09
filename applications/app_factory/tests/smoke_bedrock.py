"""Small billable integration test: GLM delegates, writes code/docs and reviews.

Run from repo root: python -m applications.app_factory.tests.smoke_bedrock
Uses a new /tmp workspace; no shell tool, deployment or existing-file mutation.
"""
import ast
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile

from applications.app_factory.bedrock_runtime import AgentDefinition, ResultMessage, query
from applications.app_factory.builder import build_agent_options


async def main():
    root = Path(tempfile.mkdtemp(prefix="ava-app-factory-smoke-"))
    original = build_agent_options("smoke")
    options = replace(
        original, cwd=str(root), writable_paths=(str(root),), max_tokens=1024,
        max_turns=8, max_calls=20, max_total_tokens=25000, timeout_seconds=180,
        allowed_tools=["Read", "Agent"], required_agents=("agent-builder", "docs-builder", "validator"),
        system_prompt="Coordinate a small code-generation task. Invoke agent-builder to write normalize.py first, then docs-builder to write README.md, then validator to read both files. Use those exact filenames in delegation prompts. Use the Agent tool for every stage. Finish after all three succeed.",
        agents={
            "agent-builder": AgentDefinition(
                "Generate Python code", "Use Write to create normalize.py with normalize_names(values). It returns a sorted list of unique lowercased, stripped strings, excluding blanks. Use no imports, annotations, extra functions or top-level code. Only sorted/set builtins and lower/strip methods may be called. Then finish.",
                ["Read", "Write", "Edit"], original.model, max_turns=4, required_files=("normalize.py",)),
            "docs-builder": AgentDefinition(
                "Document the function", "Read normalize.py, then Write README.md with one short example and a description. Do not change Python files.",
                ["Read", "Write"], original.agents["docs-builder"].model, max_turns=4, required_files=("README.md",)),
            "validator": AgentDefinition(
                "Review generated code", "Read normalize.py and README.md. Check the requested behavior. Report PASS or FAIL and a short explanation. Do not change files.",
                ["Read"], original.model, max_turns=4),
        },
    )
    async for message in query(prompt="Create exactly normalize.py and README.md. In normalize.py write only def normalize_names(values): returning sorted({v.strip().lower() for v in values if v.strip()}). No type checks, imports, other functions or top-level code. The docs-builder must create README.md, not modify Python docstrings. The validator must read both files.", options=options):
        if isinstance(message, ResultMessage):
            if message.is_error:
                raise RuntimeError(message.errors)
            print(json.dumps({"workspace": str(root), "usage": message.usage}))
    source = (root / "normalize.py").read_text()
    tree = ast.parse(source)
    assert len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef)
    function = tree.body[0]
    assert function.name == "normalize_names" and not function.decorator_list
    # Limit executable syntax before evaluating the model-generated test function.
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
               ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.comprehension,
               ast.Call, ast.Name, ast.Attribute, ast.Load, ast.Store, ast.Constant,
               ast.Assign, ast.List, ast.Set, ast.If, ast.For, ast.Expr, ast.Compare,
               ast.NotEq, ast.Eq, ast.UnaryOp, ast.Not)
    for node in ast.walk(tree):
        assert isinstance(node, allowed), type(node).__name__
        if isinstance(node, ast.Call):
            assert ((isinstance(node.func, ast.Name) and node.func.id in ("sorted", "set")) or
                    (isinstance(node.func, ast.Attribute) and node.func.attr in ("strip", "lower")))
        if isinstance(node, ast.Attribute):
            assert node.attr in ("strip", "lower")
    namespace = {"__builtins__": {"sorted": sorted, "set": set}}
    exec(compile(tree, str(root / "normalize.py"), "exec"), namespace)
    assert namespace["normalize_names"]([" ANA ", "bob", "ana", "", "  "]) == ["ana", "bob"]
    assert namespace["normalize_names"]([]) == []
    assert (root / "README.md").stat().st_size > 20
    print("PASS: GLM generated tested Python code, Flash documented it, GLM reviewed it.")


if __name__ == "__main__":
    asyncio.run(main())
