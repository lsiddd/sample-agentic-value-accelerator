"""Start AVA with automatically refreshed AWS login credentials (Linux/systemd)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from credentials.provider import cli_environment, fetch

root = Path(__file__).resolve().parents[1]
aws = shutil.which("aws")
if not aws or not shutil.which("systemctl"):
    raise SystemExit("This demo launcher requires AWS CLI and a systemd user session")
identity = json.loads(subprocess.check_output([
    aws, "sts", "get-caller-identity", "--profile", "default", "--output", "json", "--no-cli-pager"
], text=True, env=cli_environment()))
if identity["Account"] != "821672147714":
    raise SystemExit("Unexpected AWS account; local startup stopped")

socket_dir = Path.home() / ".local/state/ava-demo/credentials"
socket_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
socket_dir.chmod(0o700)
unit_dir = Path.home() / ".config/systemd/user"
unit_dir.mkdir(parents=True, exist_ok=True)
# Paths are literal systemd arguments; escape systemd's percent specifiers.
command = " ".join(json.dumps(str(p).replace("%", "%%")) for p in (
    sys.executable, root / "demo/credentials/provider.py", "serve", socket_dir / "provider.sock",
    "--aws", aws,
))
unit = f"""[Unit]
Description=AVA local AWS login credential provider

[Service]
Type=simple
ExecStart={command}
Restart=on-failure
RestartSec=2
UMask=0077

[Install]
WantedBy=default.target
"""
(unit_dir / "ava-aws-credentials.service").write_text(unit)
subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
subprocess.run(["systemctl", "--user", "enable", "ava-aws-credentials.service"], check=True)
subprocess.run(["systemctl", "--user", "restart", "ava-aws-credentials.service"], check=True)
for attempt in range(30):
    try:
        fetch(socket_dir / "provider.sock")
        break
    except (FileNotFoundError, ConnectionRefusedError):
        time.sleep(0.1)
else:
    raise SystemExit("AWS credential provider did not start")

env = {**cli_environment(), "AWS_REGION": "us-east-1", "AWS_PROFILE": "ava-demo",
       "AVA_CREDENTIAL_SOCKET_DIR": str(socket_dir)}
if (root / "demo/pipeline/terraform.tfstate").exists():
    env["STATE_MACHINE_ARN"] = subprocess.check_output([
        "terraform", f"-chdir={root / 'demo/pipeline'}", "output", "-raw", "state_machine_arn"
    ], text=True).strip()
print("Starting AVA with automatically refreshed AWS credentials, us-east-1", flush=True)
subprocess.run(["docker", "compose", "--project-name", "ava-demo", "-f", "docker-compose.yaml",
                "-f", str(root / "demo/compose.credentials.yaml"), "up", "--build", "-d"],
               cwd=root / "platform/control_plane", env=env, check=True)
