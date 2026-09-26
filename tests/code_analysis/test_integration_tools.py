"""Integration test chạy công cụ THẬT (tự skip nếu chưa cài semgrep/gitleaks).

Chạy trong CI/đồ án khi đã cài công cụ:
    semgrep --version && gitleaks version
"""

import shutil
from pathlib import Path

import pytest

from apps.code_analysis.secret_scan import run_gitleaks
from apps.code_analysis.semgrep_runner import ruleset_sha256, run_semgrep

SEMGREP_INSTALLED = shutil.which("semgrep") is not None
GITLEAKS_INSTALLED = shutil.which("gitleaks") is not None


@pytest.fixture()
def vulnerable_project(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text(
        'API_KEY = "AKIAIOSFODNN7REALKEY"\n'
        "\n"
        "def run(user_input):\n"
        "    eval(user_input)\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.skipif(not SEMGREP_INSTALLED, reason="semgrep CLI chưa cài")
def test_real_semgrep_scan(vulnerable_project):
    res = run_semgrep(str(vulnerable_project))
    assert res.state in {"FINDINGS", "CLEAN"}, res.state_reason
    if res.state == "FINDINGS":
        ids = {r.get("check_id") for r in res.data.get("results", [])}
        assert "checkease-eval-exec" in ids


@pytest.mark.skipif(not SEMGREP_INSTALLED, reason="semgrep CLI chưa cài")
def test_real_semgrep_is_reproducible(vulnerable_project):
    first = run_semgrep(str(vulnerable_project))
    second = run_semgrep(str(vulnerable_project))
    assert first.state == second.state
    if first.state == "FINDINGS":
        ids_first = sorted(r["check_id"] for r in first.data["results"])
        ids_second = sorted(r["check_id"] for r in second.data["results"])
        assert ids_first == ids_second


@pytest.mark.skipif(not GITLEAKS_INSTALLED, reason="gitleaks CLI chưa cài")
def test_real_gitleaks_scan(vulnerable_project):
    res = run_gitleaks(str(vulnerable_project))
    assert res.state_reason == ""
    assert res.triggered is True
    assert res.findings
    for finding in res.findings:
        assert finding.secret_sha256
        assert finding.secret_length > 0


def test_ruleset_hash_stable():
    assert ruleset_sha256() == ruleset_sha256()
