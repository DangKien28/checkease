"""Unit tests cho Semgrep runner (mock subprocess — không cần cài semgrep)."""

import json
import subprocess
from types import SimpleNamespace

from apps.code_analysis import semgrep_runner


def _proc(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _capture_run(monkeypatch, proc):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return proc

    monkeypatch.setattr(semgrep_runner.subprocess, "run", fake_run)
    return calls


def _payload(results=None, errors=None, scanned=None):
    return json.dumps({
        "results": results or [],
        "errors": errors or [],
        "paths": {"scanned": scanned or [], "skipped": []},
    })


def test_build_command_uses_pinned_rules_and_safe_flags():
    cmd = semgrep_runner.build_command("src")
    joined = " ".join(cmd)
    assert "--config=auto" not in joined
    for flag in ("--json", "--metrics=off", "--disable-version-check",
                 "--no-rewrite-rule-ids", "--strict", "--error"):
        assert flag in cmd
    assert f"--config={semgrep_runner.RULES_DIR}" in cmd
    assert cmd[-1] == "src"


def test_run_semgrep_detects_findings_and_never_uses_shell(monkeypatch):
    entry = {"check_id": "checkease-eval-exec", "path": "a.py",
             "start": {"line": 3},
             "extra": {"severity": "WARNING", "lines": "eval(x)"}}
    calls = _capture_run(monkeypatch, _proc(1, _payload([entry], scanned=["a.py"])))
    res = semgrep_runner.run_semgrep("src")
    assert res.state == "FINDINGS"
    assert res.returncode == 1
    cmd, kwargs = calls[0]
    assert kwargs.get("shell") is False
    assert "scan" in cmd


def test_run_semgrep_clean(monkeypatch):
    _capture_run(monkeypatch, _proc(0, _payload([])))
    res = semgrep_runner.run_semgrep("src")
    assert res.state == "CLEAN"
    assert res.data["paths"]["scanned"] == []


def test_run_semgrep_tool_error_fatal(monkeypatch):
    _capture_run(monkeypatch, _proc(2, "", "boom"))
    res = semgrep_runner.run_semgrep("src")
    assert res.state == "TOOL_ERROR"
    assert "fatal error" in res.state_reason


def test_run_semgrep_tool_error_unparseable_yaml(monkeypatch):
    _capture_run(monkeypatch, _proc(5, "", "invalid yaml"))
    res = semgrep_runner.run_semgrep("src")
    assert res.state == "TOOL_ERROR"
    assert "unparseable YAML" in res.state_reason


def test_run_semgrep_invalid_json(monkeypatch):
    _capture_run(monkeypatch, _proc(0, "not json"))
    res = semgrep_runner.run_semgrep("src")
    assert res.state == "TOOL_ERROR"


def test_run_semgrep_timeout(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 300)

    monkeypatch.setattr(semgrep_runner.subprocess, "run", fake_run)
    res = semgrep_runner.run_semgrep("src")
    assert res.state == "TOOL_ERROR"
    assert "timed out" in res.state_reason


def test_run_semgrep_without_pinned_rules(monkeypatch, tmp_path):
    monkeypatch.setattr(semgrep_runner, "RULES_DIR", tmp_path)
    res = semgrep_runner.run_semgrep("src")
    assert res.state == "TOOL_ERROR"
    assert "rule đã pin" in res.state_reason


def test_run_semgrep_keeps_warnings_when_exit_nonzero_but_has_results(monkeypatch):
    entry = {"check_id": "x", "path": "a.py", "start": {"line": 1},
             "extra": {"severity": "INFO", "lines": "x"}}
    payload = _payload([entry], errors=[{"message": "parse warning"}])
    _capture_run(monkeypatch, _proc(2, payload))
    res = semgrep_runner.run_semgrep("src")
    assert res.state == "FINDINGS"           # vẫn có kết quả -> không bỏ hết
    assert res.tool_errors == ["parse warning"]


def test_ruleset_sha256_is_stable_and_changes_with_rules(tmp_path):
    d = tmp_path / "rules"
    d.mkdir()
    (d / "a.yaml").write_text("rules: []\n", encoding="utf-8")
    first = semgrep_runner.ruleset_sha256(d)
    assert first == semgrep_runner.ruleset_sha256(d)
    (d / "b.yaml").write_text("rules: []\n", encoding="utf-8")
    assert semgrep_runner.ruleset_sha256(d) != first


def test_ruleset_hash_covers_repo_rules():
    assert semgrep_runner.ruleset_sha256() == semgrep_runner.ruleset_sha256()
    assert len(semgrep_runner.rule_files()) >= 1
