"""Seed a Gramps Web API backend with synthetic data for the integration suite.

This is a CI-purpose script: it creates a handful of clearly-fictitious objects
(Person/Event/Family/Place/Source/Citation/Note/Repository/Tag/media) via the
same REST endpoints the MCP server wraps, so the live e2e tests have real data
to read and the write-tool probes can assert list results with a `total > 0`.

PRIVACY: all identities below are placeholders; nothing real is ever written.
Compose the JSON exactly per the upstream `gramps-web-api` object schemas
(tests/test_endpoints/test_post.py) - do not invent new shapes.

Usage:
    python tests/e2e/seed_gramps_data.py --url http://localhost:5000 \
        --user admin --password secret
"""

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

TREE = "cyclic"  # one family across 2 generations


def make_handle():
    return str(uuid.uuid4())


def post_json(base: str, path: str, token: str, obj: dict, timeout: float = 30.0):
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "gramps-mcp-seed",
    }
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(obj).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, {"message": e.reason, "body": body}


def post_file(base: str, path: str, token: str, raw: bytes, content_type: str):
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
        "User-Agent": "gramps-mcp-seed",
    }
    req = urllib.request.Request(
        base.rstrip("/") + path, data=raw, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, {"message": e.reason, "body": body}


def get_token(base: str, user: str, password: str):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    body = json.dumps({"username": user, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + "/api/token/", data=body, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in {data!r}")
    return token


def verify(base: str, path: str, token: str):
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "gramps-mcp-seed",
    }
    req = urllib.request.Request(
        url=base.rstrip("/") + urllib.parse.quote(path),
        headers=headers,
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.headers.get("X-Total-Count"), json.loads(resp.read().decode("utf-8"))


TONY, IDA = make_handle(), make_handle()
EMMETT, ADA = make_handle(), make_handle()
SPOUSE = make_handle()
BIRTH_EMMETT = make_handle()
FAM_1, FAM_2 = make_handle(), make_handle()
PLACE, SOURCE, CIT, NOTE, REPO, TAG = (
    make_handle(),
    make_handle(),
    make_handle(),
    make_handle(),
    make_handle(),
    make_handle(),
)

PERSON_FATHER = {
    "_class": "Person",
    "handle": TONY,
    "gramps_id": "I001",
    "primary_name": {
        "_class": "Name",
        "surname_list": [{"_class": "Surname", "surname": "Smith"}],
        "first_name": "Tony",
    },
    "gender": 1,
}
PERSON_MOTHER = {
    "_class": "Person",
    "handle": IDA,
    "gramps_id": "I002",
    "primary_name": {
        "_class": "Name",
        "surname_list": [{"_class": "Surname", "surname": "Jones"}],
        "first_name": "Ida",
    },
    "gender": 0,
}
PERSON_CHILD = {
    "_class": "Person",
    "handle": EMMETT,
    "gramps_id": "I003",
    "primary_name": {
        "_class": "Name",
        "surname_list": [{"_class": "Surname", "surname": "Smith"}],
        "first_name": "Emmett",
    },
    "gender": 1,
}
PERSON_GRANDCHILD = {
    "_class": "Person",
    "handle": ADA,
    "gramps_id": "I004",
    "primary_name": {
        "_class": "Name",
        "surname_list": [{"_class": "Surname", "surname": "Smith"}],
        "first_name": "Ada",
    },
    "gender": 0,
}
PERSON_SPOUSE = {
    "_class": "Person",
    "handle": SPOUSE,
    "gramps_id": "I005",
    "primary_name": {
        "_class": "Name",
        "surname_list": [{"_class": "Surname", "surname": "Brown"}],
        "first_name": "Bessie",
    },
    "gender": 0,
}

EVENT_BIRTH = {
    "_class": "Event",
    "handle": BIRTH_EMMETT,
    "gramps_id": "E001",
    "description": "Birth of Emmett",
    "type": {"_class": "EventType", "string": "Birth"},
    "date": {"_class": "Date", "dateval": [2, 10, 1945, False]},
    "place_handle": PLACE,
}

FAMILY_1 = {
    "_class": "Family",
    "handle": FAM_1,
    "gramps_id": "F001",
    "father_handle": TONY,
    "mother_handle": IDA,
    "child_ref_list": [{"_class": "ChildRef", "ref": EMMETT}],
}
FAMILY_2 = {
    "_class": "Family",
    "handle": FAM_2,
    "gramps_id": "F002",
    "father_handle": EMMETT,
    "mother_handle": SPOUSE,
    "child_ref_list": [{"_class": "ChildRef", "ref": ADA}],
}

PLACE_OBJ = {
    "_class": "Place",
    "handle": PLACE,
    "gramps_id": "P001",
    "name": {"_class": "PlaceName", "value": "London"},
}
SOURCE_OBJ = {
    "_class": "Source",
    "handle": SOURCE,
    "gramps_id": "S001",
    "title": "Census 1950",
    "author": "Test Author",
    "reporef_list": [{"_class": "RepoRef", "ref": REPO}],
}
CITATION_OBJ = {
    "_class": "Citation",
    "handle": CIT,
    "gramps_id": "C001",
    "page": "p. 1",
    "source_handle": SOURCE,
}
NOTE_OBJ = {
    "_class": "Note",
    "handle": NOTE,
    "gramps_id": "N001",
    "text": {"_class": "StyledText", "string": "Family note from CI seed data."},
    "type": {"_class": "NoteType", "string": "General"},
}
REPOSITORY_OBJ = {
    "_class": "Repository",
    "handle": REPO,
    "gramps_id": "R001",
    "name": "National Archives",
    "type": {"_class": "RepositoryType", "string": "Archive"},
}
TAG_OBJ = {"_class": "Tag", "handle": TAG, "name": "CI-Seed", "color": "#111111"}

# 1x1 transparent PNG (valid minimal image for the media upload endpoint).
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Gramps Web base URL, e.g. http://localhost:5000")
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    errors = []
    created = {endpoint: 0 for endpoint in (
        "people", "events", "families", "places", "sources",
        "citations", "notes", "media", "repositories", "tags")}

    try:
        token = get_token(args.url, args.user, args.password)
        print(f"login ok (user: {args.user})")
    except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
        print(f"FAIL: login: {exc}")
        return 1

    postcases = (
        ("people", PERSON_FATHER),
        ("people", PERSON_MOTHER),
        ("people", PERSON_CHILD),
        ("people", PERSON_GRANDCHILD),
        ("people", PERSON_SPOUSE),
        ("repositories", REPOSITORY_OBJ),
        ("sources", SOURCE_OBJ),
        ("citations", CITATION_OBJ),
        ("events", EVENT_BIRTH),
        ("families", FAMILY_1),
        ("families", FAMILY_2),
        ("places", PLACE_OBJ),
        ("notes", NOTE_OBJ),
        ("tags", TAG_OBJ),
    )
    for endpoint, obj in postcases:
        status, payload = post_json(args.url, f"/api/{endpoint}/", token, obj)
        ok = status in (200, 201)
        if ok:
            created[endpoint] += 1
        else:
            errors.append(f"{endpoint} -> HTTP {status}: {payload}")
            print(f"  post /api/{endpoint}/ -> HTTP {status} {payload}")
        print(f"  post /api/{endpoint}/ -> HTTP {status}")

    # media: raw file upload reuses the same add-object transaction.
    status, payload = post_file(
        args.url, "/api/media/", token, PNG_BYTES, "image/png"
    )
    if status in (200, 201):
        created["media"] += 1
        print(f"  post /api/media/ -> HTTP {status}")
    else:
        errors.append(f"media -> HTTP {status}: {payload}")
        print(f"  post /api/media/ -> HTTP {status} {payload}")

    # read-back proof: total counts per family-tree object type.
    for endpoint in ("people", "events", "families", "places", "sources",
                     "citations", "notes", "media", "repositories", "tags"):
        try:
            status, total, _payload = verify(
                args.url, f"/api/{endpoint}/?pagesize=1", token
            )
            print(f"  read /api/{endpoint}/ -> HTTP {status} total={total}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"read {endpoint}: {exc}")

    if errors:
        print(f"FAIL: {len(errors)} object(s) not created/readable")
        return 1
    print("seed complete:", json.dumps(created, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())