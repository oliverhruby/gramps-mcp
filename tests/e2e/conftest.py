"""Live e2e fixtures.

EVERYTHING IN THIS FILE IS PRIVACY-SENSITIVE. This suite runs against real
accounts and records real user data. By design:

  * It is skipped unless GRAMPS_MCP_E2E = 1 (see run_e2e.ps1).
  * GRAMPS_MCP_E2E_CI = 1 forces zero-data output: dot-only results and NO
    payload previews / ids / identity text in the report or in assert messages.
  * `expected_identities` and any exact checks read the gitignored
    tests/e2e/.local.e2e.json; CI only ever compares one-way SHA-256
    fingerprints. The suite is read-only by default.
"""
import hashlib
import json
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

import gramps_mcp  # noqa: E402

E2E = os.environ.get("GRAMPS_MCP_E2E", "") == "1"
E2E_CI = os.environ.get("GRAMPS_MCP_E2E_CI", "") == "1"
REPORT_DIR = pathlib.Path(__file__).resolve().parents[2] / "reports"
REPORT = REPORT_DIR / "e2e-report.json"


def sha256_hex(value: str) -> str:
    """One-way fingerprint. CI compares these, never raw identities."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_local_identities():
    """Exact identities from the gitignored .local.e2e.json file (owner-only)."""
    p = pathlib.Path(__file__).resolve().parent / ".local.e2e.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _redact(value, allow_ci: bool):
    if E2E_CI and not allow_ci:
        return sha256_hex(str(value))
    return value


def write_report(payload: dict) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def _session():
    results = {"failed": [], "redaction": "sha256" if E2E_CI else "raw"}
    yield
    write_report(results)


@pytest.fixture()
def record_failure(_session):
    def rec(name: str):
        _session["failed"].append(name)

    return rec


@pytest.fixture()
def identities():
    return load_local_identities()


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: live integration tests (require GRAMPS_MCP_E2E=1)")


def pytest_collection_modifyitems(config, items):
    if not E2E:
        skip_e2e = pytest.mark.skip(reason="set GRAMPS_MCP_E2E=1 (run_e2e.ps1) to run live tests")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)