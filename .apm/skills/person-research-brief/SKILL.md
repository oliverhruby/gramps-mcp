---
name: person-research-brief
description: Use when the user asks to research, summarize, narrate or update one person's life story or family history in a Gramps tree - e.g. "what do we know about this ancestor", "build a timeline for X", "fill the gaps in this person's profile", "how are these two related", or "is this person still alive". Reads the tree, assembles evidence and a chronology, then (only when asked) writes updates back. Requires the gramps-mcp MCP server (gramps-mcp-full) with GRAMPS_MCP_USERNAME and GRAMPS_MCP_PASSWORD set.
metadata:
  mcp-server: gramps
  mcp-package: gramps-mcp-full
---

# Person research brief

Research one person in a Gramps Web tree and turn scattered records into a
coherent life story: who they are, what happened when, who they are related
to, which claims are sourced, and what is still missing. Reading is free;
writes go to a real tree, so separate the two phases clearly.

## Prerequisites

- The `gramps-mcp-full` MCP server must be connected. Verify with `ping`,
  then `get_instances` to see the configured Gramps Web base URL(s).
- Credentials `GRAMPS_MCP_USERNAME` / `GRAMPS_MCP_PASSWORD` must be in the
  server's environment; login is lazy, so a missing/expired credential shows
  up as an auth error on the first data call, not at startup.
- Several instances configured? Pass `instance="<base URL from get_instances>"`
  on every tool call to pick the right tree; omit it to use the first.
- If tools come back with `isError` saying writes are rejected, the server
  runs with `GRAMPS_MCP_READONLY=1` - do the read-only brief and tell the
  user writes are disabled.

## Workflow

1. **Confirm connectivity.** `ping` then `get_instances`. Stop and report if
   either fails - do not invent tree data.

2. **Locate the person.** Search first, never guess handles:
   - `search(query="Jane Doe", type="person", strip=true)` - `strip` roughly
     halves the cost per hit.
   - Ambiguous matches? Show the candidate list (name, birth/death year) and
     ask which one. Multiple hits for the same name are often duplicates -
     note that for step 6 rather than merging on your own.
   - Once you have the handle, `manage_person(action="get", handle="P0001",
     query={"profile": "all"})` for the full record.

3. **Build the chronology.**
   - `get_timeline(kind="person", handle="P0001")` - ordered life events.
   - `manage_family(action="get", ...)` via the person's `family_list` for
     parents, spouse(s) and children.
   - `get_relation(handle1=..., handle2=...)` when the question is
     "how are these two related" (add `all=true` for every path).
   - Tree-wide context: `get_timeline(kind="people")` is a big payload -
     prefer the per-person timeline.

4. **Apply the privacy gate before writing anything down.**
   `get_living(handle="P0001", mode="status")` (and `mode="dates"` for
   probable birth/death estimates). If the person is likely living, keep
   precise dates, places and living relatives out of any narrative you hand
   to the user, and say why. Gramps Web itself enforces privacy filters on
   export; your prose should not defeat them.

5. **Assemble the evidence.**
   - `search(query=..., type="source,citation,note")` for supporting records.
   - `manage_source` / `manage_citation` / `manage_note` (`action="get"`) to
     read what is already documented.
   - `manage_media(action="get")` to list photos/documents attached; OCR and
     thumbnails need optional Gramps Web services - degrade quietly if absent.
   - DNA questions: `analyze_dna(action="matches", handle=...)` (also `ydna`,
     or `parse` with a raw match string).
   - List reads cheaply: `manage_person(action="get",
     query={"keys": "handle,name"})` instead of an unfiltered whole-tree list.

6. **Write back only on request, in this order of preference:**
   - Single field edits: fetch the object, modify it, PUT it back with
     `manage_person(action="update", handle=..., data=...)`. Never send a
     partial object - the PUT replaces the record.
   - New facts as events/notes: `manage_event(action="create")` then attach
     it by updating the person's `event_ref_list`; attach prose with
     `manage_note(action="create")` + `note_list`.
   - Duplicates found: `merge_objects(obj_type="person", handle1=<phoenix>,
     handle2=<titanic>)`. `handle1` survives; there is no undo. Confirm with
     the user first and consider `manage_export(action="run",
     extension="gedcom")` as a backup snapshot.
   - Bulk changes: `manage_transaction(action="create_objects", payload=[...])`
     or `action="apply"`; every applied transaction is undoable afterwards via
     `action="undo_history"` with the returned `transaction_id`.

7. **Deliver.** Write the brief as structured markdown: identity, chronology
   (year - event - place - source), family, evidence and gaps, then
   recommended next steps. Optionally produce a durable artifact with
   `manage_report(action="run", report_id=...)` (list ids with
   `action="list"`) or `manage_export(action="run", extension="gedcom" |
     "gramps-xml" | "csv", options={"privacy": true})`.

## Edge cases

- **Names must be nested.** `manage_person(action="create")` accepts a flat
  `{"first_name": ..., "surname": ...}` with HTTP 201 and silently saves an
  anonymous person. Always build
  `{"primary_name": {"first_name": "...", "surname_list": [{"surname": "...", "primary": true}]}}`.
- **There is no `list` action.** `action="get"` without `handle` lists
  (paginated via `query={"page": n, "pagesize": n}`); `total` in search
  results is the real match count.
- **`create` does not validate payloads.** If a write looks accepted but the
  read-back is wrong (empty name, missing refs), re-read with
  `action="get"` and fix with `action="update"`.
- **Read-only mode** rejects every write action with a clear error - report
  it, do not retry.
- **Errors arrive as `{"isError": true, ...}`** tool results, not exceptions.
  Surface the message; retrying the same call rarely helps. Auth errors mean
  credentials; 404 means the handle is wrong; 422 means a bad query param.
- **Cost control.** Search/list responses are ~0.7-2 KB per record; always
  pass `keys`/`strip`/`pagesize` on bulk reads, and avoid `profile=all`
  except on the one person you are briefing.

## Example

> "What do we know about Anna Novak, and are we missing anything?"

```
ping
get_instances
search(query="Anna Novak", type="person", strip=true)
manage_person(action="get", handle="P0042", query={"profile": "all"})
get_timeline(kind="person", handle="P0042")
get_living(handle="P0042", mode="status")
search(query="Novak", type="source,citation,note", strip=true)
manage_citation(action="get", handle="C0007")
```

Then answer with the brief: identity, dated chronology with sources, family
links, what is undocumented - and offer to create the missing events/notes
as a follow-up write step.
