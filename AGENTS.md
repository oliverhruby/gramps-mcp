# AGENTS.md

Maintainer guidance for AI agents on this repo (not user docs — that is
README.md). This file intentionally holds **only what cannot be derived from
the code**: decisions, traps, and external context. Everything else — layout,
architecture, state model, build/verify commands, e2e operations, release
process, CI/CD workflow reference, Conventional Commits — lives in
[CONTRIBUTING.md](CONTRIBUTING.md). Read it before structural work.

## Rules — decisions, not derivable from code

1. **Thin facade.** This server wraps the underlying system/library. All
   endpoint/parsing/login logic belongs upstream — never grow a scraping
   layer here. When something breaks, check upstream first.

2. **`mcp<2` is an API-compat pin, not a security pin.** `mcp` 2.x renamed
   `FastMCP` → `MCPServer` and broke the v1 API. Keep the pin and the
   `ignore: mcp >=2.0.0` block in `.github/dependabot.yml`.

3. **Tool surface is a designed constraint.** Prefer a small toolset with a
   discriminating `param=` over many near-identical tools. Adding or removing
   tools MUST update, in the same change: the `>=2` tool floor in
   `.github/workflows/quality-gates.yml`, the `GLAMA_EXPECTED_TOOLS` list in
   `.github/workflows/glama-quality.yml`, the README tool table, and the
   `tests/e2e/test_manifest.py` manifests.

4. **Docstrings are product, not prose.** Glama grades each tool with TDQS and
   gates the server on `qualityScore` (≥ 4.0, tier A). The grader sees the
   full docstring plus one `description` per parameter, taken from its
   Google-style `Args:` block. Every tool docstring must therefore carry an
   `Args:` block and, where relevant, a cross-reference telling agents which
   sibling tool to use instead. Keep them dense — no credit for restating the
   schema.

5. **Follow the tool skeleton in `src/gramps_mcp/__init__.py`:** `@_tool`
   functions returning `_run(go, "name")`. `_tool` records the function
   plainly into `_TOOLS` so tests introspect it without MCP installed; `_run`
   turns exceptions into `{"isError": ...}` JSON-RPC results. Reuse
   `_serialize`, `_define_instances`, `fail` rather than reimplementing.

6. **FastMCP 1.x has no `version` param.** The server pins
   `server._mcp_server.version` from the installed dist info via `_APP_DIST`
   in `__init__.py`. Keep `_APP_DIST` equal to the `pyproject.toml` project
   name (`gramps-mcp`); otherwise the advertised server version is wrong.

7. **e2e privacy (public repo + public CI).** Exact identities must never be
   committed, printed in CI logs, or uploaded as artifacts. CI checks only
   one-way SHA-256 fingerprints; local exact checks read the gitignored
   `tests/e2e/.local.e2e.json`; `GRAMPS_MCP_E2E_CI=1` forces zero-data
   output. The `e2e-ci.yml` workflow is **dormant** — use `run_e2e.ps1`
   locally on the owner's machine. Fingerprint regeneration is owner-only;
   its commit message must not contain identities.

## Before shipping

- Sanity: `python -m py_compile src/gramps_mcp/__init__.py` and
  `python -m pytest tests/unit -q`; a manual MCP `tools/list` is the real
  verification.
- Keep tool docstrings / README / test manifests in sync with the surface
  (rules 3 + 4).
- Commit with Conventional Commits; see CONTRIBUTING.md for all operational
  detail (local setup, e2e, releases, CI/CD).