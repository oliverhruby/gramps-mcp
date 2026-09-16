# Gramps MCP MCP Server

Full-coverage MCP server for Gramps genealogy (Gramps Web API backend): CRUD for all object types, search, merge, timelines, relations, living status, DNA, media, import/export, reports, transactions, users, trees.

A production-grade MCP server, scaffolded from the canonical, **Glama-proven**
reference project (29-tool all-A server model): identical Dockerfile, CI/CD
hardware, security checks, quality gates, release pipeline, and Glama TDQS
watchdog.

## Features

- Full-coverage facade over the **Gramps Web REST API** (people, families,
  events, places, sources, citations, notes, media, repositories, tags) —
  each `manage_*` tool serves get/create/update/delete via one `action` param.
- Genealogy-specific compute tools: full-text/semantic `search`, `merge_objects`
  (phoenix/titanic), person & family `get_timeline`, `get_relation`,
  `get_living` (alive estimates + probable dates), `analyze_dna` (matches,
  Y-DNA, segment parser).
- Media deep coverage: binary upload, file download, thumbnails, OCR, face
  detection.
- Data management: `manage_import` (file + dry-run + restore), `manage_export`
  (GEDCOM/Gramps XML with privacy filters), `manage_report` (list, generate,
  download), `manage_transaction` (raw apply/undo, history, bulk create/delete).
- Administration: `manage_user`, `manage_tree` (create/update/disable/enable/
  repair/migrate/verify/config), `manage_bookmark`, `manage_type`, plus
  `get_server_info` (database, versions, locale, object counts, capabilities).
- Multi-instance: `GRAMPS_MCP_INSTANCES` targets one or more Gramps Web base
  URLs; username/password login via `/api/token/` with token refresh, or
  pre-issued JWTs via `GRAMPS_MCP_TOKENS`.
- **Quality gates by default**: py_compile, Docker MCP handshake, HTTP auth
  smoke, Trivy, Glama TDQS watchdog (tool grades + inventory + score).
- Privacy-first verified workflow for live integration testing.

## What it provides

25 domain tools (plus `ping` and `get_instances`), grouped below. Keep this
table in sync with the tool surface — AGENTS.md rule 3.

| Tool | Purpose |
| --- | --- |
| `ping` | Health check. |
| `get_instances` | List configured Gramps Web instances. |
| `manage_person` | CRUD Gramps Person records (`action` = get/list, create, update, delete). |
| `manage_family` | CRUD Family records (father/mother/children refs are maintained upstream). |
| `manage_event` | CRUD Event records (types from `manage_type`). |
| `manage_place` | CRUD Place records. |
| `manage_source` | CRUD Source records. |
| `manage_citation` | CRUD Citation records (link to `source_handle`). |
| `manage_note` | CRUD Note records (holds DNA segment strings, prose, etc.). |
| `manage_media` | CRUD Media + binary upload, file download, thumbnail, OCR, face detection. |
| `manage_repository` | CRUD Repository records. |
| `manage_tag` | CRUD Tag records. |
| `search` | Full-text or semantic search, filterable by object type. |
| `merge_objects` | Merge two objects of the same type (phoenix survives). |
| `get_timeline` | Chronological timeline for a person, family, or whole tree. |
| `get_relation` | Degree/relationship path(s) between two people. |
| `get_living` | Likely-living verdict or probable birth/death date estimates. |
| `analyze_dna` | DNA matches, Y-DNA clade, and raw match-string parser. |
| `manage_import` | List importers, import a file (dry-run supported), restore a backup. |
| `manage_export` | List exporters, export (GEDCOM/Gramps XML/CSV...) with privacy filters. |
| `manage_report` | List reports, generate, and download report files. |
| `manage_transaction` | Apply/undo raw transactions, history, bulk create/delete objects. |
| `manage_user` | List/get/create/update/delete users, change passwords. |
| `manage_tree` | Trees: create/update, disable/enable, repair, migrate, verify, config. |
| `manage_bookmark` | Per-namespace bookmark lists and add/remove. |
| `manage_type` | Default & custom type vocabularies (event/name/place types, ...). |
| `get_server_info` | Server/database/version/locale/counts metadata from `/metadata/`. |

## Configuration

| Env var | Required | Description |
| --- | --- | --- |
| `GRAMPS_MCP_INSTANCES` | yes | Comma-separated Gramps Web base URLs (`https://gw.example.com`) |
| `GRAMPS_MCP_USERNAME` | no* | Account username (or set `GRAMPS_MCP_TOKENS`) |
| `GRAMPS_MCP_PASSWORD` | no* | Account password |
| `GRAMPS_MCP_TOKENS` | no | Comma-separated pre-issued JWTs, aligned with `GRAMPS_MCP_INSTANCES` |
| `GRAMPS_MCP_TIMEOUT` | no | Gramps Web API read timeout in seconds (default 60) |
| `GRAMPS_MCP_INSECURE` | no | Set `1` to skip TLS verification (self-signed servers) |
| `MCP_TRANSPORT` | no | `stdio` (default), `sse`, or `streamable-http` |
| `MCP_HOST` / `MCP_PORT` | no | Streamable HTTP binding (`127.0.0.1:8000`) |
| `MCP_API_KEY` | no | Enables bearer-token auth on the HTTP transport |

\* Login is lazy: the server starts without credentials, and each instance
logs in on first use via `POST /api/token/`.

## Usage

```bash
# stdio (default)
uvx gramps-mcp

# HTTP with auth
$env:MCP_TRANSPORT = "streamable-http"
$env:MCP_HOST = "0.0.0.0"
$env:MCP_API_KEY = "change-me"
uvx gramps-mcp
```

### With MCP clients

```json
{
  "mcpServers": {
    "gramps-mcp": {
      "command": "uvx",
      "args": ["gramps-mcp"],
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

## Testing & quality

- Unit: `.venv\Scripts\python -m pytest tests/unit -q` (no MCP SDK needed).
- Live e2e: `.\run_e2e.ps1` — local-only, privacy-first (see CONTRIBUTING).
- CI gates: Docker MCP handshake, HTTP auth smoke, Trivy scan.
- Glama TDQS: weekly watchdog on tool grades, inventory list, and overall
  `qualityScore` (issue `glama-quality`).

See [CONTRIBUTING.md](CONTRIBUTING.md) for everything operational.

## Privacy

The live e2e suite touches real accounts and real data. It never runs in
public CI; it never commits, logs, or uploads identities — CI compares only
one-way SHA-256 fingerprints, local runs keep exact values in gitignored
files.

## License

[MIT](LICENSE). Copyright (c) 2026 Oliver Hruby.