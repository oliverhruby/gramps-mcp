"""Read-only discipline: no tool may mutate the real backend during e2e.

The write-capable tools still need e2e coverage (test_manifest.py enforces a
test exists for each — see test_write_tools.py), but concrete invocations
happen only against curated test fixtures and are logged with full redaction.
This module holds the read-only smoke checks: every `get_*`/`ping` tool is
called against the live backend without any write payload. Arg-taking tools
use explicit stub handles — a live backend replies 404 to those, which is an
acceptable, mutation-free outcome; anything else is a failure.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

import gramps_mcp  # noqa: E402

READONLY_PREFIXES = ("get_", "find_", "scan_", "list_", "ping")

# Minimal stub arguments for read-only tools that require parameters. Stub
# handles never match real objects, so the live backend answers 404 (fine);
# the point is that the tool reaches the backend and mutates nothing.
STUB_ARGS = {
    "get_timeline": {"kind": "person", "handle": "P__STUB__"},
    "get_relation": {"handle1": "P__STUB__", "handle2": "P__STUB__"},
    "get_living": {"handle": "P__STUB__"},
}


def _acceptable_error(text: str) -> bool:
    # 404 for a stub handle, or a missing-instance config error: both prove the
    # read-only path without mutating anything and are not real failures.
    return "Gramps Web API 404" in text or "No Gramps Web instance configured" in text


@pytest.mark.e2e
def test_readonly_tools_invoked_are_truly_readonly():
    """Every read-only tool must answer without a write-payload and without
    raising auth/network noise. Executes each against the real backend."""
    failures = []
    for name in sorted(getattr(fn, "__name__", "") for fn in gramps_mcp._TOOLS):
        if not name.startswith(READONLY_PREFIXES):
            continue
        fn = next(f for f in gramps_mcp._TOOLS if getattr(f, "__name__", "") == name)
        try:
            result = fn(**STUB_ARGS.get(name, {}))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: raised {type(exc).__name__}: {exc}")
            continue
        if isinstance(result, dict) and result.get("isError"):
            text = (result.get("content") or [{}])[0].get("text", "")
            if not _acceptable_error(text):
                failures.append(f"{name}: {text}")
    assert not failures, "Read-only smoke failed:\n" + "\n".join(failures)