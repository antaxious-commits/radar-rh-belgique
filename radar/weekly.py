"""Weekly run: window -> briefing.json -> PDFs -> website.

    python -m radar.weekly                    # preceding completed Mon-Sun week (Europe/Brussels)
    python -m radar.weekly --start 2026-11-02 # a specific week (any date in it works; snapped to Monday)
    python -m radar.weekly --print-window     # just print the window and target folder
    python -m radar.weekly --research-api     # API mode: research via Anthropic API first

Claude Code mode: Claude does the research itself (see CLAUDE.md), writes
briefings/<start>_<end>/briefing.json, then runs this command.
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
TZ = ZoneInfo("Europe/Brussels")


def preceding_week(now: dt.datetime | None = None) -> tuple[dt.date, dt.date]:
    """Monday-Sunday of the last fully completed week in Europe/Brussels."""
    today = (now or dt.datetime.now(TZ)).astimezone(TZ).date()
    this_monday = today - dt.timedelta(days=today.weekday())
    start = this_monday - dt.timedelta(days=7)
    return start, start + dt.timedelta(days=6)


def parse_start(s: str) -> tuple[dt.date, dt.date]:
    d = dt.date.fromisoformat(s)
    start = d - dt.timedelta(days=d.weekday())
    return start, start + dt.timedelta(days=6)


def briefing_dir(start: dt.date, end: dt.date) -> Path:
    return ROOT / "briefings" / f"{start.isoformat()}_{end.isoformat()}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", help="a date inside the week to build (default: preceding completed week)")
    ap.add_argument("--print-window", action="store_true", help="print window and folder, then exit")
    ap.add_argument("--research-api", action="store_true", help="research via the Anthropic API first (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--input", type=Path, help="build this briefing.json instead (e.g. an ad-hoc scan in briefings/adhoc_<date>/)")
    ap.add_argument("--no-site", action="store_true", help="do not rebuild the website")
    ap.add_argument("--no-standing", action="store_true",
                    help="with --research-api: skip the standing reports/data due today (see radar/standing.py)")
    args = ap.parse_args(argv)

    if args.input:
        from radar import build_pdfs
        try:
            build_pdfs.build(args.input)
        except build_pdfs.BuildError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        return 0 if args.no_site else subprocess.call([sys.executable, str(ROOT / "site" / "build_site.py")])

    start, end = parse_start(args.start) if args.start else preceding_week()
    folder = briefing_dir(start, end)
    if args.print_window:
        print(f"window: {start} to {end} (Europe/Brussels)")
        print(f"folder: {folder.relative_to(ROOT).as_posix()}")
        return 0

    if args.research_api:
        from radar import research_api
        rc = research_api.main(["--start", start.isoformat()])
        if rc:
            return rc

    briefing = folder / "briefing.json"
    if not briefing.exists():
        print(f"ERROR: {briefing.relative_to(ROOT)} not found. Research the week and write it first "
              f"(Claude Code mode), or pass --research-api.", file=sys.stderr)
        return 1

    from radar import build_pdfs
    try:
        build_pdfs.build(briefing)
    except build_pdfs.BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.research_api and not args.no_standing:
        # Standing reports and site data (90-day deadlines, transport, payroll, holidays, ...):
        # refreshed automatically by cadence, no slash command needed.
        from radar import standing
        standing.main([])

    if args.no_site:
        return 0
    return subprocess.call([sys.executable, str(ROOT / "site" / "build_site.py")])


if __name__ == "__main__":
    sys.exit(main())
