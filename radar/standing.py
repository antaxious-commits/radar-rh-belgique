"""Standing reports and site data, refreshed automatically by the weekly run.

Nothing here needs a slash command: every Monday the weekly run refreshes what is due.
The research brief for each job is the matching file in .claude/commands/ (shared with
Claude Code mode), so both modes produce the same thing.

    python -m radar.standing --list                 # what is due today
    python -m radar.standing                        # research + build everything due (API mode)
    python -m radar.standing --only deadlines       # one job, due or not
    python -m radar.standing --all                  # every job
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from radar.weekly import ROOT, TZ

COMMANDS = ROOT / ".claude" / "commands"

# cadence: "weekly" = every Monday run; "monthly" = first run of each month (day <= 7).
# kind "report" -> reports/<slug>_<date>.json + PDF; kind "data" -> data/<name>.json (site tabs).
JOBS = [
    {"slug": "transport-data", "kind": "data", "out": "transport", "schema": "transport_schema.json",
     "command": "transport-check", "cadence": "weekly",
     "note": "Only deliverable 1 (data/transport.json) is needed in this job."},
    {"slug": "deadlines", "kind": "report", "command": "deadlines-90", "cadence": "weekly",
     "title": "RH BELGIQUE | ÉCHÉANCES À 90 JOURS"},
    {"slug": "payroll", "kind": "report", "command": "payroll-check", "cadence": "monthly",
     "title": "RH BELGIQUE | CONTRÔLE DE PAIE"},
    {"slug": "retro-90", "kind": "report", "command": "retro-90", "cadence": "monthly",
     "title": "RH BELGIQUE | CE QUI A CHANGÉ (90 DERNIERS JOURS)"},
    {"slug": "transport", "kind": "report", "command": "transport-check", "cadence": "monthly",
     "title": "RH BELGIQUE | TRANSPORT ET GRÈVES",
     "note": "Only deliverable 2 (the report) is needed in this job."},
    {"slug": "conges", "kind": "data", "out": "conges", "schema": "conges_schema.json",
     "command": "holidays", "cadence": "monthly"},
    {"slug": "retail", "kind": "report", "command": "retail-check", "cadence": "monthly",
     "title": "RH BELGIQUE | COMMERCE DE DÉTAIL"},
    {"slug": "pre-paie", "kind": "report", "command": "pre-payroll", "cadence": "monthly",
     "title": "RH BELGIQUE | CONTRÔLES AVANT PAIE"},
    {"slug": "bruxelles", "kind": "report", "command": "brussels-check", "cadence": "monthly",
     "title": "RH BELGIQUE | EMPLOYEUR À BRUXELLES"},
    {"slug": "works-council", "kind": "report", "command": "works-council-gate", "cadence": "monthly",
     "title": "RH BELGIQUE | ORGANES DE CONCERTATION"},
    {"slug": "annee", "kind": "report", "command": "annual-changes", "cadence": "monthly",
     "title": None},  # title depends on the year, see title_for()
    {"slug": "pay-transparency", "kind": "report", "command": "pay-transparency", "cadence": "monthly",
     "title": "RH BELGIQUE | TRANSPARENCE SALARIALE"},
]


def today() -> dt.date:
    return dt.datetime.now(TZ).date()


def is_due(job: dict, day: dt.date) -> bool:
    return job["cadence"] == "weekly" or day.day <= 7


def report_slug(job: dict, day: dt.date) -> str:
    return f"annee-{day.year}" if job["slug"] == "annee" else job["slug"]


def title_for(job: dict, day: dt.date) -> str:
    return job["title"] or f"RH BELGIQUE | {day.year} PAR RAPPORT À {day.year - 1}"


def brief(job: dict, day: dt.date) -> str:
    text = (COMMANDS / f"{job['command']}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    text = text.replace("$ARGUMENTS", "").replace("<today>", day.isoformat())
    return text.strip() + ("\n\n" + job["note"] if job.get("note") else "")


def output_path(job: dict, day: dt.date) -> Path:
    if job["kind"] == "data":
        return ROOT / "data" / f"{job['out']}.json"
    return ROOT / "reports" / f"{report_slug(job, day)}_{day.isoformat()}.json"


def run_job(job: dict, day: dt.date) -> Path:
    """Research one job via the API, validate, write, and build its PDF."""
    from radar import research_api

    schema_file = ROOT / "radar" / (job.get("schema") or "report_schema.json")
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    if job["kind"] == "report":
        extra = (f"Return the report as ONE JSON object for radar/report_schema.json with "
                 f"title \"{title_for(job, day)}\", slug \"{report_slug(job, day)}\", date \"{day.isoformat()}\". "
                 f"The pipeline builds the PDF; ignore any instruction to run commands.")
    else:
        extra = (f"Return ONE JSON object for {schema_file.name} with \"updated\": \"{day.isoformat()}\". "
                 f"Ignore any instruction to run commands or write files.")
    prompt = f"Today is {day.isoformat()}.\n\n{brief(job, day)}\n\n{extra}"

    def check(o: dict) -> list[str]:
        if job["kind"] != "report":
            return []
        from radar.build_pdfs import BuildError
        from radar.build_report import validate
        try:
            validate({**o, "slug": report_slug(job, day), "date": day.isoformat(), "title": title_for(job, day)})
        except BuildError as e:
            return [str(e)]
        return []

    obj = research_api.research_json(prompt, schema, check)
    out = output_path(job, day)
    out.parent.mkdir(parents=True, exist_ok=True)
    if job["kind"] == "report":
        obj.update({"slug": report_slug(job, day), "date": day.isoformat(), "title": title_for(job, day)})
        obj.pop("example", None)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if job["kind"] == "report":
        from radar import build_report
        build_report.build(out)
    print(f"ok  {job['slug']}: {out.relative_to(ROOT).as_posix()}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print which jobs are due today and exit")
    ap.add_argument("--only", nargs="+", help="run these job slugs, due or not")
    ap.add_argument("--all", action="store_true", help="run every job")
    ap.add_argument("--date", help="pretend today is this date (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    day = dt.date.fromisoformat(args.date) if args.date else today()
    jobs = [j for j in JOBS if (args.all or (args.only and j["slug"] in args.only)
                                or (not args.only and is_due(j, day)))]
    if args.list:
        for j in JOBS:
            print(f"{'DUE ' if j in jobs else '    '}{j['slug']:<17} {j['cadence']:<8} -> "
                  f"{output_path(j, day).relative_to(ROOT).as_posix()}")
        return 0
    failed = []
    for j in jobs:
        try:
            run_job(j, day)
        except Exception as e:  # one failing job must not block the others
            failed.append(j["slug"])
            print(f"ERROR {j['slug']}: {e}", file=sys.stderr)
    if failed:
        print(f"{len(failed)} job(s) failed: {', '.join(failed)} – the previous version stays online.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
