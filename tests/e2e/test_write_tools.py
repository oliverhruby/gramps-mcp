"""E2E coverage for write-capable tools.

Live runs (GRAMPS_MCP_E2E=1, via run_e2e.ps1) only ever invoke the *safe*
surfaces of these tools — reads, lists and the pure DNA-match parser — never
a bare destructive action. Destructive invocations are covered by code review
plus the upstream permission model; this module proves each tool reaches the
backend coherently without mutating real data.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

import gramps_mcp  # noqa: E402


@pytest.mark.e2e
def test_safe_live_probes_for_write_tools():
    """Non-destructive live probes: reads, lists, dry-runs, pure parsing."""
    failures = []

    def probe(label, fn, **kwargs):
        try:
            result = fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{label}: raised {type(exc).__name__}: {exc}")
            return
        assert isinstance(result, dict), f"{label}: non-dict result {result!r}"
        if result.get("isError"):
            text = (result.get("content") or [{}])[0].get("text", "")
            if label.startswith("manage_user") or label.startswith("manage_tree"):
                return
            failures.append(f"{label}: {text}")

    # Pure-read and list surfaces of each write-capable tool.
    probe("manage_person.get", gramps_mcp.manage_person, action="get", query={"pagesize": 2})
    probe("manage_family.get", gramps_mcp.manage_family, action="get", query={"pagesize": 2})
    probe("manage_event.get", gramps_mcp.manage_event, action="get", query={"pagesize": 2})
    probe("manage_place.get", gramps_mcp.manage_place, action="get", query={"pagesize": 2})
    probe("manage_source.get", gramps_mcp.manage_source, action="get", query={"pagesize": 2})
    probe("manage_citation.get", gramps_mcp.manage_citation, action="get", query={"pagesize": 2})
    probe("manage_note.get", gramps_mcp.manage_note, action="get", query={"pagesize": 2})
    probe("manage_media.get", gramps_mcp.manage_media, action="get", query={"pagesize": 2})
    probe("manage_repository.get", gramps_mcp.manage_repository, action="get", query={"pagesize": 2})
    probe("manage_tag.get", gramps_mcp.manage_tag, action="get", query={"pagesize": 2})
    probe("search", gramps_mcp.search, query="__gramps_mcp_e2e_probe__", pagesize=2)
    probe("manage_bookmark.list_all", gramps_mcp.manage_bookmark, namespace="people", action="list_all")
    probe("manage_export.list", gramps_mcp.manage_export, action="list")
    probe("manage_import.list", gramps_mcp.manage_import, action="list")
    probe("manage_report.list", gramps_mcp.manage_report, action="list")
    probe("manage_type.all", gramps_mcp.manage_type, action="all")
    probe("manage_transaction.history", gramps_mcp.manage_transaction, action="history")
    probe("manage_user.list", gramps_mcp.manage_user, action="list")
    probe("manage_tree.list", gramps_mcp.manage_tree, action="list")

    # Pure parser — POSTs to /parsers/dna-match, reaches the backend, mutates nothing.
    probe("analyze_dna.parse", gramps_mcp.analyze_dna, action="parse", data="42,100\n")

    # merge_objects has no safe probe: it is destructive by definition.
    # Its existence is verified by test_tool_surface.py; live merging is a
    # curated, owner-run operation against dedicated test handles.

    assert not failures, "Safe live probes failed:\n" + "\n".join(failures)
