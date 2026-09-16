#!/usr/bin/env python3
"""Weekly Glama TDQS quality watchdog (hybrid source).

Checks the live Glama record for this project's server from two sources:

1. HTML page  (always)   — per-tool TDQS grade letters (A-F) and the tool
   inventory (for stale-scan / drift detection against GLAMA_EXPECTED_TOOLS).
2. Directory API (when GLAMA_API_KEY is set) — the server-level
   ``qualityScore`` (0-5). Worth knowing: Glama's directory API currently
   returns *empty* ``tools`` arrays, so per-tool grades only exist on the
   page; the API is used solely for the overall score.

A violation from any available source opens/keeps the watchdog issue:
a tool graded below ``GLAMA_ALLOWED``, the tool inventory not matching
``GLAMA_EXPECTED_TOOLS`` (typically a stale scan), or an overall score
below ``GLAMA_MIN_SCORE``.

Uses only the Python standard library. Outputs under ``reports/`` (gitignored):
  glama-quality-status.txt   CLEAN | VIOLATIONS | UNPARSEABLE
  glama-quality-title.txt    issue title (VIOLATIONS only)
  glama-quality-issue.md     issue body (VIOLATIONS only)
  glama-quality-summary.json always (debug/diagnostics)

Exit code is 0 on a successful check; 2 on an UNPARSEABLE result
(workflow turns red, no issue is touched); 1 on a programming/CLI error.

Env vars:
  GLAMA_SERVER_URL      page to check (default: this project's Glama page)
  GLAMA_API_URL         directory API base (default: https://glama.ai/api/mcp)
  GLAMA_API_KEY         optional Bearer key for the directory API
  GLAMA_ALLOWED         comma-separated acceptable tool grades (default: A)
  GLAMA_MIN_SCORE       minimum overall qualityScore, 0-5 (default: 4.0)
  GLAMA_EXPECTED_TOOLS  comma-separated tool names the page inventory must match

Offline testing:
  python scripts/check_glama_quality.py --path page.html
  python scripts/check_glama_quality.py --path page.html --api-path server.json
"""

import argparse
import datetime as _dt
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://glama.ai/mcp/servers/oliverhruby/gramps-mcp"
DEFAULT_API = "https://glama.ai/api/mcp"
DEFAULT_NAMESPACE = "oliverhruby"
DEFAULT_SLUG = "gramps-mcp"
MIN_TOOLS = 10

TOOL_RE = re.compile(
    r'/tools/([a-z_]+)"[^>]*>[^<]*</a><span class="[^"]*"[^>]*>([A-F])</span>'
)


def http_get(url: str, key: str | None = None, timeout: int = 60) -> str:
    headers = {"User-Agent": "glama-quality-watchdog/0.5.0 (github workflow)"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_tools(html: str) -> list[tuple[str, str]]:
    """Return (tool_name, grade_letter) pairs for every tool with a badge."""
    return [(name, grade) for name, grade in TOOL_RE.findall(html)]


def build_report(out_dir: pathlib.Path, results: dict, url: str) -> None:
    today = _dt.date.today().isoformat()
    reasons: list[str] = []
    sections: list[str] = []

    bad = results["letters_below"]
    if bad:
        reasons.append(f"{len(bad)} tool(s) below grade {results['allowed']}")
        rows = "\n".join(
            f"| `{name}` | {grade} | [details]({url}/tools/{name}) |"
            for name, grade in sorted(bad)
        )
        sections.append(
            "## Tools below grade\n\n"
            f"| Tool | Grade | TDQS details |\n|---|---|---|\n{rows}\n"
        )

    drift = results.get("inventory_drift")
    if drift and (drift["missing"] or drift["extra"]):
        if drift["missing"]:
            reasons.append(
                f"inventory missing {len(drift['missing'])} (likely a stale scan)"
            )
        if drift["extra"]:
            reasons.append(f"inventory has {len(drift['extra'])} unexpected")
        parts = []
        if drift["missing"]:
            parts.append("**Missing** (served by Glama, expected in our server): "
                         + ", ".join(f"`{n}`" for n in sorted(drift["missing"])))
        if drift["extra"]:
            parts.append("**Unexpected** (served by Glama, not in our server): "
                         + ", ".join(f"`{n}`" for n in sorted(drift["extra"])))
        sections.append("## Tool inventory drift\n\n" + "\n\n".join(parts) + "\n")

    if results.get("score_below"):
        score = results["score"]
        reasons.append(f"overall score {score} below {results['min_score']}")
        sections.append(
            "## Overall quality score\n\n"
            f"Glama's overall **qualityScore** is **{score}/5** — below the "
            f"configured minimum of **{results['min_score']}**.\n"
        )

    notes = results.get("notes", [])
    if notes:
        sections.append("## Checks that did not fully run\n\n"
                        + "\n".join(f"- {n}" for n in notes) + "\n")

    title = f"Glama QoS: {'; '.join(reasons)} ({today})"
    if len(title) > 240:
        title = title[:237] + "..."
    body_parts = [
        f"## Glama quality watchdog — {today}\n\n",
        f"Weekly check of [{url}]({url}) found **{len(reasons)} issue group(s)**.\n\n"
        "Inputs: per-tool TDQS letters + inventory from the server page; overall "
        "`qualityScore` from the directory API when a key is configured.\n\n",
    ]
    body_parts.extend(sections)
    body_parts.append(
        "## How to fix\n\n"
        "TDQS grades come almost entirely from the **tool description and the "
        "JSON-schema parameter descriptions** surfaced in `tools/list` (see the "
        "[methodology](https://glama.ai/mcp/methodology) and "
        "[TDQS](https://tdqs.dev)). Improve the offending tool's docstring in "
        "`src/gramps_mcp/__init__.py` (behavior/side-effects in the first "
        "sentences, a Google-style `Args:` block, and cross-references to "
        "sibling tools), then tag a new release so Glama rescans. The next "
        "weekly run auto-closes this issue once everything is back to green.\n\n"
        "Thresholds are configurable in `.github/workflows/glama-quality.yml`: "
        "`GLAMA_ALLOWED`, `GLAMA_MIN_SCORE`, `GLAMA_EXPECTED_TOOLS`.\n"
    )
    (out_dir / "glama-quality-title.txt").write_text(title, encoding="utf-8")
    (out_dir / "glama-quality-issue.md").write_text("".join(body_parts), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", help="read local HTML instead of fetching the page")
    parser.add_argument("--api-path", help="read a saved API JSON response instead of calling the API")
    parser.add_argument("--url", default=os.environ.get("GLAMA_SERVER_URL", DEFAULT_URL))
    args, _ = parser.parse_known_args()

    out_dir = pathlib.Path("reports")
    out_dir.mkdir(exist_ok=True)

    api_key = os.environ.get("GLAMA_API_KEY", "").strip()
    api_url = os.environ.get("GLAMA_API_URL", DEFAULT_API)
    allowed = {g.strip().upper() for g in os.environ.get("GLAMA_ALLOWED", "A").split(",") if g.strip()}
    try:
        min_score = float(os.environ.get("GLAMA_MIN_SCORE", "4.0"))
    except ValueError:
        min_score = 4.0
    expected_raw = os.environ.get("GLAMA_EXPECTED_TOOLS", "")
    expected = {t.strip() for t in expected_raw.split(",") if t.strip()}

    results: dict = {"allowed": sorted(allowed), "min_score": min_score, "notes": []}

    try:
        html = pathlib.Path(args.path).read_text(encoding="utf-8") if args.path else http_get(args.url)
    except Exception as exc:
        print(f"ERROR: could not load Glama page: {exc}")
        results["notes"].append(f"page fetch failed: {exc}")
        html = ""

    tools = parse_tools(html) if html else []
    if tools:
        results["tools"] = tools
        results["letters_total"] = len(tools)
        results["letters_below"] = [(n, g) for n, g in tools if g not in allowed]
        served_names = {n for n, _ in tools}
        if expected:
            results["inventory_drift"] = {
                "missing": sorted(expected - served_names),
                "extra": sorted(served_names - expected),
            }
        else:
            results["notes"].append("GLAMA_EXPECTED_TOOLS unset — inventory drift not checked")
    else:
        results["letters_below"] = []

    if api_key or args.api_path:
        api_endpoint = f"{api_url}/v1/servers/{DEFAULT_NAMESPACE}/{DEFAULT_SLUG}"
        try:
            if args.api_path:
                payload = json.loads(pathlib.Path(args.api_path).read_text(encoding="utf-8"))
            else:
                payload = json.loads(http_get(api_endpoint, key=api_key))
            results["api_endpoint"] = api_endpoint
            score = payload.get("qualityScore")
            results["score"] = score
            if score is None:
                results["notes"].append("API qualityScore is null — scoring not complete yet")
            elif score < min_score:
                results["score_below"] = True
        except urllib.error.HTTPError as exc:
            results["notes"].append(
                f"API check skipped: HTTP {exc.code} on /v1/servers/"
                f"{DEFAULT_NAMESPACE}/{DEFAULT_SLUG} (missing/invalid GLAMA_API_KEY?)"
            )
        except Exception as exc:
            results["notes"].append(f"API check skipped: {exc}")
    else:
        results["notes"].append(
            "GLAMA_API_KEY not set — overall qualityScore check skipped "
            "(per-tool letters are still checked from the page)"
        )

    if not tools:
        (out_dir / "glama-quality-status.txt").write_text("UNPARSEABLE", encoding="utf-8")
        (out_dir / "glama-quality-summary.json").write_text(
            json.dumps({"check_date": _dt.datetime.utcnow().isoformat() + "Z",
                        "url": args.url, "notes": results["notes"]}, indent=2),
            encoding="utf-8",
        )
        print("UNPARSEABLE: the page returned no tool badges")
        return 2

    violations = bool(results["letters_below"]) or bool(results.get("score_below")) or bool(
        (results.get("inventory_drift") or {}).get("missing")
    ) or bool((results.get("inventory_drift") or {}).get("extra"))

    summary = {
        "check_date": _dt.datetime.utcnow().isoformat() + "Z",
        "url": args.url,
        "api_key_set": bool(api_key),
        "allowed_grades": sorted(allowed),
        "min_score": min_score,
        "tools_parsed": len(tools),
        "tools_below_grade": [n for n, _ in results["letters_below"]],
        "quality_score": results.get("score"),
        "score_below": results.get("score_below", False),
        "inventory_drift": results.get("inventory_drift"),
        "notes": results["notes"],
    }
    (out_dir / "glama-quality-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(f"Allowed grades: {sorted(allowed)} | min score: {min_score}")
    for name, grade in sorted(tools):
        marker = "OK" if grade in allowed else "BELOW"
        print(f"  [{marker:5}] {name}: {grade}")
    if "score" in results:
        print(f"API qualityScore: {results.get('score')} "
              f"(below {min_score}: {results.get('score_below', False)})")
    drift = results.get("inventory_drift")
    if drift:
        print(f"Inventory drift: missing={len(drift['missing'])} extra={len(drift['extra'])}")
    for note in results["notes"]:
        print(f"  note: {note}")

    if violations:
        build_report(out_dir, results, args.url)
        (out_dir / "glama-quality-status.txt").write_text("VIOLATIONS", encoding="utf-8")
        print("VIOLATIONS detected")
    else:
        (out_dir / "glama-quality-status.txt").write_text("CLEAN", encoding="utf-8")
        for f in ("glama-quality-title.txt", "glama-quality-issue.md"):
            (out_dir / f).unlink(missing_ok=True)
        print("CLEAN: all checks within configured thresholds")
    return 0


if __name__ == "__main__":
    sys.exit(main())