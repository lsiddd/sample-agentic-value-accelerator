"""Local AWS CLI credential process over a private Unix socket.

The host owns the login cache and refreshes it using its AWS CLI. Containers
receive expiring credentials on demand, without storing keys in Compose env.
Only the `get` command writes credentials to stdout (AWS SDK protocol).
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import time


def cli_environment():
    env = dict(os.environ)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                 "AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_CONFIG_FILE",
                 "AWS_SHARED_CREDENTIALS_FILE", "AWS_CONTAINER_CREDENTIALS_FULL_URI"):
        env.pop(name, None)
    return env


class CredentialSource:
    def __init__(self, aws, profile, account):
        self.aws, self.profile, self.account = aws, profile, account
        self.cached = None
        self.cached_at = 0

    def command(self, *args, env=None):
        result = subprocess.run([self.aws, *args, "--no-cli-pager"],
                                env=env or cli_environment(), capture_output=True,
                                text=True, timeout=30, check=True)
        return json.loads(result.stdout)

    def get(self):
        now = time.monotonic()
        if self.cached and now - self.cached_at < 30:
            expiry = datetime.fromisoformat(self.cached["Expiration"].replace("Z", "+00:00"))
            if (expiry - datetime.now(timezone.utc)).total_seconds() > 60:
                return self.cached
        data = self.command("configure", "export-credentials", "--profile", self.profile,
                            "--format", "process")
        if not all(data.get(k) for k in ("AccessKeyId", "SecretAccessKey", "SessionToken", "Expiration")):
            raise ValueError("Expected expiring AWS login credentials")
        # Check the identity of the exact credentials being handed to containers.
        env = cli_environment()
        env.update(AWS_ACCESS_KEY_ID=data["AccessKeyId"], AWS_SECRET_ACCESS_KEY=data["SecretAccessKey"],
                   AWS_SESSION_TOKEN=data["SessionToken"], AWS_DEFAULT_REGION="us-east-1")
        identity = self.command("sts", "get-caller-identity", "--output", "json", env=env)
        if identity["Account"] != self.account:
            raise ValueError("Unexpected AWS account")
        self.cached = {k: data[k] for k in ("AccessKeyId", "SecretAccessKey", "SessionToken", "Expiration")}
        self.cached["Version"] = 1
        self.cached_at = now
        return self.cached


class Server(socketserver.UnixStreamServer):
    def __init__(self, path, source):
        self.source = source
        super().__init__(path, Handler)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            payload = self.server.source.get()
        except Exception:
            # Never expose CLI stderr, tokens, or raw exceptions to logs/clients.
            print("AWS credential refresh failed; check the host AWS login/account.", file=sys.stderr, flush=True)
            payload = {"error": "AWS login unavailable; run aws login --profile default on the host"}
        self.request.sendall(json.dumps(payload).encode())


def fetch(path):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(70)
        client.connect(str(path))
        chunks = []
        while chunk := client.recv(8192):
            chunks.append(chunk)
        data = json.loads(b"".join(chunks))
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("serve", "get"))
    parser.add_argument("socket_path", type=Path)
    parser.add_argument("--aws", default="aws")
    parser.add_argument("--profile", default="default")
    parser.add_argument("--account", default="821672147714")
    args = parser.parse_args()
    if args.action == "get":
        try:
            print(json.dumps(fetch(args.socket_path)))
        except Exception:
            print("AWS credential process unavailable; check ava-aws-credentials.service and AWS login.", file=sys.stderr)
            raise SystemExit(1)
    else:
        os.umask(0o077)
        args.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        args.socket_path.unlink(missing_ok=True)
        with Server(str(args.socket_path), CredentialSource(args.aws, args.profile, args.account)) as server:
            server.serve_forever()


if __name__ == "__main__":
    main()
