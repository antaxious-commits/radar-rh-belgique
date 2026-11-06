# HR Europe Radar

Weekly European employment-law and HR briefing for an HR Business Partner Europe (EU, FR, BE, NL, DE, ES, IT). Every Monday it produces two A4 PDFs, **Weekly News** and **Action Plan**, and publishes them on a small mobile-friendly website (GitHub Pages).

```
CLAUDE.md                 research rules, scope, priorities, PDF structure, quality checks
radar/schema.json         structure of one weekly briefing.json
radar/build_pdfs.py       briefing.json -> 2 PDFs (WeasyPrint + Jinja2) + quality checks
radar/template_*.html     PDF layouts; radar/base.css shared design; radar/fonts/ DejaVu Sans
radar/weekly.py           one command for the whole weekly run
radar/research_api.py     API mode: research via the Anthropic Messages API + web search
radar/send_email.py       optional email via Resend
site/build_site.py        regenerates site/index.html (latest week, Top 3, 90-day deadlines, archive)
briefings/<mon>_<sun>/    briefing.json + both PDFs, one folder per week
.github/workflows/        pages.yml (publish site), weekly.yml (Option B)
```

Flow: research → `briefing.json` → `build_pdfs.py` → `build_site.py` → commit + push → GitHub Pages updates.

The folder `briefings/2026-10-26_2026-11-01/` holds **EXAMPLE data** for design review only (red watermark). The website shows it only until the first real briefing exists; delete the folder after the first real run.

## Commands

```bash
pip install -r requirements.txt
python -m radar.weekly --print-window          # which week, which folder
python -m radar.weekly                         # build PDFs + site for the preceding Mon–Sun week
python -m radar.weekly --start 2026-11-02      # a specific week
python -m radar.weekly --research-api          # API mode: research first (needs ANTHROPIC_API_KEY)
python -m radar.build_pdfs briefings/<folder>/briefing.json   # PDFs only
python site/build_site.py                      # site only
```

`build_pdfs` validates the JSON against the schema, checks every source reference, checks that all 7 jurisdictions are covered (or listed in `no_change`), renders every page to PNG in `briefings/<folder>/_render/`, and fails loudly on stray `?`, U+FFFD, missing glyphs, empty pages or any font other than the embedded DejaVu Sans.

### System requirements

- **Linux / CI:** `apt-get install libpango-1.0-0 libpangoft2-1.0-0 poppler-utils`
- **Windows:** WeasyPrint needs Pango from MSYS2: `pacman -S mingw-w64-ucrt-x86_64-pango`, then set `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\ucrt64\bin`. PNG rendering falls back to pypdfium2 when `pdftoppm` is missing or blocked.
- **Claude Code on the web:** the cloud environment is Linux; if WeasyPrint fails to import, install the apt packages above in the environment's setup script.

## Scheduling

Pick one.

### A) Claude Code scheduled routine (uses your Claude plan, no extra cost) – recommended

Claude Code on the web runs the job every Monday on your subscription and pushes to this repo; the push triggers `pages.yml`.

1. Push this repo to GitHub and connect it to Claude Code on the web (claude.ai/code).
2. Create a routine (in the Claude Code app or with `/schedule` in a terminal Claude Code session):
   - Repository: this repo, branch `main`
   - Schedule: weekly, **Monday 06:30 Europe/Brussels**
   - Prompt:
     > Run the weekly HR Europe Radar: research the preceding completed Mon–Sun week following CLAUDE.md, write briefing.json, run python -m radar.weekly, verify the PDFs, commit and push.
3. Make sure the routine is allowed to push to `main` (or to a branch you merge).

Email is not part of Option A. Bookmark the site instead, or add the Resend step from Option B as a separate GitHub Action triggered on push to `briefings/**`.

### B) GitHub Actions + Anthropic API (independent of your Claude account)

`.github/workflows/weekly.yml` runs **Monday 05:30 UTC** (06:30 Brussels in winter, 07:30 in summer): `research_api.py` → `radar.weekly` → commit and push → publishes the site. It can also be started by hand from the Actions tab, optionally with a date.

Repository secrets (Settings → Secrets and variables → Actions):

| Secret | Needed | What |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | API key from console.anthropic.com with prepaid credits (billed separately from Claude plans; expect a few dollars per run) |
| `RESEND_API_KEY` | for email | Resend account API key |
| `TO_EMAIL` | for email | recipient(s), comma-separated |
| `FROM_EMAIL` | optional | sender on a domain verified in Resend. Without it, Resend's test sender only delivers to your own Resend account address |

When both `RESEND_API_KEY` and `TO_EMAIL` are set, one email goes out with both PDFs attached and the Top 3 in the body.

API mode uses `claude-opus-5-5` with adaptive thinking, the server-side `web_search` and `web_fetch` tools, `CLAUDE.md` as the system prompt, and server-side refusal fallback. The returned JSON is validated against `radar/schema.json`; on errors the model gets up to two repair turns.

If you use Option A, disable the scheduled trigger in `weekly.yml` (delete the `schedule:` block) so the week isn't researched twice.

## Publishing (GitHub Pages)

1. Create a GitHub repo and push `main`.
2. Settings → Pages → Source: **GitHub Actions**.
3. Every push to `main` runs `pages.yml`, which rebuilds `index.html` and publishes it with all PDFs.

The site is public to anyone with the URL (it has `noindex`, but that is not access control). Keep it to public legal news. For a password-protected site use a private repo with Cloudflare Pages + Cloudflare Access.

## Rules that matter

- Every fact needs a fresh, external, clickable source; earlier briefings and repo files are never sources.
- Never invent sources, dates, deadlines or legal effects; proposals are labelled as proposals.
- Owners and internal targets are recommendations, never statutory deadlines.
- Secrets only in environment variables / GitHub secrets.
