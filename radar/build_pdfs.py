"""Turn a briefing.json into the two PDFs and run the quality checks.

Usage:
    python -m radar.build_pdfs briefings/2026-10-26_2026-11-01/briefing.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, StrictUndefined

RADAR_DIR = Path(__file__).resolve().parent
FONT_DIR = RADAR_DIR / "fonts"
NEWS_PDF = "RH_Belgique_Actualites.pdf"
ACTION_PDF = "RH_Belgique_Plan_d_action.pdf"

LEVEL_ORDER = ["federal", "flanders", "wallonia", "brussels", "german_community"]
LEVEL_NAMES = {
    "federal": "Fédéral", "flanders": "Flandre", "wallonia": "Wallonie",
    "brussels": "Bruxelles", "german_community": "Communauté germanophone",
}
PRI_FR = {"RED": "ROUGE", "AMBER": "ORANGE", "GREEN": "VERT"}
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]
MONTHS_FR_SHORT = ["JANV.", "FÉVR.", "MARS", "AVR.", "MAI", "JUIN", "JUIL.",
                   "AOÛT", "SEPT.", "OCT.", "NOV.", "DÉC."]
PRI_ORDER = {"RED": 0, "AMBER": 1, "GREEN": 2}


class BuildError(RuntimeError):
    pass


# ---------------------------------------------------------------- helpers

def parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def long_date(s: str) -> str:
    d = parse_date(s) if isinstance(s, str) else s
    day = "1er" if d.day == 1 else str(d.day)
    return f"{day} {MONTHS_FR[d.month - 1]} {d.year}"


def window_label(start: dt.date, end: dt.date) -> str:
    """e.g. '26 OCT. – 01 NOV. 2026' (upper case for the header line)."""
    a = f"{start.day:02d} {MONTHS_FR_SHORT[start.month - 1]}"
    if start.year != end.year:
        a += f" {start.year}"
    return f"{a} – {end.day:02d} {MONTHS_FR_SHORT[end.month - 1]} {end.year}"


def domain(url: str) -> str:
    host = urlparse(url).netloc
    return host[4:] if host.startswith("www.") else host


# ---------------------------------------------------------------- validation

def validate(b: dict) -> None:
    """Schema validation plus cross-reference checks. Raises BuildError."""
    errors: list[str] = []
    try:
        import jsonschema  # type: ignore
        schema = json.loads((RADAR_DIR / "schema.json").read_text(encoding="utf-8"))
        v = jsonschema.Draft202012Validator(schema)
        for e in sorted(v.iter_errors(b), key=lambda e: list(e.path)):
            errors.append(f"schema: {'/'.join(map(str, e.path)) or '<root>'}: {e.message}")
    except ImportError:
        print("warning: jsonschema not installed, skipping schema validation", file=sys.stderr)

    if errors:
        raise BuildError("briefing.json is invalid:\n  " + "\n  ".join(errors))

    src_ids = [s["id"] for s in b["sources"]]
    if len(src_ids) != len(set(src_ids)):
        errors.append("duplicate source ids")
    known = set(src_ids)
    item_ids = {i["id"] for i in b["items"]}

    def check_refs(where: str, ids):
        for i in ids:
            if i not in known:
                errors.append(f"{where}: unknown source id {i}")

    for it in b["items"]:
        check_refs(f"item {it['id']}", it["source_ids"])
    for a in b["actions"]:
        check_refs(f"action '{a['title']}'", a["source_ids"])
        if a["priority"] == "AMBER" and not a.get("legal_date"):
            print(f"note: AMBER action '{a['title']}' has no legal_date", file=sys.stderr)
    for d in b["deadlines_90d"]:
        check_refs(f"deadline {d['date']}", [d["source_id"]])
    for t in b["top3"]:
        if t["item_id"] not in item_ids:
            errors.append(f"top3 refers to unknown item id {t['item_id']}")

    used = set()
    for it in b["items"]:
        used.update(it["source_ids"])
    for a in b["actions"]:
        used.update(a["source_ids"])
    used.update(d["source_id"] for d in b["deadlines_90d"])
    unused = known - used
    if unused:
        print(f"note: sources never cited: {sorted(unused)}", file=sys.stderr)

    start, end = parse_date(b["window"]["start"]), parse_date(b["window"]["end"])
    if end < start:
        errors.append("window end is before window start")

    for it in b["items"]:
        if re.search(r"\b(responsable|échéance interne|owner)\b", it["what_changed"] + it["potential_impact"], re.I):
            errors.append(f"item {it['id']}: PDF 1 must not contain owners or internal targets")

    if not b["items"] and not b.get("quiet_week_note"):
        errors.append("no items: add quiet_week_note explaining what was searched")

    if errors:
        raise BuildError("briefing.json failed checks:\n  " + "\n  ".join(errors))


# ---------------------------------------------------------------- rendering

def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(RADAR_DIR)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["domain"] = domain
    env.filters["longdate"] = long_date
    env.filters["level_name"] = lambda c: LEVEL_NAMES[c]
    env.filters["pri_fr"] = lambda p: PRI_FR[p]
    return env


def context(b: dict) -> dict:
    start, end = parse_date(b["window"]["start"]), parse_date(b["window"]["end"])
    items = sorted(b["items"], key=lambda i: LEVEL_ORDER.index(i["level"]))
    groups = []
    for j in LEVEL_ORDER:
        g = [i for i in items if i["level"] == j]
        if g:
            groups.append((j, g))
    actions = sorted(b["actions"], key=lambda a: PRI_ORDER[a["priority"]])
    radar_end = end + dt.timedelta(days=90)
    return {
        "css": (RADAR_DIR / "base.css").read_text(encoding="utf-8"),
        "example": bool(b.get("example")),
        "edition": b.get("edition") or f"SEMAINE {start.isocalendar().week}",
        "window_label": window_label(start, end),
        "window_long": f"Du {long_date(b['window']['start'])} au {long_date(b['window']['end'])}",
        "radar_label": f"jusqu'au {long_date(radar_end)}",
        "top3": b["top3"],
        "items": items,
        "items_by_level": groups,
        "level_names": LEVEL_NAMES,
        "quiet_week_note": b.get("quiet_week_note", ""),
        "immediate_theme": b.get("immediate_theme", ""),
        "control_line": b.get("control_line", ""),
        "red": [a for a in actions if a["priority"] == "RED"],
        "amber": [a for a in actions if a["priority"] == "AMBER"],
        "green": [a for a in actions if a["priority"] == "GREEN"],
        "deadlines": sorted(b["deadlines_90d"], key=lambda d: d["date"]),
        "what_this_means": b["what_this_means"],
        "sources": sorted(b["sources"], key=lambda s: s["id"]),
    }


def render_pdf(template: str, ctx: dict, out: Path) -> None:
    render_pdf_html(make_env().get_template(template).render(**ctx), out)


def render_pdf_html(html: str, out: Path) -> None:
    from weasyprint import HTML  # imported late so --help works without it

    HTML(string=html, base_url=RADAR_DIR.as_uri() + "/").write_pdf(str(out))


# ---------------------------------------------------------------- quality checks

def all_strings(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in all_strings(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in all_strings(v)]
    return []


def font_charset() -> set[int]:
    from fontTools.ttLib import TTFont

    sets = [set(TTFont(str(FONT_DIR / f)).getBestCmap()) for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")]
    return set.intersection(*sets)


def embedded_fonts(pdf: Path) -> set[str]:
    """Base font names of every font used on any page."""
    from pypdf import PdfReader

    names: set[str] = set()
    for page in PdfReader(str(pdf)).pages:
        fonts = (page.get("/Resources") or {}).get("/Font") or {}
        for ref in fonts.values():
            f = ref.get_object()
            names.add(str(f.get("/BaseFont", "")))
    return names


def extract_text(pdf: Path) -> list[str]:
    from pypdf import PdfReader

    return [page.extract_text() or "" for page in PdfReader(str(pdf)).pages]


def render_pngs(pdf: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = pdf.stem
    for old in out_dir.glob(f"{stem}-*.png"):
        old.unlink()
    done = False
    if shutil.which("pdftoppm"):
        try:
            subprocess.run(["pdftoppm", "-r", "80", "-png", str(pdf), str(out_dir / stem)], check=True)
            done = True
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"note: pdftoppm unusable ({e}); falling back to pypdfium2", file=sys.stderr)
    if not done:
        import pypdfium2 as pdfium  # fallback when poppler is not installed or blocked

        doc = pdfium.PdfDocument(str(pdf))
        for i, page in enumerate(doc, start=1):
            page.render(scale=80 / 72).to_pil().save(out_dir / f"{stem}-{i:02d}.png")
    pngs = sorted(out_dir.glob(f"{stem}-*.png"))
    if not pngs:
        raise BuildError(f"{pdf.name}: no pages rendered")
    return pngs


def quality_check(pdf: Path, briefing: dict, render_dir: Path) -> None:
    problems: list[str] = []
    pages = extract_text(pdf)
    pngs = render_pngs(pdf, render_dir)
    if len(pngs) != len(pages):
        problems.append(f"rendered {len(pngs)} PNGs for {len(pages)} pages")

    text = "\n".join(pages)
    if "�" in text:
        problems.append("extracted text contains U+FFFD replacement characters")

    # '?' is only allowed as often as it occurs in the input data itself
    expected_q = sum(s.count("?") for s in all_strings(briefing) if not s.startswith("http"))
    found_q = text.count("?")
    if found_q > expected_q:
        idx = [m.start() for m in re.finditer(r"\?", text)][:5]
        snippets = [text[max(0, i - 30): i + 10].replace("\n", " ") for i in idx]
        problems.append(f"{found_q} '?' in PDF text vs {expected_q} in source data: {snippets}")

    for n, p in enumerate(pages, start=1):
        if not p.strip():
            problems.append(f"page {n} is empty")

    fonts = embedded_fonts(pdf)
    foreign = sorted(f for f in fonts if "DejaVu" not in f)
    if not fonts or foreign:
        problems.append(f"fonts other than embedded DejaVu Sans were used: {foreign or 'none found'}")

    charset = font_charset()
    needed = {ord(c) for s in all_strings(briefing) for c in s if not c.isspace()}
    missing = sorted(c for c in needed if c not in charset)
    if missing:
        problems.append("characters missing from embedded font: " + ", ".join(f"U+{c:04X} {chr(c)!r}" for c in missing))

    if problems:
        raise BuildError(f"QUALITY CHECK FAILED for {pdf.name}:\n  " + "\n  ".join(problems))
    print(f"ok  {pdf.name}: {len(pages)} pages, renders in {render_dir}")


# ---------------------------------------------------------------- entry point

def build(briefing_path: Path) -> tuple[Path, Path]:
    briefing_path = Path(briefing_path)
    b = json.loads(briefing_path.read_text(encoding="utf-8"))
    validate(b)
    ctx = context(b)
    out_dir = briefing_path.parent
    news, action = out_dir / NEWS_PDF, out_dir / ACTION_PDF
    render_pdf("template_news.html", ctx, news)
    render_pdf("template_action.html", ctx, action)
    render_dir = out_dir / "_render"
    quality_check(news, b, render_dir)
    quality_check(action, b, render_dir)

    # Content-separation check: PDF 1 must not show owners / internal targets.
    news_text = "\n".join(extract_text(news))
    for a in b["actions"]:
        if a["proposed_owner"] and a["proposed_owner"] in news_text and "Responsable" in news_text:
            raise BuildError(f"PDF 1 appears to contain owner '{a['proposed_owner']}'")
    return news, action


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("briefing", type=Path, help="path to briefing.json")
    args = ap.parse_args(argv)
    try:
        build(args.briefing)
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
