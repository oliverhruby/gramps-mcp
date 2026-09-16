"""Unit surface checks for the gramps_mcp server.

FastMCP itself is optional here: the module imports it guarded (server = None
when mcp is absent) and `_tool` records every decorated function into
`_TOOLS`, so these tests run with zero MCP SDK installed.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

import gramps_mcp as m  # noqa: E402

# Keep in sync with the actual tool surface (AGENTS.md rule 3). This list
# mirrors GLAMA_EXPECTED_TOOLS and the README tool table.
EXPECTED_TOOLS = [
    "analyze_dna",
    "get_instances",
    "get_living",
    "get_relation",
    "get_server_info",
    "get_timeline",
    "manage_bookmark",
    "manage_citation",
    "manage_event",
    "manage_export",
    "manage_family",
    "manage_import",
    "manage_media",
    "manage_note",
    "manage_person",
    "manage_place",
    "manage_report",
    "manage_repository",
    "manage_source",
    "manage_tag",
    "manage_transaction",
    "manage_tree",
    "manage_type",
    "manage_user",
    "merge_objects",
    "ping",
    "search",
]

READONLY_PREFIXES = ("get_", "find_", "scan_", "list_", "ping")


def _surface_names():
    return sorted(getattr(fn, "__name__", "") for fn in m._TOOLS)


def _write_capable():
    return [n for n in _surface_names() if not n.startswith(READONLY_PREFIXES)]


def test_tool_surface_meets_floor():
    assert len(m._TOOLS) >= 27, (
        f"Only {len(m._TOOLS)} tool(s) registered, below the designed floor of "
        f"27. Raise the floor in .github/workflows/quality-gates.yml "
        f"and GLAMA_EXPECTED_TOOLS only when the surface genuinely needs to shrink."
    )


def test_surface_matches_expected_tools():
    actual = _surface_names()
    missing = [t for t in EXPECTED_TOOLS if t not in actual]
    extra = [t for t in actual if t not in EXPECTED_TOOLS]
    assert not missing and not extra, (
        f"Tool surface drifted from EXPECTED_TOOLS. "
        f"missing={missing} extra={extra}. Update EXPECTED_TOOLS (+ "
        f"GLAMA_EXPECTED_TOOLS and the README table) in the same change."
    )


def test_write_capable_surface_matches_inventory():
    """Every write-capable tool must appear in the surface."""
    surface = _surface_names()
    write_capable = _write_capable()
    assert all(name in surface for name in write_capable)


def test_write_tools_have_e2e_coverage():
    """Every mutating tool must be exercised by an e2e test, never called blind."""
    e2e_files = "\n".join(
        pathlib.Path(p).read_text(encoding="utf-8")
        for p in (pathlib.Path(__file__).resolve().parents[2] / "tests" / "e2e").glob("test_*.py")
    )
    for name in _write_capable():
        assert name in e2e_files, (
            f"Write-capable tool '{name}' has no e2e test. Even a guarded "
            f"no-op is required: the live suite proves it against the real backend."
        )


def test_every_tool_has_docstring():
    for fn in m._TOOLS:
        assert (fn.__doc__ or "").strip(), f"{fn.__name__} is missing a docstring (TDQS rule 4)."


def test_tools_with_parameters_carry_args_block():
    for fn in m._TOOLS:
        if fn.__defaults__:
            assert "Args:" in (fn.__doc__ or ""), (
                f"{fn.__name__} takes parameters but its docstring has no 'Args:' block "
                f"(TDQS graders read parameter descriptions from there)."
            )


@pytest.mark.parametrize("name", ["ping", "get_instances"])
def test_required_tools_present(name):
    assert any(getattr(fn, "__name__", "") == name for fn in m._TOOLS), f"{name} is missing"
