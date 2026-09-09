"""Regression tests for the local refreshable AWS credential process."""
from datetime import datetime, timedelta, timezone
import threading

import boto3
import pytest

from demo.credentials.provider import CredentialSource, Server, fetch


def credentials(key="test-key"):
    return dict(Version=1, AccessKeyId=key, SecretAccessKey="test-secret", SessionToken="test-token",
                Expiration=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())


def test_export_is_cached_then_renews_and_rechecks_account(monkeypatch):
    source = CredentialSource("aws", "default", "123")
    calls = []
    def command(*args, env=None):
        calls.append(args)
        if args[0] == "sts":
            assert env["AWS_ACCESS_KEY_ID"].startswith("test-key")
            return {"Account": "123"}
        return credentials(f"test-key-{len(calls)}")
    monkeypatch.setattr(source, "command", command)
    first = source.get()
    assert source.get() == first
    assert len(calls) == 2
    source.cached_at -= 31
    assert source.get()["AccessKeyId"] != first["AccessKeyId"]
    assert len(calls) == 4


def test_wrong_account_is_not_served(monkeypatch):
    source = CredentialSource("aws", "default", "expected")
    monkeypatch.setattr(source, "command", lambda *args, **kwargs:
                        {"Account": "wrong"} if args[0] == "sts" else credentials())
    with pytest.raises(ValueError, match="Unexpected AWS account"):
        source.get()
    assert source.cached is None


def test_same_sdk_session_refreshes_through_unix_socket(tmp_path, monkeypatch):
    path = tmp_path / "provider.sock"
    class Source:
        calls = 0
        def get(self):
            self.calls += 1
            return credentials(f"test-key-{self.calls}")
    source = Source()
    with Server(str(path), source) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            from pathlib import Path
            import sys
            provider = Path(__file__).parent / "credentials/provider.py"
            config = tmp_path / "config"
            config.write_text(f'[profile test]\ncredential_process = "{sys.executable}" "{provider}" get "{path}"\n')
            for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
                monkeypatch.delenv(key, raising=False)
            monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
            monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "missing"))
            session = boto3.Session(profile_name="test")
            creds = session.get_credentials()
            assert creds.method == "custom-process"
            first = creds.get_frozen_credentials().access_key
            creds._expiry_time = datetime.now(timezone.utc) - timedelta(seconds=1)
            second = creds.get_frozen_credentials().access_key
            assert first != second
            assert session.get_credentials() is creds
        finally:
            server.shutdown()
            thread.join()


def test_refresh_errors_do_not_expose_cli_output(tmp_path, capsys):
    class BrokenSource:
        def get(self):
            raise RuntimeError("secret-from-cli")
    with Server(str(tmp_path / "provider.sock"), BrokenSource()) as server:
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        with pytest.raises(RuntimeError, match="AWS login unavailable"):
            fetch(tmp_path / "provider.sock")
        thread.join()
    assert "secret-from-cli" not in capsys.readouterr().err
