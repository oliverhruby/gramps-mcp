"""Guarantee the tool surface stays intentional.

The committed EXPECTED_TOOLS manifest lives in tests/unit/test_tool_surface.py
where it actually runs in CI. This e2e module contains only the live-backend
checks that require GRAMPS_MCP_E2E=1 (via run_e2e.ps1).
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

import gramps_mcp  # noqa: E402


@pytest.mark.e2e
def test_surface_is_readonly_in_ci():
    pytest.skip("Surface inventory check only; read-only guarantee is enforced by conftest guards.")
