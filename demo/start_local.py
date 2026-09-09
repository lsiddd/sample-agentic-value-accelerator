"""Start local AVA using resolved default-profile credentials, kept in memory."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
identity = json.loads(subprocess.check_output([
    "aws", "sts", "get-caller-identity", "--profile", "default", "--output", "json", "--no-cli-pager"
], text=True))
if identity["Account"] != "821672147714":
    raise SystemExit("Unexpected AWS account; local startup stopped")
credentials = json.loads(subprocess.check_output([
    "aws", "configure", "export-credentials", "--profile", "default", "--format", "process"
], text=True))
env = {**os.environ, "AWS_REGION": "us-east-1", "AWS_PROFILE": "default"}
for source, target in (("AccessKeyId", "AWS_ACCESS_KEY_ID"), ("SecretAccessKey", "AWS_SECRET_ACCESS_KEY"),
                       ("SessionToken", "AWS_SESSION_TOKEN")):
    env[target] = credentials.get(source, "")
print("Starting AVA locally with account ending 7714, us-east-1", flush=True)
subprocess.run(["docker", "compose", "--project-name", "ava-demo", "up", "--build", "-d"],
               cwd=root / "platform/control_plane", env=env, check=True)
