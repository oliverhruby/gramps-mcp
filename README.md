# Gramps MCP Server

<!-- mcp-name: io.github.oliverhruby/gramps-mcp -->

[![GitHub release](https://img.shields.io/github/v/tag/oliverhruby/gramps-mcp.svg?sort=semver&label=release)](https://github.com/oliverhruby/gramps-mcp/releases)
[![Quality gates](https://img.shields.io/github/actions/workflow/status/oliverhruby/gramps-mcp/quality-gates.yml.svg?label=quality%20gates)](https://github.com/oliverhruby/gramps-mcp/actions/workflows/quality-gates.yml)
[![Security](https://img.shields.io/github/actions/workflow/status/oliverhruby/gramps-mcp/security.yml.svg?label=security)](https://github.com/oliverhruby/gramps-mcp/actions/workflows/security.yml)
[![Container security](https://img.shields.io/github/actions/workflow/status/oliverhruby/gramps-mcp/container-security.yml.svg?label=container%20security)](https://github.com/oliverhruby/gramps-mcp/actions/workflows/container-security.yml)

## Project

A Model Context Protocol (MCP) server that exposes the full functionality of the Gramps Web API to AI agents such as opencode, Claude, Cursor and any other MCP client. It is published on PyPI as [`gramps-mcp-full`](https://pypi.org/project/gramps-mcp-full/).

Gramps is a free, open-source genealogy program, and **Gramps Web** ships a REST API (`gramps-web-api`) that lets you read and operate a family tree — people, families, events, places, sources, citations, notes, media, repositories and tags, plus genealogy compute (merge, timelines, relations, living status, DNA), import/export, reports, transactions and server administration.

This server lets your agent query and operate a Gramps tree directly: full CRUD for all object types, full-text/semantic search, merge objects (phoenix/titanic survival), timelines, relationships, alive estimates, DNA match analysis, a media pipeline (binary upload, file download, thumbnails, OCR, face detection), GEDCOM / Gramps XML import and export with privacy filters, report generation, raw transactions, and admin over users, trees, bookmarks and type vocabularies — including **multiple instances** (one or more Gramps Web base URLs, each with token/JWT auth).

> **⚠️ Official API, mutable data.** Unlike the EduPage server (which reverse-engineers undocumented endpoints), this uses the **official, documented** Gramps Web REST API — [`gramps-web-api`](https://github.com/gramps-project/gramps-web-api), maintained under the `gramps-project` organization with a published OpenAPI spec at <https://gramps-project.github.io/gramps-web-api/>. Use read-only features freely; use the write features (`manage_*`, `merge_objects`, `manage_import`, `manage_transaction`, …) carefully — they mutate real tree data.

---

## Table of Contents

- [Why another Gramps MCP server?](#why-another-gramps-mcp-server)
- [What it provides](#what-it-provides)
- [Getting started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Install](#1-install)
  - [2. Configure credentials](#2-configure-credentials)
  - [3. Register with your MCP client](#3-register-with-your-mcp-client)
- [Prompt examples](#prompt-examples)
- [Multiple instances (base URLs)](#multiple-instances-base-urls)
- [Tool reference](#tool-reference)
- [Data & safety notes](#data--safety-notes)
- [Contributing](#contributing)
- [Limitations](#limitations)
- [Support](#support)
- [License](#license)

---

## Why another Gramps MCP server?

Other Gramps MCP servers already exist:

- [`Knuckles-Team/gramps-mcp`](https://github.com/Knuckles-Team/gramps-mcp) — 35 action-routed tools, A2A agent, OTEL telemetry, single `GRAMPS_URL`
- [`cabout-me/gramps-mcp`](https://github.com/cabout-me/gramps-mcp) — 16 tools, AGPL-3.0, Docker Compose based, HTTP-first
- [`Scormave/gramps-web-mcp`](https://github.com/Scormave/gramps-web-mcp) — 57 tools + 6 resources, .NET, multi-transport, read-only mode
- [`Genealogy-MCP/gramps-mcp`](https://gitlab.com/Genealogy-MCP/gramps-mcp) — AGPLv3, GitLab mirror, 32 releases

All are good and I have **no affiliation** with them — they are simply referenced here for honest comparison. They either fragment the surface into many near-identical tools or cover only read-mostly slices of the API.

This project deliberately goes further:

| Capability | Knuckles-Team/gramps-mcp | cabout-me/gramps-mcp | Scormave/gramps-web-mcp | **this project** |
|---|---|---|---|---|
| **Full CRUD** — people, families, events, places, sources, citations, notes, media, repositories, tags | partial (actions) | partial | ✅ | ✅ |
| **One `manage_*` tool per object type** (`action=` get/list/create/update/delete) | ❌ | ❌ | ❌ | ✅ |
| **Genealogy compute** — `merge_objects` (phoenix/titanic), `get_timeline`, `get_relation`, `get_living` | ❌ | ❌ | partial | ✅ |
| **DNA analysis** — `analyze_dna` (matches, Y-DNA, segment parser) | ❌ | ❌ | ❌ | ✅ |
| **Media pipeline** — binary upload, file download, thumbnails, OCR, face detection | ❌ | partial | partial | ✅ |
| **Import / export** — GEDCOM / Gramps XML with dry-run, restore, privacy filters | import only | import only | export only | ✅ |
| **Reports** — list, generate, download | ❌ | ❌ | ❌ | ✅ |
| **Transactions** — raw apply/undo, history, bulk create/delete | ❌ | ❌ | ❌ | ✅ |
| **Administration** — users, trees (repair/migrate/verify/config), bookmarks, types | partial | ❌ | partial | ✅ |
| **Server metadata** — database, versions, locale, counts, capabilities | ❌ | ❌ | ❌ | ✅ |
| **Multiple instances** — one or more Gramps Web base URLs | ❌ | ❌ | ✅ | ✅ |
| **Auth** — lazy token login `/api/token/` + pre-issued JWTs + refresh | JWT | user/pass | token | ✅ |
| **Read-only mode** | ❌ | ❌ | ✅ | ❌ |
| **Quality gates by default** — py_compile, Docker MCP handshake, HTTP auth smoke, Trivy, Glama TDQS watchdog | ❌ | ❌ | ❌ | ✅ |
| **Publishing** — PyPI, GHCR, MCP Registry, Glama | PyPI | Docker Hub/GitHub | GHCR | ✅ |

**Key differentiators:**

- **Tight toolset with discriminating parameters.** 27 tools (vs 57 fragmented or 35 action-routed): every object type is served by one `manage_*` tool with an `action=` parameter, mirroring the canonical `get_timetable`/`login` family design.
- **Genealogy-specific compute.** Merge with phoenix/titanic survival, chronological timelines, relationship degrees/paths, living status with probable dates, and a real DNA segment parser — not just object storage.
- **Full write surface.** Import/export with privacy filters and dry-run, report generation, raw transactions, user/tree/bookmark/type administration — the other servers don't cover these.
- **Production-ready.** Multi-instance + token/JWT auth with refresh, quality gates on every PR (lint → Docker handshake → HTTP auth smoke → Trivy → Glama TDQS watchdog), and OIDC publishing to PyPI, GHCR and the MCP Registry.

---

## What it provides

A single MCP server exposing **27 tools** (published on PyPI as [`gramps-mcp-full`](https://pypi.org/project/gramps-mcp-full/)):

- **Core** — `ping` (health), `get_instances` (configured Gramps Web base URLs)
- **Objects (full CRUD)** — `manage_person`, `manage_family`, `manage_event`, `manage_place`, `manage_source`, `manage_citation`, `manage_note`, `manage_media`, `manage_repository`, `manage_tag` — each takes one `action=` (`get`, `list`, `create`, `update`, `delete`); `manage_media` also handles binary upload, file download, thumbnails, OCR and face detection
- **Search & compute** — `search` (full-text/semantic, filterable by object type), `merge_objects` (phoenix survives by default, titanic optional), `get_timeline` (person/family/tree), `get_relation` (degree + paths), `get_living` (status or probable dates), `analyze_dna` (matches, Y-DNA, segment parser)
- **Data management** — `manage_import` (list importers, import file with dry-run, restore backup), `manage_export` (list exporters, export GEDCOM/Gramps XML/CSV with privacy filters), `manage_report` (list/generate/download), `manage_transaction` (apply/undo raw payloads, history, bulk create/delete)
- **Administration** — `manage_user`, `manage_tree` (create/update/disable/enable/repair/migrate/verify/config), `manage_bookmark` (per-namespace), `manage_type` (default + custom vocabularies), `get_server_info` (database, versions, locale, object counts, capabilities)

---

## Getting started

You need an MCP-capable client (opencode, Claude Desktop, Cursor, etc.) and a reachable Gramps Web instance (base URL + a user account with the needed permissions).

### 1. Install

If you are using an AI coding client, a simple prompt is often enough to get started, for example: "Install the Gramps MCP as described in this GitHub repository oliverhruby/gramps-mcp". Most MCP-capable clients can then guide you through the available setup options.

**Option A — from MCP Registry (recommended, one-click in VS Code / GitHub Copilot)**

The server is listed in the [MCP Registry](https://registry.modelcontextprotocol.io/). In VS Code or GitHub Copilot, search for "Gramps MCP" and install with one click. Or use the direct deeplink: `mcp://install/io.github.oliverhruby/gramps-mcp`

**Option B — from PyPI**

Use this for normal usage with a released version.

Requirements: `uv` for `uvx`, or Python **3.10+** for `pip`.

```bash
uvx gramps-mcp-full
# or, if you prefer pip (into whatever environment your MCP client uses):
pip install gramps-mcp-full
```

`uvx` runs the package without a persistent install. If `uvx` is unavailable, install `uv` first (`pip install uv` or `winget install astral-sh.uv`).

**Option C — from GitHub (latest source)**

Use this if you want the latest changes before a PyPI release.

Requirements: `uv` for `uvx`, or Python **3.10+** for `pip`.

```bash
uvx --from "git+https://github.com/oliverhruby/gramps-mcp.git" gramps-mcp-full
# or
pip install "git+https://github.com/oliverhruby/gramps-mcp.git"
```

**Option D — Docker**

Use this for an isolated container runtime.

Requirements: Docker.

Pull a prebuilt image (recommended):

```bash
docker pull ghcr.io/oliverhruby/gramps-mcp:latest

docker run --rm -i \
  -e GRAMPS_MCP_INSTANCES=https://gw.example.com \
  -e GRAMPS_MCP_USERNAME=your_username \
  -e GRAMPS_MCP_PASSWORD=your_password \
  ghcr.io/oliverhruby/gramps-mcp:latest
```

Version tags are also available (for example `v0.1.0`) if you prefer pinned images.

Build locally from source (fallback):

```bash
docker build -t gramps-mcp-full .

docker run --rm -i \
  -e GRAMPS_MCP_INSTANCES=https://gw.example.com \
  -e GRAMPS_MCP_USERNAME=your_username \
  -e GRAMPS_MCP_PASSWORD=your_password \
  gramps-mcp-full
```

The container uses the same environment variables described in [Configure credentials](#2-configure-credentials). It also includes a `HEALTHCHECK` (stdio process liveness by default; local TCP check in HTTP transport modes).

For HTTP transports, set optional runtime vars:

- `MCP_TRANSPORT`: `stdio` (default), `sse`, or `streamable-http`
- `MCP_HOST`: bind host (default `127.0.0.1`)
- `MCP_PORT`: bind port (default `8000`)
- `MCP_API_KEY`: optional bearer token for HTTP auth

When `MCP_API_KEY` is set, HTTP requests must include `Authorization: Bearer <key>`. If `MCP_API_KEY` is not set, HTTP endpoints are unauthenticated. For production, prefer proper authentication and TLS via a reverse proxy or API gateway.

> `pyproject.toml` pins `mcp<2` (the stable FastMCP v1 API). `mcp 2.x` renamed `FastMCP` to `MCPServer` and changed the API surface; this server targets the FastMCP v1 API for simplicity and stability.

**Development from source**

Use this if you are contributing or debugging locally.

Requirements: Python **3.10+**.

```bash
git clone https://github.com/oliverhruby/gramps-mcp.git
cd gramps-mcp
pip install -e . pytest
```

### 2. Configure credentials

Either set environment variables **or** pass them at runtime. Point the server at your Gramps Web instance(s) and account:

```bash
# Windows (persistent, per-user)
setx GRAMPS_MCP_INSTANCES "https://gw.example.com,https://gw2.example.com"   # one or more base URLs
setx GRAMPS_MCP_USERNAME "your_username"
setx GRAMPS_MCP_PASSWORD "your_password"

# macOS / Linux
export GRAMPS_MCP_INSTANCES="https://gw.example.com,https://gw2.example.com"
export GRAMPS_MCP_USERNAME="your_username"
export GRAMPS_MCP_PASSWORD="your_password"
```

**Single instance?** Just set the base URL plus `GRAMPS_MCP_USERNAME` / `GRAMPS_MCP_PASSWORD`. Login is lazy — the server starts without credentials and logs in on first use via `POST /api/token/`.

**Multiple instances?** Add a comma-separated `GRAMPS_MCP_INSTANCES` list. Login happens per instance `api/token/` (default on first use). Alternatively, set `GRAMPS_MCP_TOKENS` (comma-separated, aligned with `GRAMPS_MCP_INSTANCES`) to seed pre-issued JWTs for each instance.

Other knobs: `GRAMPS_MCP_TIMEOUT` (read timeout seconds, default `60`), `GRAMPS_MCP_INSECURE=1` (skip TLS verification for self-signed servers).

### 3. Register with your MCP client

**opencode** — add to `~/.config/opencode/opencode.json` (or `opencode.jsonc`):

```jsonc
{
  "mcp": {
    "gramps": {
      "type": "local",
      "enabled": true,
      "command": ["uvx", "gramps-mcp-full"],
      "env": {
        "GRAMPS_MCP_INSTANCES": "{env:GRAMPS_MCP_INSTANCES}",
        "GRAMPS_MCP_USERNAME": "{env:GRAMPS_MCP_USERNAME}",
        "GRAMPS_MCP_PASSWORD": "{env:GRAMPS_MCP_PASSWORD}"
      }
    }
  }
}
```

> Put credentials in your shell/environment (or a `.env`) and reference them with `{env:VAR}`, or hardcode them under `env:` directly. `uvx` will auto-provision the package the first time; it must be on your `PATH`.

**Claude Desktop / Cursor** — use `claude_desktop_config.json` / `.mcp.json` with a `mcpServers` entry in the standard shape, pointing `command`/`args` at the venv python and the `gramps_mcp.py` path, plus an `env` block with your credentials.

After editing client config, **restart the client** so the MCP server is loaded.

---

## Prompt examples

| User prompt | Likely tool call(s) | Expected response |
|---|---|---|
| "Are we connected and logged in?" | `ping` → `get_instances` | Server health and the configured Gramps Web instance(s). |
| "List all people with birth dates after 1900" | `manage_person action="list"` | A short list of matching people. |
| "Show the family tree for person I001" | `manage_family action="list"` → `get_timeline handle="I001"` | The person's family and chronological timeline. |
| "Merge person I002 into I001, keeping I001's data" | `merge_objects obj_type="person" handle1="I001" handle2="I002"` | Merge confirmation (phoenix survival). |
| "What is the relationship between person I003 and I020?" | `get_relation handle1="I003" handle2="I020"` | Degree of kinship plus the path(s) between them. |
| "Is person I005 likely living?" | `get_living handle="I005"` | Likely-living verdict or probable birth/death date estimates. |
| "Analyze DNA matches for person I010" | `analyze_dna action="matches" handle="I010"` | DNA matches, Y-DNA clade, and parsed segments. |
| "Upload a media file for person I012" | `manage_media action="upload" handle="I012" …` | Media object created; thumbnail + OCR available. |
| "Export the tree as GEDCOM with privacy filters" | `manage_export extension="gedcom" options={"privacy": …}` | Export file produced and downloadable. |
| "Import a GEDCOM file (dry-run first)" | `manage_import action="import" extension="gedcom" file_path="…"` | Dry-run report, then the import result. |
| "Generate a research report for person I018" | `manage_report action="generate" report_id="…"` | Report generated and downloadable. |
| "Apply a raw transaction to update a source" | `manage_transaction action="apply" payload="…"` | Transaction applied (and undoable later). |
| "List all users, then disable `ciowner`" | `manage_user action="list"` → `manage_user action="update" data={…}` | User list and the disabled account. |
| "Create a new tree and configure its base URL" | `manage_tree action="create" data={…}` → `… action="config_set"` | New tree created and configured. |
| "List all default and custom event/place types" | `manage_type action="all"` | Type vocabularies per object type. |
| "Get server metadata" | `get_server_info` | Database, versions, locale, object counts, capabilities. |

---

## Multiple instances (base URLs)

Each Gramps Web instance keeps its **own** session. Two ways to configure:

**A) Environment (recommended).** Set `GRAMPS_MCP_INSTANCES` (comma-separated base URLs) plus shared `GRAMPS_MCP_USERNAME` / `GRAMPS_MCP_PASSWORD` — the server logs into each instance lazily on first use:

```bash
setx GRAMPS_MCP_INSTANCES "https://gw.example.com,https://gw2.example.com"   # Windows
export GRAMPS_MCP_INSTANCES="https://gw.example.com,https://gw2.example.com" # macOS / Linux
```

```text
get_instances     # lists both base URLs + login status per instance
```

Each data tool targets the active instance; every instance logs in lazily on its
first use via `api/token/`.

**B) Pre-issued JWTs.** Set `GRAMPS_MCP_TOKENS` (comma-separated) aligned with `GRAMPS_MCP_INSTANCES` — sessions are seeded directly, no on-demand `api/token/` login.

> **Single instance?** Just `GRAMPS_MCP_INSTANCES` + `USERNAME` + `PASSWORD`. For several, add them to the comma-separated list (auto-login) or seed `GRAMPS_MCP_TOKENS`.

---

## Tool reference

| Tool | Description | Writes? |
|---|---|---|
| `ping` | Health check. | 💡 read |
| `get_instances` | List configured Gramps Web instances. | 💡 read |
| `manage_person` | CRUD Person records (`action` = get/list/create/update/delete). | ✅ create/update/delete |
| `manage_family` | CRUD Family records (father/mother/children refs maintained upstream). | ✅ create/update/delete |
| `manage_event` | CRUD Event records (types from `manage_type`). | ✅ create/update/delete |
| `manage_place` | CRUD Place records. | ✅ create/update/delete |
| `manage_source` | CRUD Source records. | ✅ create/update/delete |
| `manage_citation` | CRUD Citation records (link to `source_handle`). | ✅ create/update/delete |
| `manage_note` | CRUD Note records (holds DNA segment strings, prose, etc.). | ✅ create/update/delete |
| `manage_media` | CRUD Media + binary upload, file download, thumbnail, OCR, face detection. | ✅ create/update/delete/upload |
| `manage_repository` | CRUD Repository records. | ✅ create/update/delete |
| `manage_tag` | CRUD Tag records. | ✅ create/update/delete |
| `search` | Full-text or semantic search, filterable by object type. | 💡 read |
| `merge_objects` | Merge two objects of the same type into one. | ✅ merge |
| `get_timeline` | Chronological event timeline for a person, family, or whole tree. | 💡 read |
| `get_relation` | Compute a genealogical relationship between two people. | 💡 read |
| `get_living` | Estimate whether (or until when) a person is alive. | 💡 read |
| `analyze_dna` | DNA match analysis and raw match-string parsing. | ✅ parse only |
| `manage_import` | List importers or import a file (Gramps XML, GEDCOM…); dry-run + restore. | ✅ file/restore |
| `manage_export` | List exporters or produce an export (GEDCOM, Gramps XML…); privacy filters. | ✅ run |
| `manage_report` | List, configure or generate reports (PDF, text, web…). | ✅ run |
| `manage_transaction` | Apply raw DB transactions, undo history, or bulk create/delete. | ✅ all actions |
| `manage_user` | Administer Gramps Web users (create/update/delete/change password). | ✅ all actions |
| `manage_tree` | Trees: create/update, disable/enable, repair, migrate, verify, config. | ✅ all actions |
| `manage_bookmark` | Read or edit bookmarks per object namespace. | ✅ add/remove |
| `manage_type` | List Gramps type vocabularies (custom + default) for all object types. | 💡 read |
| `get_server_info` | Read server, database, locale and object-count metadata. | 💡 read |

✅ write / 💡 read labels come from each tool's docstring (AGENTS.md rule 4).

---

## Data & safety notes

- Most tools have both **read** and **write** paths via `action=`. The write actions (marked ✅ above) mutate real Gramps tree data — use them with care and prefer dry-runs where available (`manage_import` dry-run, export preview) before destructive operations.
- `merge_objects` defaults to **phoenix** survival (the surviving object keeps its handle); pass the appropriate option for titanic survival. There is no undo — consider a `manage_transaction` snapshot or an export backup beforehand.
- `manage_transaction` applies raw DB payloads; mistakes are undoable via `action="undo"` with the returned transaction id, but the tree is otherwise mutated in place.
- The live e2e suite touches real accounts and real data. It never runs in public CI; it never commits, logs, or uploads identities — CI compares only one-way SHA-256 fingerprints, local runs keep exact values in gitignored files.
- Quality gates run on every PR: `py_compile`, Docker MCP handshake, HTTP auth smoke, Trivy scan, and Glama TDQS watchdog (tool grades + inventory + overall `qualityScore`).

---

## Contributing

Contributor and maintainer guidance is in [CONTRIBUTING.md](CONTRIBUTING.md).

- Contribution workflow and local setup
- Architecture and implementation details
- Release process (PyPI, GitHub Releases, GHCR, MCP Registry)
- CI quality gates and the Glama TDQS watchdog
- Convention: keep the 4 sync points in lockstep when adding/removing tools (quality-gates tool floor, `GLAMA_EXPECTED_TOOLS`, README tool table + count, `tests/e2e/test_manifest.py`)

---

## Limitations

- **Depends on the official Gramps Web API.** Field coverage follows the upstream `gramps-project/gramps-web-api` REST schema; object payloads use Gramps handle/`gramps_id` conventions.
- **Write tools mutate real data with no confirmation layer.** Never run destructive tool-calls you don't understand; the server does not add an extra confirmation prompt on top of the API.
- **Auth lives for the process lifetime.** Sessions are created lazily per instance via `api/token/` and refreshed on demand; it is not a browser-style persistent login.
- **Media OCR / face detection depend on optional Gramps Web services.** When the instance doesn't enable them, those `manage_media` features degrade to upload/download only.
- **Single-tree license constraints.** Gramps Web's free tier historically gates multi-user/tree features; administration tools (`manage_user`, some `manage_tree` actions) require a license tier that exposes them.
- **`MCP_API_KEY` only protects the HTTP transport.** For production, terminate TLS and authenticate via a reverse proxy in front of the streamable-HTTP endpoint.

---

## Support

If you like this project and want to support or request a feature, send me a beer, it keeps my mind relaxed and ideas will come :-)

[![Support via PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.me/oliverhruby/)

---

## License

[MIT](LICENSE) © Oliver Hrubý

This project is **not affiliated with or endorsed by** the Gramps project or the authors of `gramps-web-api`. Gramps is a trademark of its respective owner(s).