# Contributing

Everything an operator/agent needs beyond what is derivable from the code.
Shorter internal rulebook: [AGENTS.md](AGENTS.md).

## Repository layout

```
src/gramps_mcp/        server (single big __init__.py: env, helpers, all tools)
tests/unit/             offline surface tests (no MCP SDK needed)
tests/e2e/              live integration suite (local-only, privacy-first)
scripts/                graders + release helpers (inherited from the canonical project)
.github/workflows/      CI/CD (see table below)
reports/                gitignored local artifacts (e2e report, watchdog outputs)
```

This project was scaffolded from the canonical, Glama-proven MCP project
(quality-gates, watchdog, security, publish/release pipeline). To inherit
upstream improvements, `git fetch` the source repo and cherry-pick/diff the
`scripts/` and `.github/workflows/` layer — never fork the domain code.

## Local setup

```powershell
python -m venv .venv            # or: uv venv
.venv\Scripts\python -m pip install -e . pytest
.venv\Scripts\python -m pytest tests/unit -q
```

Sanity (mirrors CI): `python -m py_compile src/gramps_mcp/__init__.py`.
The real verification is a manual MCP handshake:
`npx @modelcontextprotocol/inspector uvx gramps-mcp` then `tools/list`.

## Quality gates (AGENTS.md rule 3)

The tool surface is a designed constraint with 4 sync points that MUST move
together whenever a tool is added or removed:

1. tool floor in `.github/workflows/quality-gates.yml`
2. `GLAMA_EXPECTED_TOOLS` in `.github/workflows/glama-quality.yml`
3. the README tool table + "What it provides" count
4. `tests/e2e/test_manifest.py` (`EXPECTED_TOOLS`, write-coverage check)

Every tool docstring needs a Google-style `Args:` block — Glama's TDQS grader
reads parameter descriptions from it (AGENTS.md rule 4).

## Live e2e suite (local-only)

Real backend, real accounts, real user data. Never in public CI.

```powershell
$env:GRAMPS_MCP_USERNAME = "..."; $env:GRAMPS_MCP_PASSWORD = "..."
$env:GRAMPS_MCP_INSTANCES = "<id1,id2,..>"
.\run_e2e.ps1
```

- Requires the three env vars; skips unless `GRAMPS_MCP_E2E=1`.
- `GRAMPS_MCP_E2E_CI=1` → zero-data (dot-only, no identities).
- Exact identity checks read the gitignored `tests/e2e/.local.e2e.json`
  (`{ "person_name": { "inst": "<id>", "person_id": "<id>" } }`); CI compares
  only one-way SHA-256 fingerprints. Regenerating fingerprints is owner-only —
  the commit must not contain identities.
- The suite is read-only on the real backend (conftest guards mutating tools).

## Release process

CI handles it (tag → version check → PyPI + GHCR + MCP Registry publish via
OIDC):

1. Bump `version` in `pyproject.toml` (`feat:/fix:` commit, Conventional Commits).
2. Push the change to `main`, then push a **manual** tag `v<version>` — the
   auto-tag was deliberately removed; CI only verifies tag↔version match
   (`scripts/check_tag_matches_version.py`).
3. `release` workflow builds, runs quality gates, publishes PyPI, builds/pushes
   the container, and registers `server.json` with the MCP Registry.

First-time repo setup: PyPI OIDC publisher, MCP Registry OIDC,
`release` GitHub environment, GHCR package settings, and secrets. Full
checklist in `skills/mcp-server-scaffold`.

## CI/CD workflow reference

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `quality-gates` | PR, push to `main`, manual | py_compile, pip install, Docker MCP stdio handshake + `>=N` tools, HTTP auth smoke |
| `security` | PR, push to `main`, schedule | pip/actions advisory, SAST-ish token scan |
| `container-security` | PR, push to `main`, schedule | Trivy image scan; quality gate for merges |
| `glama-quality` | weekly cron + manual | TDQS watchdog — opens/closes the `glama-quality` issue |
| `e2e-live` | manual, dormant | live suite on hosted runner when reachable |
| `publish` | release | publish to PyPI (OIDC) |
| `publish-container` | release | build/push `ghcr.io/oliverhruby/gramps-mcp` |
| `publish-mcp-registry` | release | register/update `server.json` in the MCP Registry |
| `release` | tag | orchestrates the above |
| dependabot | daily | updates deps; `mcp<2` pinned with an ignore block |

To run a manual workflow: `gh workflow run <name>` (see each file's `on`).

## Conventions

- Conventional Commits (`feat:`, `fix:`, `chore:`) — the release pipeline keys
  off them.
- No secrets, no real identities in commits, logs, reports (AGENTS.md rule 7).
- The hidden `.opencode/skills/dev-playbook` skill encodes the agent-side
  working rules — keep it in sync when changing the rules above.