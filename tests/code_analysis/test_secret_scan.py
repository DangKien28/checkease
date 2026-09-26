"""Unit tests cho secret scan (mock subprocess — không cần cài gitleaks)."""

import json
import os
from types import SimpleNamespace

from apps.code_analysis import secret_scan


def _fake_run_factory(monkeypatch, items=None, returncode=0, stderr="",
                      fail_first_unknown=False):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        is_detect = "detect" in cmd
        if fail_first_unknown and is_detect:
            return SimpleNamespace(
                returncode=1, stdout="",
                stderr='Error: unknown command "detect" for "gitleaks"',
            )
        if returncode == 0 and "--report-path" in cmd:
            path = cmd[cmd.index("--report-path") + 1]
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(items or [], fh)
        return SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)

    monkeypatch.setattr(secret_scan.subprocess, "run", fake_run)
    return calls


def test_run_gitleaks_parses_and_redacts_secret(monkeypatch):
    items = [
        {"RuleID": "aws-access-token", "File": "app/config.py", "StartLine": 3,
         "Secret": "AKIAIOSFODNN7REALKEY"},
        {"RuleID": "generic-api-key", "File": "tests/fixtures/keys.py",
         "StartLine": 1, "Secret": "AKIAZZZZZZZZZZZZZZZZ"},
        {"RuleID": "generic-api-key", "File": "app/keys.py", "StartLine": 5,
         "Secret": "YOUR_API_KEY"},
    ]
    _fake_run_factory(monkeypatch, items)
    res = secret_scan.run_gitleaks("src")

    assert res.triggered is True
    assert res.state_reason == ""
    assert len(res.findings) == 1
    finding = res.findings[0]
    assert finding.file == "app/config.py" and finding.line == 3
    assert finding.secret_length == len("AKIAIOSFODNN7REALKEY")
    # thư mục test/fixtures + placeholder bị loại
    assert res.suppressed == 2
    # Không lưu raw secret ở bất kỳ đâu trong kết quả
    assert "REALKEY" not in json.dumps([f.__dict__ for f in res.findings])


def test_run_gitleaks_respects_allowlist(monkeypatch):
    items = [{"RuleID": "r", "File": "legacy/db.py", "StartLine": 1,
              "Secret": "AKIAIOSFODNN7REALKEY"}]
    _fake_run_factory(monkeypatch, items)
    res = secret_scan.run_gitleaks("src", allowlist=["legacy/"])
    assert res.triggered is False
    assert res.suppressed == 1


def test_run_gitleaks_clean(monkeypatch):
    _fake_run_factory(monkeypatch, [])
    res = secret_scan.run_gitleaks("src")
    assert res.triggered is False and res.state_reason == ""


def test_run_gitleaks_tool_error_is_not_silent(monkeypatch):
    """Lỗi công cụ phải có state_reason — không được im lặng coi như sạch."""
    _fake_run_factory(monkeypatch, returncode=1, stderr="invalid flag --nope")
    res = secret_scan.run_gitleaks("src")
    assert res.triggered is False
    assert "exit=1" in res.state_reason


def test_run_gitleaks_falls_back_to_dir_command(monkeypatch):
    items = [{"RuleID": "aws-access-token", "File": "app/x.py", "StartLine": 1,
              "Secret": "AKIAIOSFODNN7REALKEY"}]
    calls = _fake_run_factory(monkeypatch, items, fail_first_unknown=True)
    res = secret_scan.run_gitleaks("src")
    assert res.triggered is True
    assert len(calls) == 2
    assert "detect" in calls[0] and "dir" in calls[1]


def test_run_gitleaks_does_not_pass_unsupported_exclude_flag(monkeypatch):
    """Regression: gitleaks không có cờ --exclude (từng làm scan chết âm thầm)."""
    calls = _fake_run_factory(monkeypatch, [])
    secret_scan.run_gitleaks("src")
    assert "--exclude" not in " ".join(calls[0])


def test_run_gitleaks_timeout(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise secret_scan.subprocess.TimeoutExpired(cmd, 180)

    monkeypatch.setattr(secret_scan.subprocess, "run", fake_run)
    res = secret_scan.run_gitleaks("src")
    assert res.triggered is False
    assert "timed out" in res.state_reason


def test_run_gitleaks_cleans_up_temp_report(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        path = cmd[cmd.index("--report-path") + 1]
        seen["path"] = path
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([], fh)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(secret_scan.subprocess, "run", fake_run)
    secret_scan.run_gitleaks("src")
    assert not os.path.exists(seen["path"])
