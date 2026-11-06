"""Build a single-topic report PDF (same design as the weekly PDFs).

Reports live in reports/<slug>_<date>.json and are built next to it as .pdf:

    python -m radar.build_report reports/payroll_2026-11-06.json

The JSON must match radar/report_schema.json (all text in French).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from radar.build_pdfs import (
    RADAR_DIR, BuildError, make_env, parse_date, quality_check, render_pdf_html,
)


def validate(r: dict) -> None:
    errors: list[str] = []
    import jsonschema

    schema = json.loads((RADAR_DIR / "report_schema.json").read_text(encoding="utf-8"))
    for e in jsonschema.Draft202012Validator(schema).iter_errors(r):
        errors.append(f"schema: {'/'.join(map(str, e.path)) or '<root>'}: {e.message}")
    if errors:
        raise BuildError("report JSON is invalid:\n  " + "\n  ".join(errors))

    known = {s["id"] for s in r["sources"]}
    if len(known) != len(r["sources"]):
        errors.append("duplicate source ids")
    for s in r["sections"]:
        refs = [i for c in s.get("cards", []) for i in c["source_ids"]]
        refs += [i for row in (s.get("table") or {}).get("rows", []) for i in row.get("source_ids", [])]
        for i in refs:
            if i not in known:
                errors.append(f"section '{s['heading']}': unknown source id {i}")
        table = s.get("table")
        if table:
            n = len(table["columns"])
            for k, row in enumerate(table["rows"], 1):
                if len(row["cells"]) != n:
                    errors.append(f"section '{s['heading']}': row {k} has {len(row['cells'])} cells, expected {n}")
    if errors:
        raise BuildError("report failed checks:\n  " + "\n  ".join(errors))


def build(path: Path) -> Path:
    path = Path(path)
    r = json.loads(path.read_text(encoding="utf-8"))
    validate(r)
    ctx = {
        **r,
        "css": (RADAR_DIR / "base.css").read_text(encoding="utf-8"),
        "example": bool(r.get("example")),
        "window_label": r["period"].upper(),
        "sources": sorted(r["sources"], key=lambda s: s["id"]),
    }
    parse_date(r["date"])
    # Fill optional keys so the template can stay strict about typos.
    ctx["sections"] = [
        {
            "paragraphs": [], "bullets": [], "table": None, **s,
            "cards": [{"priority": None, "status": "", "impact": "", "tags": [], **c} for c in s.get("cards", [])],
        }
        for s in r["sections"]
    ]
    for s in ctx["sections"]:
        if s["table"]:
            rows = [{"priority": None, "source_ids": [], **row} for row in s["table"]["rows"]]
            s["table"] = {**s["table"], "rows": rows}
    out = path.with_suffix(".pdf")
    html = make_env().get_template("template_report.html").render(**ctx)
    render_pdf_html(html, out)
    quality_check(out, r, path.parent / "_render")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", type=Path, help="path to reports/<slug>_<date>.json")
    ap.add_argument("--no-site", action="store_true", help="do not rebuild the website afterwards")
    args = ap.parse_args(argv)
    try:
        build(args.report)
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if not args.no_site:
        import subprocess
        return subprocess.call([sys.executable, str(RADAR_DIR.parent / "site" / "build_site.py")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
