# Gramps MCP Server
<!-- mcp-name: io.github.oliverhruby/gramps-mcp -->

[![publish](https://github.com/oliverhruby/gramps-mcp/actions/workflows/publish.yml/badge.svg)](https://github.com/oliverhruby/gramps-mcp/actions/workflows/publish.yml)

[![quality-gates](https://github.com/oliverhruby/gramps-mcp/actions/workflows/quality-gates.yml/badge.svg)](https://github.com/oliverhruby/gramps-mcp/actions/workflows/quality-gates.yml)

[![container-security](https://github.com/oliverhruby/gramps-mcp/actions/workflows/container-security.yml/badge.svg)](https://github.com/oliverhruby/gramps-mcp/actions/workflows/container-security.yml)



**Full-coverage MCP server for Gramps genealogy (Gramps Web API backend): CRUD for all object types, search, merge, timelines, relations, living status, DNA, media, import/export, reports, transactions, users, trees.**
A production-grade MCP server, scaffolded from the canonical, **Glama-proven** reference project (27-tool all-A server model): identical Dockerfile, CI/CD hardware, security checks, quality gates, release pipeline, and Glama TDQS watchdog.



## What it provides

**27 tools** — full CRUD for every Gramps object type, genealogy-specific compute, media deep coverage, import/export/reports/transactions, administration, multi-instance + JWT auth, and quality gates by default.

Tools are grouped by domain:

| Domain | Tools |
|---|---|
| **Core CRUD** | `ping`, `get_instances` |
| Persons | `manage_person`, `search`, `merge_objects`, `get_timeline`, `get_relation`, `get_living`, `analyze_dna` |
| Families | `manage_family` |
| Events | `manage_event` |
| Places | `manage_place` |
| Sources | `manage_source`, `manage_citation` |
| Notes | `manage_note` |
| Media | `manage_media` (binary upload, file download, thumbnail, OCR, face detection) |
| Repositories | `manage_repository` |
| Tags | `manage_tag` |
| Import/Export | `manage_import`, `manage_export` (GEDCOM/Gramps XML/CSV with privacy filters) |
| Reports | `manage_report` |
| Transactions | `manage_transaction` (apply/undo, history, bulk create/delete) |
| Administration | `manage_user`, `manage_tree` (create/update/disable/enable/repair/migrate/verify/config), `manage_bookmark`, `manage_type` |
| Server info | `get_server_info` (database, versions, locale, object counts, capabilities) |

## Why another Gramps MCP server?

| Server | Tools | Stars | Key Differentiators |
|---|---|---|---|
| **gramps-mcp-full** (this) | 27 (full CRUD + genealogy compute) | N/A | Full CRUD for all object types via `action` param; genealogy compute (merge, timeline, relation, living, DNA); media deep coverage (upload/download/thumbnail/OCR/face); import/export/reports/transactions; admin (users/trees/bookmarks/types); multi-instance + JWT auth; quality gates (Trivy, Glama, Docker handshake, HTTP smoke); MCP Registry + PyPI + GHCR publishing |
| Knuckles-Team/gramps-mcp | 35 action-routed tools | ~?? | A2A agent, OTEL telemetry, single GRAMPS_URL, JWT token login, Docker `knucklessg1/gramps-mcp` |
| cabout-me/gramps-mcp | 16 tools | 42 stars | Docker Compose based, GRAMPS_API_URL + username/password + tree id, HTTP first, AGPL-3.0 |
| Scormave/gramps-web-mcp | 57 tools | 12 stars | .NET 8/10, multi-transport, read-only mode, GHCR `scormave/gramps-web-mcp`, 6 resources |
| Genealogy-MCP/gramps-mcp (GitLab) | ~32 tools | ?? | AGPLv3, 32 releases, mirror, focuses on ... |

**Our differentiators:** 27 focused tools (vs 57 fragmented or 35 action-routed), deep genealogy compute (merge survival, timeline/relation/living/DNA), media pipeline with OCR/face, full import/export/report/transaction lifecycle, admin over users/trees/bookmark/type, multi-instance + JWT refresh, and a quality-gate suite covering every layer (lint → Docker → Trivy → Glama).

## Getting started

| Method | Command |
|---|---|
| **PyPI** | `uvx gramps-mcp-full` |
| **Docker** | `docker run --rm -i -e GRAMPS_MCP_USERNAME=... -e GRAMPS_MCP_PASSWORD=... ghcr.io/oliverhruby/gramps-mcp:latest` |
| **Development** | `python -m pip install -e . pytest` |

## Configuration

| Env var | Required | Description |
|---|---|---|
| `GRAMPS_MCP_INSTANCES` | yes | Comma-separated Gramps Web base URLs (`https://gw.example.com`) |
| `GRAMPS_MCP_USERNAME` | no* | Account username (or set `GRAMPS_MCP_TOKENS`) |
| `GRAMPS_MCP_PASSWORD` | no* | Account password |
| `GRAMPS_MCP_TOKENS` | no | Comma-separated pre-issued JWTs, aligned with `GRAMPS_MCP_INSTANCES` |
| `GRAMPS_MCP_TIMEOUT` | no | Gramps Web API read timeout in seconds (default 60) |
| `GRAMPS_MCP_INSECURE` | no | Set `1` to skip TLS verification (self-signed servers) |
| `MCP_TRANSPORT` | no | `stdio` (default), `sse`, or `streamable-http` |
| `MCP_HOST` / `MCP_PORT` | no | Streamable HTTP binding (`127.0.0.1:8000`) |
| `MCP_API_KEY` | no | Enables bearer-token auth on the HTTP transport |

* Login is lazy: the server starts without credentials, and each instance logs in on first use via `POST /api/token/`.

## Usage

### stdio (default)

```bash
uvx gramps-mcp-full
```

### HTTP with auth

```bash
$env:MCP_TRANSPORT = "streamable-http"
$env:MCP_HOST = "0.0.0.0"
$env:MCP_API_KEY = "change-me"
uvx gramps-mcp-full
```

### With MCP clients (Claude Desktop, etc.)

```json
{
  "mcpServers": {
    "gramps-mcp-full": {
      "command": "uvx",
      "args": ["gramps-mcp-full"],
      "env": {
        "GRAMPS_MCP_USERNAME": "...",
        "GRAMPS_MCP_PASSWORD": "..."
      }
    }
  }
}
```

### Docker

```bash
docker run --rm -i -e GRAMPS_MCP_USERNAME=... -e GRAMPS_MCP_PASSWORD=... ghcr.io/oliverhruby/gramps-mcp:latest
```

## Prompt examples

- `List all people with birth dates after 1900.`
- `Show the family tree for person I001.`
- `Merge person I002 into I001, keeping I001's data (phoenix survival).`
- `Get the chronological timeline for person I015.`
- `What is the relationship between person I003 and I020?`
- `Is person I005 likely living? Estimate probable birth/death dates.`
- `Analyze DNA matches for person I010; show Y-DNA clade and segment positions.`
- `Upload a media file for person I012; generate a thumbnail and run OCR.`
- `Import a GEDCOM file (dry-run first), then restore from backup if needed.`
- `Export the tree as GEDCOM with privacy filters for living persons.`
- `Generate a research report for person I018 and download the PDF.`
- `Apply a bulk transaction to add source citations to all people born in 1850.`
- `List all users and disable the account `ciowner`.`
- `Create a new tree named "CI Example Tree" and configure its base URL.`
- `Add a bookmark "direct ancestors" for person I009 under namespace "research".`
- `List all default and custom event/place/source types.`
- `Get server metadata: database version, locale, object counts, capabilities.`

## Tool reference (27 tools)

See the "What it provides" table above for the complete grouped listing. Keep this table in sync with the tool surface — AGENTS.md rule 3.

## Data & safety notes

- The live e2e suite touches real accounts and real data. It never runs in public CI; it never commits, logs, or uploads identities — CI compares only one-way SHA-256 fingerprints, local runs keep exact values in gitignored files.
- Quality gates run on every PR: `py_compile`, Docker MCP handshake, HTTP auth smoke, Trivy scan, and Glama TDQS watchdog (tool grades + inventory + overall `qualityScore`).
- Glama inventory must match `GLAMA_EXPECTED_TOOLS` (currently 27 tools); any addition/removal must sync the quality-gates workflow, Glama slug, README table, and `tests/e2e/test_manifest.py`.

## Contributing

- Follow [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, e2e, releases, and CI/CD.
- Conventional Commits for all changes.
- Before adding or removing a tool, update these sync points: quality-gates.yml tool floor, glama-quality.yml `GLAMA_EXPECTED_TOOLS`, README tool table, `tests/e2e/test_manifest.py` manifests.
- Run `python -m py_compile src/gramps_mcp/__init__.py` and `python -m pytest tests/unit -q` before committing.

## Limitations

- Requires Gramps Web API version compatible with this server's facade (check `/metadata/` via `get_server_info`).
- Token refresh window: pre-issued JWTs via `GRAMPS_MCP_TOKENS` must align with `GRAMPS_MCP_INSTANCES` ordering; misordered tokens cause auth failures.
- Media OCR/face detection depends on external service availability; results may degrade when those services are offline.
- Glama TDQS grades depend on docstring quality; improving a tool's grade requires updating its docstring in `src/gramps_mcp/__init__.py` and tagging a new release.

## License

[MIT](LICENSE). Copyright (c) 2026 Oliver Hruby.