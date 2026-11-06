# Radar RH Belgique

Weekly Belgian employment-law and HR briefing (federal, Flanders, Wallonia, Brussels, German-speaking Community), **all output in French**. Every Monday it produces two A4 PDFs, **Actualités** and **Plan d'action**, and publishes them on a small mobile-friendly website (GitHub Pages). Single-topic reports (payroll check, 90-day deadlines, works-council gate, pay transparency, deep dives) use the same design and are listed under **Rapports** on the site.
Live site: https://antaxious-commits.github.io/radar-rh-belgique/


```
CLAUDE.md                   research rules, scope, priorities, PDF structure, quality checks
.claude/commands/           slash commands (/monday-briefing, /payroll-check, /deadlines-90, ...)
radar/schema.json           structure of one weekly briefing.json
radar/report_schema.json    structure of one single-topic report
radar/build_pdfs.py         briefing.json -> 2 PDFs (WeasyPrint + Jinja2) + quality checks
radar/build_report.py       reports/<slug>_<date>.json -> PDF in the same design
radar/template_*.html       PDF layouts; radar/base.css shared design; radar/fonts/ DejaVu Sans
radar/weekly.py             one command for the whole weekly run
radar/research_api.py       API mode: research via the Anthropic Messages API + web search
radar/send_email.py         optional email via Resend
site/build_site.py          regenerates site/index.html (latest week, Top 3, 90-day deadlines + echeances.ics,
                            all items of the week, reports, archive, mode d'emploi, official links)
briefings/<mon>_<sun>/      briefing.json + both PDFs, one folder per week
reports/                    single-topic report JSON + PDF
.github/workflows/          pages.yml (publish site), weekly.yml (Option B)
```

## What the site contains (all automatic)

Tabs: **Semaine** (at-a-glance tiles, both weekly PDFs, Top 3, every item, archive) · **Transport** (announced strikes and works, live SNCB disruptions, links to STIB / De Lijn / TEC, access to the store) · **Congés** (public holidays with countdown, school holidays of the three Communities, sales and retail peaks, `.ics`) · **Échéances** (next 90 days, `.ics`) · **Rapports** · **Infos**. On a phone: "Add to home screen" installs it like an app.

## Standing reports – refreshed automatically, no command needed

`radar/standing.py` runs after the weekly briefing (API mode: `python -m radar.weekly --research-api`; Claude Code routine: step 7 of CLAUDE.md). `python -m radar.standing --list` shows what is due.

| Every Monday | First Monday of the month |
|---|---|
| Transport data (strikes, works) · 90-day deadlines | Payroll check · Last 90 days · Transport & strikes report · Holidays data · Retail CP 311 · Pre-payroll checks · Employer in Brussels · Works council · This year vs last year · Pay transparency |

A failed job never blocks the others; the previous version stays online.

## Slash commands (optional, to refresh something on demand)

| Command | Output |
|---|---|
| `/monday-briefing [date]` | weekly briefing, both PDFs, website update |
| `/adhoc-scan [days] [levels]` | both PDFs for a chosen period in `briefings/adhoc_<date>/`, not published |
| `/payroll-check` · `/deadlines-90` · `/retro-90` · `/annual-changes` | payroll, next 90 days, last 90 days, this year vs last year |
| `/retail-check` · `/pre-payroll` · `/brussels-check` | CP 311 retail, pre-payroll checklist, employer in Brussels (FR/NL glossary) |
| `/transport-check` · `/holidays` | transport data + report, holidays data |
| `/works-council-gate` · `/pay-transparency` | consultation of employee bodies, Directive 2023/970 |
| `/deep-dive <theme or region>` | report: 30 days back, 90 days ahead on one theme or region |
| `/explain-for-managers` | plain-language French note for line managers, chat only |

## Commands

```bash
pip install -r requirements.txt
python -m radar.weekly --print-window          # which week, which folder
python -m radar.weekly                         # build PDFs + site for the preceding Mon–Sun week
python -m radar.weekly --start 2026-11-02      # a specific week
python -m radar.weekly --input briefings/adhoc_2026-11-06/briefing.json --no-site   # ad-hoc scan
python -m radar.weekly --research-api          # API mode: research first (needs ANTHROPIC_API_KEY)
python -m radar.build_report reports/payroll_2026-11-06.json                        # one report + site
python site/build_site.py                      # site only
```

Every build validates the JSON against its schema, checks every source reference, renders every page to PNG in a `_render/` folder, and fails loudly on stray `?`, U+FFFD, missing glyphs, empty pages or any font other than the embedded DejaVu Sans.

### System requirements

- **Linux / CI:** `apt-get install libpango-1.0-0 libpangoft2-1.0-0 poppler-utils`
- **Windows:** WeasyPrint needs Pango from MSYS2: `pacman -S mingw-w64-ucrt-x86_64-pango`, then set `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\ucrt64\bin`. PNG rendering falls back to pypdfium2 when `pdftoppm` is missing or blocked.
- **Claude Code on the web:** the cloud environment is Linux; if WeasyPrint fails to import, install the apt packages above in the environment's setup script.

## Scheduling

Pick one.

### A) Claude Code scheduled routine (uses your Claude plan, no extra cost) – recommended

1. Connect this GitHub repo to Claude Code on the web (claude.ai/code).
2. Create a routine (in the Claude Code app or with `/schedule` in a terminal session):
   - Repository: this repo, branch `main`
   - Schedule: weekly, **Monday 06:30 Europe/Brussels**
   - Prompt:
     > Run the weekly Radar RH Belgique: research the preceding completed Mon–Sun week following CLAUDE.md (Belgium only, French output), write briefing.json, run python -m radar.weekly, verify the PDFs, commit and push.
3. Make sure the routine is allowed to push to `main`.

If you use Option A, delete the `schedule:` block in `weekly.yml` so the week isn't researched twice.

### B) GitHub Actions + Anthropic API (independent of your Claude account)

`.github/workflows/weekly.yml` runs **Monday 05:30 UTC** (06:30 Brussels in winter, 07:30 in summer): `research_api.py` → `radar.weekly` → commit and push → publishes the site. It can also be started by hand from the Actions tab.

| Secret | Needed | What |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | API key from console.anthropic.com with prepaid credits (billed separately from Claude plans) |
| `RESEND_API_KEY` | for email | Resend account API key |
| `TO_EMAIL` | for email | recipient(s), comma-separated |
| `FROM_EMAIL` | optional | sender on a domain verified in Resend; without it, Resend only delivers to your own account address |

## Publishing (GitHub Pages)

Every push to `main` runs `pages.yml`, which rebuilds `index.html` and publishes it with all weekly PDFs and reports. The site is public to anyone with the URL (it has `noindex`, but that is not access control). Keep it to public legal news.

## Rules that matter

- Belgium only, French only.
- Every fact needs a fresh, external, clickable source; earlier briefings and repo files are never sources.
- Never invent sources, dates, deadlines or legal effects; proposals are labelled as proposals.
- Owners and internal targets are recommendations, never statutory deadlines.
- Secrets only in environment variables / GitHub secrets.
