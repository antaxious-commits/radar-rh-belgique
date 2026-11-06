"""API mode: let Claude research the week via the Messages API and write briefing.json.

Uses the server-side web_search / web_fetch tools, CLAUDE.md as the system
prompt, and validates the returned JSON against radar/schema.json.
Needs ANTHROPIC_API_KEY in the environment (or a GitHub secret in CI).

Usage:
    python -m radar.research_api                 # preceding completed Mon-Sun week
    python -m radar.research_api --start 2026-11-02
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import anthropic

from radar.weekly import ROOT, briefing_dir, preceding_week, parse_start

MODEL = "claude-opus-5-5"
MAX_CONTINUATIONS = 12   # pause_turn resumes (server tool loop hits its iteration cap)
MAX_REPAIRS = 2          # extra turns to fix schema errors

SCHEMA = json.loads((ROOT / "radar" / "schema.json").read_text(encoding="utf-8"))


def system_prompt(schema: dict | None = None) -> str:
    schema = schema or SCHEMA
    rules = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    return (
        rules
        + "\n\n## API mode output contract\n"
        "You are running unattended via the API. You cannot run scripts or write files. "
        "Do all research with the web_search and web_fetch tools, then reply with ONE JSON object "
        "that validates against the JSON Schema below, inside a single ```json fenced block, and nothing after it. "
        "Do not set \"example\". Source ids are integers starting at 1, numbered in order of first use. "
        "Every source url must be a page you actually opened or found in search results this run.\n\n"
        "JSON Schema:\n```json\n" + json.dumps(SCHEMA, indent=1) + "\n```"
    )


def user_prompt(start: str, end: str) -> str:
    return (
        f"Produce this week's Radar RH Belgique briefing (Belgium only, all text in French) for the window "
        f"{start} (Monday) to {end} (Sunday), timezone Europe/Brussels. Follow every rule in the system prompt: "
        f"payroll first, at least 10 searches in French and Dutch (including the retail CP 311/312/201 and "
        f"Brussels checks listed in the reader profile), 6-12 verified items, a 90-day Belgian deadline "
        f"radar counted from {end}, Top 3, RED/AMBER/GREEN actions with proposed owners, and the source register. "
        f"Return only the JSON object as instructed."
    )


def extract_json(text: str) -> dict:
    m = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    raw = m[-1] if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def schema_errors(obj: dict, schema: dict | None = None) -> list[str]:
    import jsonschema

    v = jsonschema.Draft202012Validator(schema or SCHEMA)
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in v.iter_errors(obj)]


def call(client: anthropic.Anthropic, messages: list, schema: dict | None = None) -> "anthropic.types.beta.BetaMessage":
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=system_prompt(schema),
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        tools=[
            {"type": "web_search_20260209", "name": "web_search", "max_uses": 80},
            {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 40},
        ],
        messages=messages,
    ) as stream:
        return stream.get_final_message()


def run_turn(client, messages: list, schema: dict | None = None) -> str:
    """Run one user turn to completion, resuming pause_turn. Returns final text."""
    for _ in range(MAX_CONTINUATIONS + 1):
        resp = call(client, messages, schema)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "pause_turn":
            continue  # server tool loop paused; resend as-is to resume
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model declined: {resp.stop_details}")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("hit max_tokens before finishing the JSON")
        return "".join(b.text for b in resp.content if b.type == "text")
    raise RuntimeError("too many pause_turn continuations")


def research(start: str, end: str) -> dict:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    messages: list = [{"role": "user", "content": user_prompt(start, end)}]
    text = run_turn(client, messages)
    for attempt in range(MAX_REPAIRS + 1):
        try:
            obj = extract_json(text)
            errs = schema_errors(obj)
        except (json.JSONDecodeError, ValueError) as e:
            obj, errs = None, [f"not valid JSON: {e}"]
        if obj is not None:
            if obj.get("window", {}).get("start") != start or obj.get("window", {}).get("end") != end:
                errs.append(f"window must be {start} to {end}")
        if not errs:
            obj.pop("example", None)
            return obj
        if attempt == MAX_REPAIRS:
            raise RuntimeError("briefing JSON still invalid:\n  " + "\n  ".join(errs[:30]))
        messages.append({"role": "user", "content": (
            "The JSON did not validate. Fix these errors and return the complete corrected JSON object "
            "in one ```json block (no other text). Do not invent sources to fill gaps.\n- " + "\n- ".join(errs[:30])
        )})
        text = run_turn(client, messages)
    raise AssertionError("unreachable")


def ref_errors(obj: dict) -> list[str]:
    """Every source_id / source_ids used anywhere must exist in obj['sources']."""
    known = {s.get("id") for s in obj.get("sources", []) if isinstance(s, dict)}
    errs: list[str] = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "source_id" and isinstance(v, int) and v not in known:
                    errs.append(f"{path}: unknown source_id {v}")
                elif k == "source_ids" and isinstance(v, list):
                    errs.extend(f"{path}: unknown source id {i}" for i in v if i not in known)
                elif k != "sources":
                    walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}/{i}")

    walk(obj, "")
    return errs


def research_json(prompt: str, schema: dict, check=None) -> dict:
    """Generic research turn for standing reports and site data: returns a schema-valid JSON object."""
    client = anthropic.Anthropic()
    messages: list = [{"role": "user", "content": prompt}]
    text = run_turn(client, messages, schema)
    for attempt in range(MAX_REPAIRS + 1):
        try:
            obj = extract_json(text)
            errs = schema_errors(obj, schema) + ref_errors(obj) + (check(obj) if check else [])
        except (json.JSONDecodeError, ValueError) as e:
            obj, errs = None, [f"not valid JSON: {e}"]
        if not errs:
            return obj
        if attempt == MAX_REPAIRS:
            raise RuntimeError("JSON still invalid:\n  " + "\n  ".join(errs[:30]))
        messages.append({"role": "user", "content": (
            "The JSON did not validate. Fix these errors and return the complete corrected JSON object "
            "in one ```json block (no other text). Do not invent sources to fill gaps.\n- " + "\n- ".join(errs[:30])
        )})
        text = run_turn(client, messages, schema)
    raise AssertionError("unreachable")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", help="Monday of the week to research (YYYY-MM-DD); default: preceding completed week")
    args = ap.parse_args(argv)
    start, end = parse_start(args.start) if args.start else preceding_week()
    out = briefing_dir(start, end) / "briefing.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        obj = research(start.isoformat(), end.isoformat())
    except (anthropic.APIError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ok  wrote {out.relative_to(ROOT)} ({len(obj['items'])} items, {len(obj['sources'])} sources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
