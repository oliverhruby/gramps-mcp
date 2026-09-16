"""gramps_mcp MCP server.

Exposes the full feature set of the Gramps Web API as MCP tools:
CRUD for every object type, search, merge, timelines, relations, living
status, DNA, media, import/export, reports, transactions, users, trees,
bookmarks, types and server info.

This is a thin facade over the Gramps Web REST API. All endpoint/parsing
logic belongs upstream (https://github.com/gramps-project/gramps-web-api) —
never grow a scraping layer here (see AGENTS.md).

Careful: the `manage_*` tools, `merge_objects`, `analyze_dna` (`parse`),
`manage_import`, `manage_export`, `manage_report` and `manage_transaction`
mutate state. All `get_*` tools are read-only.
"""

import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from dataclasses import fields, is_dataclass
from enum import Enum
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.auth.provider import AccessToken, TokenVerifier
    from mcp.server.auth.settings import AuthSettings
except Exception:
    FastMCP = None
    AccessToken = None
    TokenVerifier = None
    AuthSettings = None

GRAMPS_MCP_USERNAME = os.environ.get("GRAMPS_MCP_USERNAME", "")
GRAMPS_MCP_PASSWORD = os.environ.get("GRAMPS_MCP_PASSWORD", "")
# Comma-separated Gramps Web instance base URLs to target on startup
# (empty = auto-discovery). Each entry is the site origin (no "/api" suffix),
# e.g. "https://gw.example.com" or "https://gw.example.com,https://gw2.example.com".
GRAMPS_MCP_INSTANCES = os.environ.get("GRAMPS_MCP_INSTANCES", "")
# Comma-separated access tokens (JWTs) pre-issued per instance, in the same
# order/positions as GRAMPS_MCP_INSTANCES. Overrides username/password login.
GRAMPS_MCP_TOKENS = os.environ.get("GRAMPS_MCP_TOKENS", "")
# 1 = do not verify TLS certificates (self-signed Gramps Web instances).
GRAMPS_MCP_INSECURE = os.environ.get("GRAMPS_MCP_INSECURE", "") == "1"
# Read timeout in seconds for Gramps Web API calls.
_GRAMPS_MCP_TIMEOUT_RAW = os.environ.get("GRAMPS_MCP_TIMEOUT", "60")
try:
    GRAMPS_MCP_TIMEOUT = int(_GRAMPS_MCP_TIMEOUT_RAW)
    if GRAMPS_MCP_TIMEOUT <= 0:
        raise ValueError
except ValueError:
    GRAMPS_MCP_TIMEOUT = 60
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
_MCP_PORT_RAW = os.environ.get("MCP_PORT", "8000")
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")
_MCP_PORT_ERROR = None
try:
    MCP_PORT = int(_MCP_PORT_RAW)
    if MCP_PORT <= 0 or MCP_PORT > 65535:
        raise ValueError
except ValueError:
    MCP_PORT = 8000
    _MCP_PORT_ERROR = f"Error: invalid MCP_PORT '{_MCP_PORT_RAW}'. Expected an integer between 1 and 65535."

_APP_DIST = "gramps-mcp"


def _server_version() -> str:
    """Our published package version, from the installed distribution metadata.

    Single source of truth is `version` in pyproject.toml. Both PyPI wheels and
    the Docker image install this package via `pip`, so importlib.metadata
    resolves the same number everywhere. Falls back to "dev" only for bare
    source checkouts (not pip-installed)."""
    try:
        return _pkg_version(_APP_DIST)
    except PackageNotFoundError:
        return "dev"


def fail(message: str) -> dict:
    return {"isError": True, "content": [{"type": "text", "text": message}]}


def _define_instances():
    """Return configured instance identifiers from GRAMPS_MCP_INSTANCES."""
    return [s.strip() for s in GRAMPS_MCP_INSTANCES.split(",") if s.strip()]


def _serialize(obj):
    """Convert upstream objects (dataclasses, enums, times, dicts) to plain data."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_serialize(v) for v in obj]
    if is_dataclass(obj):
        out = {}
        for f in fields(obj):
            if f.name.startswith("__"):
                continue
            out[f.name] = _serialize(getattr(obj, f.name))
        return out
    if hasattr(obj, "__dict__"):
        out = {}
        for k, v in vars(obj).items():
            if k.startswith("_"):
                continue
            out[k] = _serialize(v)
        return out
    return str(obj)


def _to_text(data) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(_serialize(data), ensure_ascii=False, indent=2)}]}


# --------------------------------------------------------------------------
# helper indirection so FastMCP is optional (tests can call these directly)
# --------------------------------------------------------------------------
class _StaticApiKeyTokenVerifier:
    """Simple bearer token verifier backed by MCP_API_KEY."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def verify_token(self, token: str):
        if token != self.api_key:
            return None
        return AccessToken(token=token, client_id="mcp-api-key", scopes=["mcp"])  # type: ignore[misc]


if FastMCP:
    token_verifier = None
    auth_settings = None
    if MCP_API_KEY:
        token_verifier = _StaticApiKeyTokenVerifier(MCP_API_KEY)
        auth_settings = AuthSettings(
            issuer_url=f"http://{MCP_HOST}:{MCP_PORT}",
            resource_server_url=f"http://{MCP_HOST}:{MCP_PORT}",
            required_scopes=["mcp"],
        )
    server = FastMCP(
        "Gramps MCP",
        host=MCP_HOST,
        port=MCP_PORT,
        auth=auth_settings,
        token_verifier=token_verifier,
    )
    # FastMCP 1.x exposes no `version` parameter and the lowlevel Server falls
    # back to pkg_version("mcp"), so `initialize` would report the *mcp SDK*
    # version instead of ours. Pin it to our own distribution version so the
    # serverInfo advertises the version we published on PyPI / as a container.
    server._mcp_server.version = _server_version()
else:
    server = None

# Plain-callable tool registry, so unit tests introspect tools without MCP.
_TOOLS = []


def _tool(fn):
    if server is not None:
        decorated = server.tool()(fn)
    else:
        decorated = fn
    _TOOLS.append(fn)
    return decorated


def _run(fn, error_label="gramps-mcp call"):
    try:
        return fn()
    except _ApiError as e:
        return fail(f"{error_label}: {e}")
    except Exception as e:  # noqa: BLE001
        return fail(f"{error_label} failed: {type(e).__name__}: {e}")


# --------------------------------------------------------------------------
# Gramps Web API client (thin REST facade, no scraping)
# --------------------------------------------------------------------------
_VALID_ACTIONS = "one of: get, create, update, delete"


def _plural_for(obj_type: str) -> str:
    """Map a Gramps object type name to its collection route segment."""
    return {
        "person": "people",
        "people": "people",
        "family": "families",
        "families": "families",
        "event": "events",
        "events": "events",
        "place": "places",
        "places": "places",
        "source": "sources",
        "sources": "sources",
        "citation": "citations",
        "citations": "citations",
        "note": "notes",
        "notes": "notes",
        "media": "media",
        "repository": "repositories",
        "repositories": "repositories",
        "tag": "tags",
        "tags": "tags",
    }.get(str(obj_type).lower())


_MERGE_ROUTES = {
    "person": ("people", "Person"),
    "family": ("families", "Family"),
    "event": ("events", "Event"),
    "place": ("places", "Place"),
    "source": ("sources", "Source"),
    "citation": ("citations", "Citation"),
    "repository": ("repositories", "Repository"),
    "media": ("media", "Media"),
    "note": ("notes", "Note"),
}

_BOOKMARK_NAMESPACES = [
    "citations",
    "events",
    "families",
    "media",
    "notes",
    "people",
    "places",
    "repositories",
    "sources",
]


class _ApiError(Exception):
    """Raised when the Gramps Web API rejects a request."""


class _GrampsApi:
    """Tiny authenticated client for the Gramps Web REST API (/api/*)."""

    def __init__(self, instances, username, password, tokens, timeout, verify_ssl):
        self.instances = instances  # list of base URLs ("" for auto-discovery scope)
        self.username = username
        self.password = password
        self.tokens = tokens  # list aligned with instances; may be shorter
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._auth = {}  # base URL -> {"access": ..., "refresh": ...}
        self._ssl_ctx = None if verify_ssl else ssl._create_unverified_context()

    # -- instance resolution ------------------------------------------------
    def _configured(self, instance: str) -> str:
        """Resolve an instance identifier to a configured base URL."""
        if instance:
            if instance not in self.instances:
                raise _ApiError(
                    f"Unknown instance '{instance}'. Configured instances: "
                    + (", ".join(self.instances) if self.instances else "(none)")
                )
            return instance
        if self.instances:
            return self.instances[0]
        raise _ApiError(
            "No Gramps Web instance configured. Set GRAMPS_MCP_INSTANCES to one or "
            "more base URLs (e.g. 'https://gw.example.com')."
        )

    # -- auth ---------------------------------------------------------------
    def _token_for(self, base: str) -> str:
        """Return an access token for base, logging in lazily."""
        if base not in self._auth:
            self._auth[base] = {"access": None, "refresh": None}
        entry = self._auth[base]
        if entry.get("access"):
            return entry["access"]
        idx = self.instances.index(base) if base in self.instances else 0
        if idx < len(self.tokens) and self.tokens[idx]:
            entry["access"] = self.tokens[idx]
            return entry["access"]
        if not self.username or not self.password:
            raise _ApiError(
                f"Login required for instance '{base or '/'}': set GRAMPS_MCP_USERNAME/"
                "GRAMPS_MCP_PASSWORD or GRAMPS_MCP_TOKENS."
            )
        status, _headers, payload = self._request(
            base, "/token/", method="POST",
            body={"username": self.username, "password": self.password},
            retry_auth=False,
        )
        if status == 200 and isinstance(payload, dict):
            entry["access"] = payload.get("access_token") or ""
            entry["refresh"] = payload.get("refresh_token") or ""
            if entry["access"]:
                return entry["access"]
        raise _ApiError(f"Login to '{base or '/'}' failed (HTTP {status}).")

    def _refresh(self, base: str, entry: dict) -> bool:
        """Attempt a token refresh; returns True on success."""
        if not entry.get("refresh"):
            return False
        try:
            status, _headers, payload = self._request(
                base, "/token/refresh/", method="POST",
                body=None, token=entry["refresh"], retry_auth=False,
            )
        except _ApiError:
            return False
        if status == 200 and isinstance(payload, dict) and payload.get("access_token"):
            entry["access"] = payload["access_token"]
            return True
        entry["access"] = None
        entry["refresh"] = None
        return False

    # -- low-level request --------------------------------------------------
    def _full_url(self, base: str, path: str) -> str:
        if not path.startswith("/"):
            raise _ApiError(f"Internal: path must start with '/', got '{path}'")
        return (base.rstrip("/") + "/api" + path) if base else ("/api" + path)

    def _request(self, base, path, method="GET", query=None, body=None,
                 raw_body=None, content_type=None, token=None, retry_auth=True):
        """Perform a request and return (status, headers, payload).

        `payload` is parsed JSON when the response is JSON, else raw bytes.
        When `body` is a dict it is sent as JSON; `raw_body` is sent as-is
        (for file uploads)."""
        url = self._full_url(base, path)
        if query:
            q = urllib.parse.urlencode(
                {k: (("1" if v is True else "0") if isinstance(v, bool) else str(v))
                 for k, v in query.items() if v is not None},
                doseq=True,
            )
            if q:
                url += "?" + q
        if token is None:
            token = self._token_for(base)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "gramps-mcp",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif raw_body is not None:
            data = raw_body
            if content_type:
                headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:
                raw = resp.read()
                status = resp.status
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as e:
            status = e.code
            raw = None
            try:
                raw = e.read()
            except Exception:  # noqa: BLE001
                raw = None
            resp_headers = {k.lower(): v for k, v in getattr(e, "headers", {}).items()}
            if status == 401 and retry_auth and base in self._auth:
                entry = self._auth[base]
                entry["access"] = None
                if not self._refresh(base, entry):
                    entry["access"] = self._token_for(base)
                return self._request(
                    base, path, method=method, query=query, body=body,
                    raw_body=raw_body, content_type=content_type,
                    token=entry["access"], retry_auth=False,
                )
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            raise _ApiError(f"Network error for {url}: {reason}")
        except OSError as e:
            raise _ApiError(f"Connection error for {url}: {e}")
        else:
            self._check_status(url, status, raw, headers=resp_headers)
        return self._payload(status, raw, resp_headers)

    @staticmethod
    def _check_status(url, status, raw, headers):
        if status >= 400:
            detail = ""
            if raw:
                try:
                    parsed = json.loads(raw.decode("utf-8", "replace"))
                    if isinstance(parsed, dict):
                        msg = parsed.get("message") or parsed.get("error") or parsed.get("description")
                        detail = f": {msg}" if msg else ""
                except Exception:  # noqa: BLE001
                    detail = ""
            raise _ApiError(f"Gramps Web API {status} for {url}{detail}")

    @staticmethod
    def _payload(status, raw, resp_headers):
        if raw is None:
            return status, resp_headers, None
        ctype = resp_headers.get("content-type", "")
        if "application/json" in ctype:
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except ValueError:
                parsed = raw
        else:
            parsed = raw
        return status, resp_headers, parsed

    # -- public helpers -----------------------------------------------------
    def request(self, path, method="GET", query=None, body=None,
                raw_body=None, content_type=None, instance=""):
        base = self._configured(instance)
        status, headers, payload = self._request(
            base, path, method=method, query=query, body=body,
            raw_body=raw_body, content_type=content_type,
        )
        result = {"status": status, "url": self._full_url(base, path)}
        if isinstance(payload, bytes):
            result["filename_hint"] = _filename_from(headers)
            result["mimetype"] = headers.get("content-type", "application/octet-stream")
            result["base64"] = base64.b64encode(payload).decode("ascii")
            result["bytes"] = len(payload)
        else:
            total = headers.get("x-total-count")
            if total is not None and isinstance(payload, list):
                result["data"] = payload
                result["total"] = _safe_int(total, len(payload))
            else:
                result["data"] = payload
        return result

    def scan(self, path, instance="", page=1, pagesize=20, query=None):
        """Read one page of a list endpoint, returning {data, total}."""
        q = dict(query or {})
        q.setdefault("page", page)
        q.setdefault("pagesize", pagesize)
        return self.request(path, "GET", query=q, instance=instance)


def _filename_from(headers):
    cd = headers.get("content-disposition", "")
    if "filename=" in cd:
        return cd.split("filename=", 1)[1].strip("\"'")
    return None


def _safe_int(value, fallback):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


_gramps = None


def _api():
    global _gramps
    if _gramps is None:
        configured = _define_instances()
        _gramps = _GrampsApi(
            instances=configured,
            username=GRAMPS_MCP_USERNAME,
            password=GRAMPS_MCP_PASSWORD,
            tokens=[t.strip() for t in GRAMPS_MCP_TOKENS.split(",") if t.strip()],
            timeout=GRAMPS_MCP_TIMEOUT,
            verify_ssl=not GRAMPS_MCP_INSECURE,
        )
    return _gramps


def _drop_empty(data):
    """Drop None values from a dict before sending to the API."""
    if not isinstance(data, dict):
        return data
    return {k: v for k, v in data.items() if v is not None}


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
@_tool
def ping() -> dict:
    """Health check. Read-only.

    Args:
        (none)

    Returns:
        dict: {"pong": true, "version": <server version>}.
    """
    def go():
        return {"pong": True, "version": _server_version()}

    return _run(go, "ping")


@_tool
def get_instances() -> dict:
    """List the configured target instances. Read-only.

    Args:
        (none)

    Returns:
        dict: {"instances": [<base url>, ...], "scope": "<value of
        GRAMPS_MCP_INSTANCES, or 'auto-discovery' when unset>"}.
    """
    def go():
        configured = _define_instances()
        return {"instances": configured, "scope": ", ".join(configured) if configured else "auto-discovery"}

    return _run(go, "get_instances")


# --------------------------------------------------------------------------
# Generic CRUD plumbing (single discriminating `action` parameter per tool)
# --------------------------------------------------------------------------
_READ_ACTION = {
    "get": ("GET", None),
    "create": ("POST", False),
    "update": ("PUT", True),
    "delete": ("DELETE", True),
}


def _crud(collection, name, action, handle, data, query, instance):
    """Implement one manage_<type> tool over the Gramps Web CRUD endpoints.

    Handles the four standard actions:
      get    -> GET    /<collection>/            (list, when handle is empty)
                GET    /<collection>/<handle>
      create -> POST   /<collection>/            (body = data)
      update -> PUT    /<collection>/<handle>    (body = data)
      delete -> DELETE /<collection>/<handle>
    """
    method, need_handle = _READ_ACTION[action]
    if data is not None:
        data = _drop_empty(data)
    if method == "POST" and data is None:
        raise _ApiError(f"create requires a `data` payload (the {name} object).")
    path = f"/{collection}/"
    if need_handle or (method == "GET" and handle):
        if not handle:
            raise _ApiError(f"`handle` is required for action '{action}'.")
        path = f"/{collection}/{handle}"
    return _api().request(path, method=method, query=query or None, body=data, instance=instance)


# --------------------------------------------------------------------------
# Object CRUD tools
# --------------------------------------------------------------------------
@_tool
def manage_person(action: str, handle: str = None, data: dict = None,
                  query: dict = None, instance: str = "") -> dict:
    """Create, read, update or delete Gramps Person records. Writes: create, update, delete.

    `action=get` lists people (`handle` empty, paginated) or returns one person
    (`handle` set, `?profile=&extend=` via `query`). `action=create` posts a
    full Person JSON object in `data` (handles are assigned by the server).
    `action=update` PUTs `data` to /people/<handle>; `action=delete` removes it.
    Person payload fields follow the Gramps schema (gramps_id, gender,
    primary_name, names, event_ref_list, family_list, person_ref_list,
    attribute_list, media_list, address_list, url_list, note_list, change, ...).

    Args:
        action: The operation, "get", "create", "update" or "delete".
        handle: Person handle (e.g. 'P0001'); required for get-one, update, delete.
        data: The Person object for create/update (required for those).
        query: Optional dict of extra query-string parameters (e.g. {"page": 1,
            "pagesize": 20, "keys": "handle,name", "strip": true, "profile": "all",
            "extend": "all", "locale": "en"}).
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status": <http status>, "url": <api url>, "data": <object(s) | transaction>}.
    """
    def go():
        return _crud("people", "Person", action, handle, data, query, instance)

    return _run(go, "manage_person")


@_tool
def manage_family(action: str, handle: str = None, data: dict = None,
                  query: dict = None, instance: str = "") -> dict:
    """Create, read, update or delete Gramps Family records. Writes: create, update, delete.

    `action=get` lists families (`handle` empty) or returns one family by
    handle. `action=create` posts a full Family JSON object in `data`;
    `action=update` PUTs `data` to /families/<handle>; `action=delete` removes
    it. Family payload fields: gramps_id, father_handle, mother_handle,
    child_ref_list, event_ref_list, attribute_list, media_list, note_list,
    change, relationship, ... . Creating a family rewrites its parents' and
    children's person records, so it requires edit + add permissions upstream.

    Args:
        action: The operation, "get", "create", "update" or "delete".
        handle: Family handle (e.g. 'F0001'); required for get-one, update, delete.
        data: The Family object for create/update (required for those).
        query: Optional dict of extra query-string parameters for reads.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data"}.
    """
    def go():
        return _crud("families", "Family", action, handle, data, query, instance)

    return _run(go, "manage_family")


@_tool
def manage_event(action: str, handle: str = None, data: dict = None,
                 query: dict = None, instance: str = "") -> dict:
    """Create, read, update or delete Gramps Event records. Writes: create, update, delete.

    `action=get` lists events (`handle` empty) or returns one event by handle.
    `action=create` posts a full Event JSON object in `data`; `action=update`
    PUTs `data` to /events/<handle>; `action=delete` removes it. Event payload
    fields: gramps_id, type, date, description, place, citations, notes,
    attribute_list, media_list, change, ... . Events are typically referenced
    by Person/Family event_ref_list entries.

    Args:
        action: The operation, "get", "create", "update" or "delete".
        handle: Event handle; required for get-one, update, delete.
        data: The Event object for create/update (required for those).
        query: Optional dict of extra query-string parameters for reads.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data"}.
    """
    def go():
        return _crud("events", "Event", action, handle, data, query, instance)

    return _run(go, "manage_event")


@_tool
def manage_place(action: str, handle: str = None, data: dict = None,
                 query: dict = None, instance: str = "") -> dict:
    """Create, read, update or delete Gramps Place records. Writes: create, update, delete.

    `action=get` lists places (`handle` empty) or returns one place by handle.
    `action=create` posts a full Place JSON object in `data`; `action=update`
    PUTs `data` to /places/<handle>; `action=delete` removes it. Place payload
    fields: gramps_id, name, type, longitude, latitude, alt_names,
    place_ref_list, enclosed_by, media_list, note_list, change, ... . Use
    manage_place with a filter query instead of search when you need raw
    object data rather than full-text hits.

    Args:
        action: The operation, "get", "create", "update" or "delete".
        handle: Place handle; required for get-one, update, delete.
        data: The Place object for create/update (required for those).
        query: Optional dict of extra query-string parameters for reads.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data"}.
    """
    def go():
        return _crud("places", "Place", action, handle, data, query, instance)

    return _run(go, "manage_place")


@_tool
def manage_source(action: str, handle: str = None, data: dict = None,
                  query: dict = None, instance: str = "") -> dict:
    """Create, read, update or delete Gramps Source records. Writes: create, update, delete.

    `action=get` lists sources (`handle` empty) or returns one source by
    handle. `action=create` posts a full Source JSON object in `data`;
    `action=update` PUTs `data` to /sources/<handle>; `action=delete` removes
    it. Source payload fields: gramps_id, title, author, pubinfo, abbrev,
    reporef_list, media_list, note_list, change, ... . Citations of a source
    are managed with manage_citation.

    Args:
        action: The operation, "get", "create", "update" or "delete".
        handle: Source handle; required for get-one, update, delete.
        data: The Source object for create/update (required for those).
        query: Optional dict of extra query-string parameters for reads.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data"}.
    """
    def go():
        return _crud("sources", "Source", action, handle, data, query, instance)

    return _run(go, "manage_source")


@_tool
def manage_citation(action: str, handle: str = None, data: dict = None,
                    query: dict = None, instance: str = "") -> dict:
    """Create, read, update or delete Gramps Citation records. Writes: create, update, delete.

    `action=get` lists citations (`handle` empty) or returns one citation by
    handle. `action=create` posts a full Citation JSON object in `data`;
    `action=update` PUTs `data` to /citations/<handle>; `action=delete` removes
    it. Citation payload fields: gramps_id, source_handle, date, page,
    confidence, note_list, media_list, change, ... . Attach a citation to a
    Person/Family/Event by adding its handle to that object's citation_list.

    Args:
        action: The operation, "get", "create", "update" or "delete".
        handle: Citation handle; required for get-one, update, delete.
        data: The Citation object for create/update (required for those).
        query: Optional dict of extra query-string parameters for reads.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data"}.
    """
    def go():
        return _crud("citations", "Citation", action, handle, data, query, instance)

    return _run(go, "manage_citation")


@_tool
def manage_note(action: str, handle: str = None, data: dict = None,
                query: dict = None, instance: str = "") -> dict:
    """Create, read, update or delete Gramps Note records. Writes: create, update, delete.

    `action=get` lists notes (`handle` empty) or returns one note by handle.
    `action=create` posts a full Note JSON object in `data`; `action=update`
    PUTs `data` to /notes/<handle>; `action=delete` removes it. Note payload
    fields: gramps_id, type, text, format, note_list, change, ... . Notes are
    referenced by other objects' note_list fields; DNA match segment strings
    live in notes (see analyze_dna).

    Args:
        action: The operation, "get", "create", "update" or "delete".
        handle: Note handle; required for get-one, update, delete.
        data: The Note object for create/update (required for those).
        query: Optional dict of extra query-string parameters for reads.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data"}.
    """
    def go():
        return _crud("notes", "Note", action, handle, data, query, instance)

    return _run(go, "manage_note")


@_tool
def manage_media(action: str, handle: str = None, data: dict = None,
                 query: dict = None, file_path: str = None, mime_type: str = None,
                 size: int = None, instance: str = "") -> dict:
    """Manage Gramps Media objects and their files. Writes: create, update, delete, upload.

    Standard CRUD via /media/ plus binary operations:
      get/create/update/delete  -> as in manage_person (GET/POST/PUT/DELETE).
      upload                    -> POST /media/ streaming `file_path` bytes with
                                   `mime_type` (required); the API computes the
                                   checksum and creates the Media row.
      file                      -> GET /media/<handle>/file; returns base64 bytes.
      thumbnail                 -> GET /media/<handle>/thumbnail/<size>; returns
                                   base64 image; pass {"square": true} in `query`.
      ocr                       -> GET /media/<handle>/ocr; returns OCR text.
      face_detection            -> GET /media/<handle>/face_detection; returns
                                   detected/test faces (see upstream for params).
    Repeat `action` for repeated sub-actions; 'create' accepts a Media JSON body
    in `data` (needs an already-uploaded file), while 'upload' bulk-loads a
    local file. Consider merge_objects for duplicate media.

    Args:
        action: "get", "create", "update", "delete", "upload", "file",
            "thumbnail", "ocr" or "face_detection".
        handle: Media handle; required for get-one, update, delete, file,
            thumbnail, ocr, face_detection.
        data: The Media object for create/update (required for those).
        query: Optional dict of extra query-string parameters (e.g. {"square": true}).
        file_path: Local file path for the 'upload' action (required there).
        mime_type: MIME type of the upload (e.g. 'image/jpeg'); required for 'upload'.
        size: Thumbnail target size in pixels (required for 'thumbnail').
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data"} where binary results carry base64/mimetype.
    """
    def go():
        api = _api()
        if action in ("get", "create", "update", "delete"):
            return _crud("media", "Media", action, handle, data, query, instance)
        if action == "upload":
            if not file_path or not mime_type:
                raise _ApiError("upload requires both `file_path` and `mime_type`.")
            with open(file_path, "rb") as fh:
                raw = fh.read()
            return api.request("/media/", method="POST", raw_body=raw,
                               content_type=mime_type, instance=instance)
        if action in ("file", "ocr", "face_detection"):
            if not handle:
                raise _ApiError(f"`handle` is required for action '{action}'.")
            route = {
                "file": "/file",
                "ocr": "/ocr",
                "face_detection": "/face_detection",
            }[action]
            return api.request(f"/media/{handle}{route}", "GET",
                               query=query or None, instance=instance)
        if action == "thumbnail":
            if not handle or not size:
                raise _ApiError("thumbnail requires both `handle` and `size`.")
            return api.request(f"/media/{handle}/thumbnail/{size}", "GET",
                               query=query or None, instance=instance)
        raise _ApiError(f"Unknown action '{action}'. Expected one of: get, create, "
                        "update, delete, upload, file, thumbnail, ocr, face_detection.")

    return _run(go, "manage_media")


@_tool
def manage_repository(action: str, handle: str = None, data: dict = None,
                      query: dict = None, instance: str = "") -> dict:
    """Create, read, update or delete Gramps Repository records. Writes: create, update, delete.

    `action=get` lists repositories (`handle` empty) or returns one by handle.
    `action=create` posts a full Repository JSON object in `data`;
    `action=update` PUTs `data` to /repositories/<handle>; `action=delete`
    removes it. Repository payload fields: gramps_id, type, name, address_list,
    url_list, note_list, change, ... . Sources link to a repository through
    their reporef_list entry.

    Args:
        action: The operation, "get", "create", "update" or "delete".
        handle: Repository handle; required for get-one, update, delete.
        data: The Repository object for create/update (required for those).
        query: Optional dict of extra query-string parameters for reads.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data"}.
    """
    def go():
        return _crud("repositories", "Repository", action, handle, data, query, instance)

    return _run(go, "manage_repository")


@_tool
def manage_tag(action: str, handle: str = None, data: dict = None,
               query: dict = None, instance: str = "") -> dict:
    """Create, read, update or delete Gramps Tag records. Writes: create, update, delete.

    Tags are lightweight labels attachable to any object. `action=get` lists
    tags (`handle` empty) or returns one by handle; `action=create` posts a Tag
    JSON object (`name` required) in `data`; `action=update` PUTs `data` to
    /tags/<handle>; `action=delete` removes it. To tag an object, reference the
    tag handle in that object's `tag_list`.

    Args:
        action: The operation, "get", "create", "update" or "delete".
        handle: Tag handle; required for get-one, update, delete.
        data: The Tag object for create/update (required for those).
        query: Optional dict of extra query-string parameters for reads.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data"}.
    """
    def go():
        return _crud("tags", "Tag", action, handle, data, query, instance)

    return _run(go, "manage_tag")


# --------------------------------------------------------------------------
# Primary read/compute tools
# --------------------------------------------------------------------------
@_tool
def search(query: str, type: str = None, page: int = None, pagesize: int = None,
           sort: str = None, profile: str = None, strip: bool = None,
           semantic: bool = None, change: str = None, locale: str = None,
           instance: str = "") -> dict:
    """Full-text (or semantic) search across the Gramps tree. Read-only.

    Hits the search index: type-ahead style queries for people, families,
    events, places, sources, citations, repositories, media and notes. `type`
    is a comma-delimited allowlist of object types; `query` is required. Use
    `manage_<type>` with a get/filter instead when you already know the handle
    or want raw object data.

    Args:
        query: The search string (required).
        type: Comma-delimited object types to include, e.g. "person,family,source".
        page: 1-based result page.
        pagesize: Results per page (default 20).
        sort: Comma-delimited sort keys; "change" or "type", '-' prefix for
            descending (e.g. "-change").
        profile: Comma-delimited profile sections: all,self,age,span,events,
            families,references.
        strip: If true, drop empty-valued keys from hits.
        semantic: If true, use the vector/semantic index instead of full text.
        change: ISO-8601 last-change filter, prefix with '>' or '<'.
        locale: Language code for localized profile output.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": [hits], "total": <match count>}.
    """
    def go():
        return _api().request("/search/", "GET", query={
            k: v for k, v in {
                "query": query,
                "type": type,
                "page": page,
                "pagesize": pagesize,
                "sort": sort,
                "profile": profile,
                "strip": strip,
                "semantic": semantic,
                "change": change,
                "locale": locale,
            }.items() if v is not None
        } or None, instance=instance)

    return _run(go, "search")


@_tool
def merge_objects(obj_type: str, handle1: str, handle2: str, data: dict = None,
                  instance: str = "") -> dict:
    """Merge two Gramps objects of the same type into one. Writes: merge.

    `handle1` (the "phoenix") survives; `handle2` (the "titanic") is absorbed
    and deleted. Supported obj_type values: person, family, event, place,
    source, citation, repository, media, note. Person merges accept
    {"family_merger": bool} in `data`; family merges accept
    {"phoenix_father_handle", "phoenix_mother_handle"}. Requires edit+delete
    permissions upstream. For duplicate handling of other object types, use
    manage_* to probe first, then merge_objects to combine.

    Args:
        obj_type: Object type to merge, e.g. "person" or "family".
        handle1: Handle that survives the merge (phoenix).
        handle2: Handle that is absorbed and deleted (titanic).
        data: Optional merge options dict (person/family specific).
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": {}} on success.
    """
    def go():
        plural, _cls = _MERGE_ROUTES.get(str(obj_type).lower(), (None, None))
        if not plural:
            raise _ApiError(
                f"Unsupported obj_type '{obj_type}'. Expected one of: {', '.join(sorted(_MERGE_ROUTES))}."
            )
        return _api().request(
            f"/{plural}/{handle1}/merge/{handle2}", "POST",
            body=_drop_empty(data) if data else None, instance=instance,
        )

    return _run(go, "merge_objects")


@_tool
def get_timeline(kind: str, handle: str = None, page: int = None,
                 pagesize: int = None, strip: bool = None, discard_empty: bool = None,
                 omit_anchor: bool = None, ratings: bool = None,
                 keys: str = None, skipkeys: str = None, precision: int = None,
                 ancestors: int = None, offspring: int = None,
                 query: dict = None, instance: str = "") -> dict:
    """Chronological event timeline for a person, family, or the whole tree. Read-only.

    `kind=person` -> /people/<handle>/timeline; `kind=family` ->
    /families/<handle>/timeline; `kind=people` and `kind=families` return
    tree-wide timelines (no handle). Events can be grouped into generations
    (`ancestors`/`offspring`), filtered by event class (`event_classes` via
    `query`), and paged (`page`/`pagesize`).

    Args:
        kind: "person", "family", "people" or "families".
        handle: Person/family handle; required for kinds 'person' and 'family'.
        page: 1-based page of the event list.
        pagesize: Events per page.
        strip: If true, drop empty-valued keys from returned objects.
        discard_empty: If true, omit placeholder slot rows.
        omit_anchor: If true, exclude the anchor object's own event row.
        ratings: If true, include per-event relevance ratings.
        keys: Comma-delimited subset of object keys to return.
        skipkeys: Comma-delimited keys to exclude.
        precision: Significant time components (1-3) for age/span strings.
        ancestors: Number of ancestor generations to include (person kind).
        offspring: Number of descendant generations to include (person kind).
        query: Optional dict of extra timeline params (event_classes, events,
            relative_events, relatives, first, last, handles, ...).
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": [timeline rows]}.
    """
    def go():
        q = dict(query or {})
        q.update({k: v for k, v in {
            "page": page, "pagesize": pagesize, "strip": strip,
            "discard_empty": discard_empty, "omit_anchor": omit_anchor,
            "ratings": ratings, "keys": keys, "skipkeys": skipkeys,
            "precision": precision, "ancestors": ancestors, "offspring": offspring,
        }.items() if v is not None})
        if kind == "person":
            if not handle:
                raise _ApiError("`handle` is required when kind='person'.")
            path = f"/people/{handle}/timeline"
        elif kind == "family":
            if not handle:
                raise _ApiError("`handle` is required when kind='family'.")
            path = f"/families/{handle}/timeline"
        elif kind in ("people", "families"):
            path = f"/timelines/{kind}/"
        else:
            raise _ApiError("kind must be one of: person, family, people, families.")
        return _api().request(path, "GET", query=q or None, instance=instance)

    return _run(go, "get_timeline")


@_tool
def get_relation(handle1: str, handle2: str, all: bool = False, depth: int = None,
                 instance: str = "") -> dict:
    """Compute a genealogical relationship between two people. Read-only.

    Without `all`, returns the shortest/most direct relationship (relationship
    string plus distances). With `all=true`, lists every possible relationship,
    including common ancestors per path. Uses /relations/<h1>/<h2> or
    /relations/<h1>/<h2>/all with an optional `depth` cap on generations.

    Args:
        handle1: First person handle.
        handle2: Second person handle.
        all: If true, return all possible relationships (and ancestors).
        depth: Maximum generations to search for a common ancestor (default 15,
            minimum 2).
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": relationship(s)}.
    """
    def go():
        suffix = "/all" if all else ""
        return _api().request(
            f"/relations/{handle1}/{handle2}{suffix}", "GET",
            query={"depth": depth} if depth else None, instance=instance,
        )

    return _run(go, "get_relation")


@_tool
def get_living(handle: str, mode: str = "status",
               average_generation_gap: int = None, max_age_probably_alive: int = None,
               max_sibling_age_difference: int = None, instance: str = "") -> dict:
    """Estimate whether (or until when) a person is alive. Read-only.

    `mode=status` returns {"living": bool} from /living/<handle>;
    `mode=dates` returns probable birth/death date estimates plus an
    explanation from /living/<handle>/dates. Tune the heuristic with the
    three optional integer parameters (upstream defaults: 20 / 110 / 20).

    Args:
        handle: Person handle.
        mode: "status" (default) or "dates".
        average_generation_gap: Average years between generations (>= 1).
        max_age_probably_alive: Max age in years still considered alive (>= 1).
        max_sibling_age_difference: Max sibling age gap tolerated (>= 1).
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": <living verdict or date estimates>}.
    """
    def go():
        q = {k: v for k, v in {
            "average_generation_gap": average_generation_gap,
            "max_age_probably_alive": max_age_probably_alive,
            "max_sibling_age_difference": max_sibling_age_difference,
        }.items() if v is not None}
        if mode not in ("status", "dates"):
            raise _ApiError("mode must be 'status' or 'dates'.")
        suffix = "/dates" if mode == "dates" else ""
        return _api().request(f"/living/{handle}{suffix}", "GET",
                              query=q or None, instance=instance)

    return _run(go, "get_living")


@_tool
def analyze_dna(action: str, handle: str = None, data: str = None,
                raw: bool = None, instance: str = "") -> dict:
    """DNA match analysis and raw match-string parsing. Writes: parse only.

    Actions:
      matches -> GET /people/<handle>/dna/matches; per-match relationship,
                 segments, common-ancestor profiles and citation-linked notes.
      ydna    -> GET /people/<handle>/ydna; Y-DNA haplogroup clade lineage.
      parse   -> POST /parsers/dna-match with `data` = the raw DNA match text
                 (e.g. 23andMe/Ancestry segment blocks); returns parsed segments.
    `matches` accepts `raw=true` to include the raw segment strings. Matches
    are stored as "DNA" associations plus notes; see manage_person/manage_note.

    Args:
        action: "matches", "ydna" or "parse".
        handle: Person handle; required for matches and ydna.
        data: Raw DNA match string; required for parse.
        raw: If true, include raw segment strings in matches output.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": matches, clade or parsed segments}.
    """
    def go():
        api = _api()
        if action == "matches":
            if not handle:
                raise _ApiError("`handle` is required for action 'matches'.")
            return api.request(f"/people/{handle}/dna/matches", "GET",
                               query={"raw": raw} if raw is not None else None,
                               instance=instance)
        if action == "ydna":
            if not handle:
                raise _ApiError("`handle` is required for action 'ydna'.")
            return api.request(f"/people/{handle}/ydna", "GET", instance=instance)
        if action == "parse":
            if not data:
                raise _ApiError("`data` (raw DNA match string) is required for 'parse'.")
            return api.request("/parsers/dna-match", "POST",
                               body={"string": data}, instance=instance)
        raise _ApiError("action must be one of: matches, ydna, parse.")

    return _run(go, "analyze_dna")


# --------------------------------------------------------------------------
# Import / export / report
# --------------------------------------------------------------------------
@_tool
def manage_import(action: str, extension: str = None, file_path: str = None,
                  dry_run: bool = False, instance: str = "") -> dict:
    """List importers or import a family tree file (Gramps XML, GEDCOM...). Writes: file, restore.

    `action=list` returns every available importer (GET /importers/);
    `action=info` describes one importer (GET /importers/<extension>);
    `action=file` uploads `file_path` to /importers/<extension>/file (raw body,
    extension picks the importer) and returns the import counts;
    `action=restore` resets the tree to match an uploaded Gramps backup via
    /importers/<extension>/file/restore (replaces all content; requires batch
    delete permission). Use `dry_run=true` on file/restore to preview counts and
    changes without touching the tree. Extensions: gramps, gpkg, ged, gedcom,
    csv, etc., depending on installed plugins.

    Args:
        action: "list", "info", "file" or "restore".
        extension: Importer extension (e.g. 'gramps' or 'ged'); required for
            info, file, restore.
        file_path: Local path of the file to upload (required for file/restore).
        dry_run: If true, compute counts/summary without importing (file/restore).
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": importer list or import summary}.
    """
    def go():
        api = _api()
        if action == "list":
            return api.request("/importers/", "GET", instance=instance)
        if action == "info":
            if not extension:
                raise _ApiError("`extension` is required for action 'info'.")
            return api.request(f"/importers/{extension}", "GET", instance=instance)
        if action in ("file", "restore"):
            if not extension or not file_path:
                raise _ApiError(f"`extension` and `file_path` are required for '{action}'.")
            with open(file_path, "rb") as fh:
                raw = fh.read()
            suffix = "/file" if action == "file" else "/file/restore"
            return api.request(f"/importers/{extension}{suffix}", "POST",
                               raw_body=raw,
                               content_type="application/octet-stream",
                               query={"dry_run": dry_run} if dry_run else None,
                               instance=instance)
        raise _ApiError("action must be one of: list, info, file, restore.")

    return _run(go, "manage_import")


@_tool
def manage_export(action: str, extension: str = None, options: dict = None,
                  instance: str = "") -> dict:
    """List exporters or produce an export file (GEDCOM, Gramps XML...). Writes: run.

    `action=list` returns every available exporter (GET /exporters/);
    `action=info` describes one exporter (GET /exporters/<extension>);
    `action=run` starts an asynchronous export (POST /exporters/<extension>/file)
    and returns a task reference (poll with manage_transaction or re-call to
    fetch); `action=file` runs a synchronous export (GET /exporters/<extension>/file)
    and returns the file as base64. Exports run on the whole tree unless
    filtered; pass `options` as a dict of query params: compress, living
    (IncludeAll/FullNameOnly/LastNameOnly/ReplaceCompleteName/ExcludeAll),
    private, person, event, note, reference, sequence, handle, gramps_id,
    years_after_death, current_year, locale, include_individuals,
    include_children, include_marriages, include_places, include_media,
    include_witnesses, translate_headers. Extensions: ged, gramps, gw, csv, etc.

    Args:
        action: "list", "info", "run" or "file".
        extension: Exporter extension (e.g. 'ged' or 'gramps'); required for
            info, run, file.
        options: Dict of export option query parameters (see docstring).
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": exporter list, task ref, or base64 file}.
    """
    def go():
        api = _api()
        if action == "list":
            return api.request("/exporters/", "GET", instance=instance)
        if action == "info":
            if not extension:
                raise _ApiError("`extension` is required for action 'info'.")
            return api.request(f"/exporters/{extension}", "GET", instance=instance)
        if action in ("run", "file"):
            if not extension:
                raise _ApiError(f"`extension` is required for action '{action}'.")
            method = "POST" if action == "run" else "GET"
            return api.request(f"/exporters/{extension}/file", method,
                               query=_drop_empty(options) if options else None,
                               instance=instance)
        raise _ApiError("action must be one of: list, info, run, file.")

    return _run(go, "manage_export")


@_tool
def manage_report(action: str, report_id: str = None, options: dict = None,
                  locale: str = None, include_help: bool = None,
                  instance: str = "") -> dict:
    """List, configure or generate Gramps reports (PDF, text, web...). Writes: run.

    `action=list` returns all available reports (GET /reports/);
    `action=info` describes one report and its options (GET /reports/<id>);
    `action=run` generates a report in the background
    (POST /reports/<id>/file?options=<json>) returning a task reference;
    `action=file` generates it synchronously (GET /reports/<id>/file) and
    returns the produced file as base64; `action=result` downloads a
    previously generated file by `filename` (pass via `options` or a separate
    call: GET /reports/<id>/file/processed/<filename>). Report options are a
    JSON dict documented by each report's options_help (see action=info).

    Args:
        action: "list", "info", "run", "file" or "result".
        report_id: Report id (e.g. 'descend_report'); required for info, run,
            file, result.
        options: Dict of report options (JSON-serialized into the options param).
        locale: Language code for report output (default server locale).
        include_help: If true, include the options-help dictionary in list/info.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": reports, task ref, or base64 file}.
    """
    def go():
        api = _api()
        if action == "list":
            return api.request("/reports/", "GET",
                               query={"include_help": include_help} if include_help else None,
                               instance=instance)
        if action == "info":
            if not report_id:
                raise _ApiError("`report_id` is required for action 'info'.")
            return api.request(f"/reports/{report_id}", "GET",
                               query={"include_help": include_help} if include_help else None,
                               instance=instance)
        if action in ("run", "file"):
            if not report_id:
                raise _ApiError(f"`report_id` is required for action '{action}'.")
            q = {}
            if options:
                q["options"] = json.dumps(options)
            if locale:
                q["locale"] = locale
            method = "POST" if action == "run" else "GET"
            return api.request(f"/reports/{report_id}/file", method,
                               query=q or None, instance=instance)
        if action == "result":
            if not report_id:
                raise _ApiError("`report_id` is required for action 'result'.")
            filename = None
            if options and isinstance(options, dict):
                filename = options.get("filename") or options.get("name")
            if not filename:
                raise _ApiError(
                    "action 'result' requires the generated file name; pass it as "
                    "options={'filename': <name>} (see the previous run's response)."
                )
            return api.request(f"/reports/{report_id}/file/processed/{filename}", "GET",
                               instance=instance)
        raise _ApiError("action must be one of: list, info, run, file, result.")

    return _run(go, "manage_report")


# --------------------------------------------------------------------------
# Transaction / user / tree administration
# --------------------------------------------------------------------------
@_tool
def manage_transaction(action: str, payload: dict = None, params: dict = None,
                       transaction_id: int = None, namespace: str = None,
                       handles: list = None, instance: str = "") -> dict:
    """Apply raw DB transactions, undo history, or bulk create/delete. Writes: all actions.

    Low-level database operations that the object endpoints cannot express:
      apply            -> POST /transactions/ replaying `payload` (a raw
                          transaction dict of {add, update, delete} operations).
      undo             -> POST /transactions/?undo=1 applying the inverse of
                          `payload`; pass a recent transaction to revert it.
      history          -> GET /transactions/history/ (list of past transactions).
      history_id       -> GET /transactions/history/<transaction_id>.
      undo_history     -> POST /transactions/history/<transaction_id>/undo.
      create_objects   -> POST /objects/ with `payload` = list of object dicts
                          (validated and added together in one transaction).
      delete_objects   -> POST /objects/delete/?namespaces=<csv> batches an
                          async delete of whole object types (e.g. 'people,notes').
      delete_by_handle -> POST /objects/delete-by-handle/ with `namespace` (e.g.
                          'people') and `handles` (list) to delete specific objects.
    `params` forwards query args for apply/undo: undo, message, force, background.
    Prefer the typed manage_* tools for single-record work; raw apply skips
    cross-reference maintenance and can corrupt a tree if malformed.

    Args:
        action: "apply", "undo", "history", "history_id", "undo_history",
            "create_objects", "delete_objects" or "delete_by_handle".
        payload: Transaction dict (apply/undo) or list of objects (create_objects).
        params: Optional dict for apply/undo (undo, message, force, background).
        transaction_id: History transaction id; required for history_id, undo_history.
        namespace: Object plural namespace (e.g. 'people'); for delete_objects /
            delete_by_handle.
        handles: List of handles to delete; for delete_by_handle.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": transaction result or task reference}.
    """
    def go():
        api = _api()
        if action in ("apply", "undo"):
            if not payload:
                raise _ApiError(f"`payload` is required for action '{action}'.")
            q = dict(params or {})
            if action == "undo":
                q.setdefault("undo", True)
            return api.request("/transactions/", "POST", query=q or None,
                               body=payload, instance=instance)
        if action == "history":
            return api.request("/transactions/history/", "GET", instance=instance)
        if action in ("history_id", "undo_history"):
            if not transaction_id:
                raise _ApiError(f"`transaction_id` is required for action '{action}'.")
            method = "GET" if action == "history_id" else "POST"
            return api.request(f"/transactions/history/{transaction_id}/undo",
                               method, instance=instance)
        if action == "create_objects":
            if not isinstance(payload, list):
                raise _ApiError("`payload` must be a list of object dicts for "
                                "'create_objects'.")
            return api.request("/objects/", "POST", body=payload, instance=instance)
        if action == "delete_objects":
            if not namespace:
                raise _ApiError("`namespace` is required for 'delete_objects'.")
            return api.request("/objects/delete/", "POST",
                               query={"namespaces": namespace}, instance=instance)
        if action == "delete_by_handle":
            if not namespace or not handles:
                raise _ApiError("`namespace` and `handles` are required for "
                                "'delete_by_handle'.")
            return api.request("/objects/delete-by-handle/", "POST",
                               body={"namespace": namespace, "handles": handles},
                               instance=instance)
        raise _ApiError("action must be one of: apply, undo, history, history_id, "
                        "undo_history, create_objects, delete_objects, delete_by_handle.")

    return _run(go, "manage_transaction")


@_tool
def manage_user(action: str, user_name: str = None, data: dict = None,
                instance: str = "") -> dict:
    """Administer Gramps Web users. Writes: create, update, delete, change_password.

    `action=list` lists users (GET /users/); `action=get` returns one user by
    name; `action=create` POSTs `data` (full_name, email, password, role and
    tree required by the API) to /users/; `action=update` PUTs `data` (role,
    email, full_name, name_new, tree) to /users/<user_name>/; `action=delete`
    removes the user; `action=change_password` POSTs with data = {"old_password",
    "new_password"}. Requires owner/admin permissions upstream for most actions.

    Args:
        action: "list", "get", "create", "update", "delete" or "change_password".
        user_name: The user's name; required for get/update/delete/change_password.
        data: Body dict; required for create/update/change_password.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": user list/object or empty}.
    """
    def go():
        api = _api()
        if action == "list":
            return api.request("/users/", "GET", instance=instance)
        if action == "get":
            if not user_name:
                raise _ApiError("`user_name` is required for action 'get'.")
            return api.request(f"/users/{user_name}/", "GET", instance=instance)
        if action == "create":
            if not data:
                raise _ApiError("`data` is required for action 'create'.")
            return api.request("/users/", "POST", body=_drop_empty(data),
                               instance=instance)
        if action in ("update", "delete"):
            if not user_name:
                raise _ApiError(f"`user_name` is required for action '{action}'.")
            method = "PUT" if action == "update" else "DELETE"
            return api.request(f"/users/{user_name}/", method,
                               body=_drop_empty(data) if method == "PUT" and data else None,
                               instance=instance)
        if action == "change_password":
            if not user_name or not data:
                raise _ApiError("`user_name` and `data` are required for 'change_password'.")
            return api.request(f"/users/{user_name}/password/change", "POST",
                               body=_drop_empty(data), instance=instance)
        raise _ApiError("action must be one of: list, get, create, update, delete, "
                        "change_password.")

    return _run(go, "manage_user")


@_tool
def manage_tree(action: str, tree_id: str = None, data: dict = None,
                instance: str = "") -> dict:
    """Inspect or administer Gramps Web family trees. Writes: create, update, disable, enable, repair, migrate, verify, config_set.

    `action=list` lists trees (GET /trees/); `action=get` inspects one tree
    (tree_id '-' means the current tree); `action=create` adds a tree
    (data = {"name": <required>, "quota_media", "quota_people", "min_role_ai"});
    `action=update` renames/rescales a tree; `action=disable`/`action=enable`
    toggle login for a tree; `action=repair` checks/repairs its database;
    `action=migrate` upgrades its schema; `action=verify` runs integrity
    checks; `action=config_get`/`action=config_set` read or write tree
    configuration. Admin-only upstream. Note: this API version has no tree
    delete endpoint (delete trees via the server CLI).

    Args:
        action: "list", "get", "create", "update", "disable", "enable",
            "repair", "migrate", "verify", "config_get" or "config_set".
        tree_id: Tree id; required except for list/create; '-' = current tree.
        data: Body dict for create/update/config_set (create requires 'name').
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": tree details or configuration}.
    """
    def go():
        api = _api()
        if action == "list":
            return api.request("/trees/", "GET", instance=instance)
        if action == "create":
            if not data or not data.get("name"):
                raise _ApiError("`data` with a 'name' is required for action 'create'.")
            return api.request("/trees/", "POST", body=_drop_empty(data), instance=instance)
        if not tree_id:
            raise _ApiError(f"`tree_id` is required for action '{action}'.")
        if action == "get":
            return api.request(f"/trees/{tree_id}", "GET", instance=instance)
        if action == "update":
            return api.request(f"/trees/{tree_id}", "PUT",
                               body=_drop_empty(data) if data else None, instance=instance)
        if action in ("disable", "enable", "repair", "migrate", "verify"):
            route = {"disable": "disable", "enable": "enable", "repair": "repair",
                     "migrate": "migrate", "verify": "verify"}[action]
            return api.request(f"/trees/{tree_id}/{route}", "POST", instance=instance)
        if action == "config_get":
            return api.request(f"/trees/{tree_id}/config", "GET", instance=instance)
        if action == "config_set":
            return api.request(f"/trees/{tree_id}/config", "PUT",
                               body=_drop_empty(data) if data else None, instance=instance)
        raise _ApiError("action must be one of: list, get, create, update, disable, "
                        "enable, repair, migrate, verify, config_get, config_set.")

    return _run(go, "manage_tree")


# --------------------------------------------------------------------------
# Bookmarks / types / server info
# --------------------------------------------------------------------------
@_tool
def manage_bookmark(namespace: str, action: str = "list", handle: str = None,
                    instance: str = "") -> dict:
    """Read or edit bookmarks per object namespace. Writes: add, remove.

    Bookmarks are per-user, per-type handle shortcuts. `namespace` is one of:
    citations, events, families, media, notes, people, places, repositories,
    sources. `action=list_all` returns every namespace's bookmarks
    (GET /bookmarks/); `action=list` returns one namespace (GET /bookmarks/<ns>);
    `action=add` bookmarks a handle (PUT /bookmarks/<ns>/<handle>, idempotent);
    `action=remove` unbookmarks it (DELETE). Adding validates that the object
    exists.

    Args:
        namespace: Bookmark namespace (one of the nine object plurals).
        action: "list_all", "list", "add" or "remove" (default "list").
        handle: Object handle to bookmark/unbookmark; required for add/remove.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": bookmark list or empty}.
    """
    def go():
        api = _api()
        if namespace.lower() not in _BOOKMARK_NAMESPACES:
            raise _ApiError(
                f"Invalid namespace '{namespace}'. Expected one of: {', '.join(_BOOKMARK_NAMESPACES)}."
            )
        if action == "list_all":
            return api.request("/bookmarks/", "GET", instance=instance)
        if action == "list":
            return api.request(f"/bookmarks/{namespace}", "GET", instance=instance)
        if action == "add":
            if not handle:
                raise _ApiError("`handle` is required for action 'add'.")
            return api.request(f"/bookmarks/{namespace}/{handle}", "PUT",
                               instance=instance)
        if action == "remove":
            if not handle:
                raise _ApiError("`handle` is required for action 'remove'.")
            return api.request(f"/bookmarks/{namespace}/{handle}", "DELETE",
                               instance=instance)
        raise _ApiError("action must be one of: list_all, list, add, remove.")

    return _run(go, "manage_bookmark")


@_tool
def manage_type(action: str = "all", datatype: str = None, locale: bool = False,
                instance: str = "") -> dict:
    """List Gramps type vocabularies (custom + default) for all object types. Read-only.

    Enumerates the controlled vocabularies used across the schema, e.g. event
    types, name types, place types, child reference types, gender types.
    `action=all` merges default and custom types (GET /types/); `action=defaults`
    lists every default vocabulary; `action=default` returns one vocabulary
    (e.g. 'event_types'); `action=default_map` returns its machine-readable
    mapping (standard key -> localized string); `action=customs` lists every
    custom vocabulary; `action=custom` returns one. Datatypes include:
    event_types, event_role_types, name_types, name_origin_types, place_types,
    note_types, repository_types, source_attribute_types, source_media_types,
    url_types, attribute_types, family_relation_types, child_reference_types,
    gender_types (+ person/family/media/event attribute_types on custom).
    Values are the strings Gramps objects use in their `type` fields.

    Args:
        action: "all", "defaults", "default", "default_map", "customs" or "custom".
        datatype: Vocabulary name (e.g. 'event_types'); required for default,
            default_map, custom.
        locale: If true, translate default type names to the server locale.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": vocabulary dict or list}.
    """
    def go():
        api = _api()
        route = {
            "all": "/types/",
            "defaults": "/types/default/",
            "customs": "/types/custom/",
        }.get(action)
        if route:
            return api.request(route, "GET",
                               query={"locale": locale} if locale and action == "all" else None,
                               instance=instance)
        if action in ("default", "default_map", "custom"):
            if not datatype:
                raise _ApiError(f"`datatype` is required for action '{action}'.")
            if action == "default_map":
                path = f"/types/default/{datatype}/map"
            else:
                path = f"/types/{action}/{datatype}"
            return api.request(path, "GET",
                               query={"locale": locale} if locale and action == "default" else None,
                               instance=instance)
        raise _ApiError("action must be one of: all, defaults, default, default_map, "
                        "customs, custom.")

    return _run(go, "manage_type")


@_tool
def get_server_info(surnames: bool = False, instance: str = "") -> dict:
    """Read Gramps Web server, database, locale and object-count metadata. Read-only.

    Wraps GET /metadata/: database id/name/type, Gramps + Gramps Web API + QL
    versions, locale, per-type object counts, tree researcher info, search
    index details, and server capabilities (multi-tree, task queue, OCR,
    semantic search, chat, face detection, thumbnails). When `surnames` is
    true, the response additionally lists every surname in the database.

    Args:
        surnames: If true, include the full list of surnames in the database.
        instance: Gramps Web base URL from get_instances; default = first.

    Returns:
        dict: {"status", "url", "data": metadata object}.
    """
    def go():
        return _api().request("/metadata/", "GET",
                              query={"surnames": surnames} if surnames else None,
                              instance=instance)

    return _run(go, "get_server_info")


# --------------------------------------------------------------------------
def main():
    if server is None:
        raise SystemExit("The 'mcp' python package is not installed.")
    if _MCP_PORT_ERROR:
        sys.stderr.write(f"{_MCP_PORT_ERROR}\n")
        raise SystemExit(1)
    transport = MCP_TRANSPORT.strip().lower()
    allowed = {"stdio", "sse", "streamable-http"}
    if transport not in allowed:
        sys.stderr.write(
            f"Error: invalid MCP_TRANSPORT '{MCP_TRANSPORT}'. Expected one of: {', '.join(sorted(allowed))}.\n"
        )
        raise SystemExit(1)
    server.run(transport=transport)