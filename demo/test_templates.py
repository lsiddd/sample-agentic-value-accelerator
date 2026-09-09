"""Offline regressions for startup failures discovered during the demo."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_template(name, code):
    env = {**os.environ, "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
           "AWS_SESSION_TOKEN": "testing", "AWS_EC2_METADATA_DISABLED": "true",
           "AWS_REGION": "us-east-1"}
    result = subprocess.run([sys.executable, "-c", code],
                            cwd=ROOT / "platform/control_plane/templates" / name,
                            env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_streaming_handler_rejects_empty_prompt_without_inference():
    run_template("conversational-assistant", '''
import asyncio
from src.strands.main import handler
async def check():
    assert [event async for event in handler({})] == [{"error": "prompt is required"}]
asyncio.run(check())
''')


def test_supervisor_registers_distinct_specialist_tools():
    run_template("supervisor-specialists", '''
from src.strands.main import supervisor
assert set(supervisor.tool_registry.registry) == {"researcher", "writer", "analyst"}
''')
