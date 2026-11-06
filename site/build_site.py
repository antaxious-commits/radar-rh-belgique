"""Regenerate site/index.html from briefings/*/briefing.json.

The latest week gets Top 3 cards, the 90-day deadline table and PDF download
buttons; earlier weeks go into the archive. PDFs are copied into site/briefings/
so the folder can be served as-is (locally or by GitHub Pages).

Usage:  python site/build_site.py
"""
from __future__ import annotations

import datetime as dt
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEFINGS = ROOT / "briefings"
REPORTS = ROOT / "reports"
SITE = ROOT / "site"
PDFS = ("RH_Belgique_Actualites.pdf", "RH_Belgique_Plan_d_action.pdf")
LEVELS = {"federal": "Fédéral", "flanders": "Flandre", "wallonia": "Wallonie", "brussels": "Bruxelles",
          "german_community": "Communauté germanophone"}
PRI_FR = {"RED": "ROUGE", "AMBER": "ORANGE", "GREEN": "VERT"}
MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]

e = html.escape


def d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def fmt(s: str, year=True) -> str:
    x = d(s)
    day = "1er" if x.day == 1 else str(x.day)
    return f"{day} {MONTHS[x.month - 1]}" + (f" {x.year}" if year else "")


def span(w: dict) -> str:
    return f"{fmt(w['start'], year=d(w['start']).year != d(w['end']).year)} au {fmt(w['end'])}"


def load() -> list[dict]:
    weeks = []
    for p in sorted(BRIEFINGS.glob("*/briefing.json")):
        if p.parent.name.startswith("adhoc_"):
            continue  # ad-hoc scans are not published unless moved
        b = json.loads(p.read_text(encoding="utf-8"))
        if not all((p.parent / f).exists() for f in PDFS):
            continue  # not built yet
        b["_dir"] = p.parent.name
        weeks.append(b)
    real = [w for w in weeks if not w.get("example")]
    weeks = real or weeks  # the EXAMPLE week is shown only until the first real run
    return sorted(weeks, key=lambda w: w["window"]["start"], reverse=True)


def load_reports() -> list[dict]:
    reports = []
    for p in REPORTS.glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("example") or not p.with_suffix(".pdf").exists():
            continue
        r["_pdf"] = p.with_suffix(".pdf").name
        reports.append(r)
    return sorted(reports, key=lambda r: (r["date"], r["title"]), reverse=True)


def stage_reports(reports: list[dict]) -> None:
    out = SITE / "reports"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for r in reports:
        shutil.copy2(REPORTS / r["_pdf"], out / r["_pdf"])


def reports_html(reports: list[dict]) -> str:
    if not reports:
        return '<li class="muted">Aucun rapport thématique pour le moment.</li>'
    out = []
    for r in reports:
        title = r["title"].split("|", 1)[-1].strip().capitalize()
        summary = f'<small>{e(r["summary"])}</small>' if r.get("summary") else ""
        out.append(f'<li><span>{e(title)}<small>{e(r["period"])} · {e(fmt(r["date"]))}</small>{summary}</span>'
                   f'<a href="reports/{e(r["_pdf"])}">PDF</a></li>')
    return "".join(out)


def stage_pdfs(weeks: list[dict]) -> None:
    out = SITE / "briefings"
    if out.exists():
        shutil.rmtree(out)
    for w in weeks:
        dst = out / w["_dir"]
        dst.mkdir(parents=True)
        for f in PDFS:
            shutil.copy2(BRIEFINGS / w["_dir"] / f, dst / f)


def render(weeks: list[dict], reports: list[dict]) -> str:
    reports_section = f"""
  <section>
    <h2>Rapports</h2>
    <ul class="archive reports">{reports_html(reports)}</ul>
  </section>"""
    if not weeks:
        body = '<p class="empty">Aucune note publiée pour le moment.</p>' + reports_section
        return PAGE.format(title="Radar RH Belgique", body=body)

    w = weeks[0]
    items = {i["id"]: i for i in w["items"]}
    src = {s["id"]: s for s in w["sources"]}
    base = f"briefings/{e(w['_dir'])}"

    cards = []
    for t in w["top3"]:
        it = items.get(t["item_id"], {})
        cc = it.get("level", "")
        cards.append(f"""
      <article class="card {e(t['priority'])}">
        <div class="tag"><span class="pri">{PRI_FR[t['priority']]}</span><span>{e(LEVELS.get(cc, cc))}</span></div>
        <h3>{e(t['headline'])}</h3>
        <p>{e(t['why_it_matters'])}</p>
        {f'<p class="meta">{e(it["status"])} · {e(it["effective_date"])}</p>' if it else ''}
      </article>""")

    rows = []
    for x in sorted(w["deadlines_90d"], key=lambda x: x["date"]):
        s = src.get(x["source_id"])
        link = f' <a href="{e(s["url"])}" rel="noopener noreferrer">source</a>' if s else ""
        kind = "Échéance légale" if x["type"] == "legal_deadline" else "Date d'application"
        rows.append(f"<tr><td class=\"date\">{e(fmt(x['date']))}</td><td>{e(LEVELS.get(x['level'], x['level']))}</td>"
                    f"<td>{e(x['description'])}{link}<span class=\"kind\">{kind}</span></td></tr>")
    if not rows:
        rows.append('<tr><td colspan="3">Aucune échéance identifiée dans les 90 prochains jours.</td></tr>')

    archive = "".join(
        f'<li><span>{e(span(a["window"]))}</span>'
        f'<a href="briefings/{e(a["_dir"])}/{PDFS[0]}">Actualités</a>'
        f'<a href="briefings/{e(a["_dir"])}/{PDFS[1]}">Plan d’action</a></li>'
        for a in weeks[1:]
    ) or '<li class="muted">Les semaines précédentes apparaîtront ici.</li>'

    example = ('<p class="example">DONNÉES D’EXEMPLE – aperçu de la mise en page. La première vraie note remplacera cette page.</p>'
               if w.get("example") else "")

    body = f"""
  <header class="top">
    <p class="eyebrow">Radar RH Belgique</p>
    <h1>Semaine du {e(span(w['window']))}</h1>
    <p class="sub">Veille droit social et RH pour la Belgique. Mise à jour chaque lundi.</p>
  </header>
  {example}
  <section class="downloads">
    <a class="btn primary" href="{base}/{PDFS[0]}"><b>Actualités</b><span>Ce qui change et impact potentiel · PDF</span></a>
    <a class="btn" href="{base}/{PDFS[1]}"><b>Plan d’action</b><span>Actions priorisées et échéances · PDF</span></a>
  </section>
  <section>
    <h2>Les 3 points clés</h2>
    <div class="cards">{''.join(cards)}
    </div>
  </section>
  <section>
    <h2>Échéances des 90 prochains jours</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Date</th><th>Niveau</th><th>Quoi</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table></div>
  </section>
{reports_section}
  <section>
    <h2>Archives</h2>
    <ul class="archive">{archive}</ul>
  </section>
  <footer>L’impact potentiel est une évaluation et non un avis juridique. L’applicabilité dépend de l’entité, de la commission paritaire, du personnel et de la CCT applicable. Chaque point renvoie à sa source dans les PDF.</footer>"""
    return PAGE.format(title=f"Radar RH Belgique – {e(span(w['window']))}", body=body)


PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<style>
:root {{
  --bg: #f6f7f9; --panel: #ffffff; --ink: #1d2433; --muted: #5b6475; --rule: #dfe3ea;
  --navy: #1F2A44; --teal: #3FB8AF; --teal-fill: #E8F6F5;
  --red: #C0392B; --amber: #B7791F; --green: #2F855A;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #10151f; --panel: #182030; --ink: #e7ebf2; --muted: #9aa5b8; --rule: #2a3447;
          --teal-fill: #15302f; --red: #ef7a6c; --amber: #e3b25b; --green: #6cc795; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
main {{ max-width: 860px; margin: 0 auto; padding: 0 16px 48px; }}
.top {{ background: var(--navy); color: #fff; margin: 0 -16px; padding: 28px 16px 22px; border-bottom: 4px solid var(--teal); }}
.eyebrow {{ margin: 0; color: var(--teal); font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }}
h1 {{ margin: 6px 0 4px; font-size: 26px; line-height: 1.2; }}
.sub {{ margin: 0; color: #c9d2e3; font-size: 15px; }}
h2 {{ font-size: 13px; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin: 32px 0 12px; }}
.example {{ border: 2px solid var(--red); color: var(--red); font-weight: 700; padding: 10px 12px; border-radius: 8px; margin: 20px 0 0; }}
.downloads {{ display: grid; gap: 12px; margin-top: 20px; }}
.btn {{ display: block; padding: 16px 18px; border-radius: 12px; text-decoration: none; color: var(--ink);
  background: var(--panel); border: 1px solid var(--rule); min-height: 64px; }}
.btn b {{ display: block; font-size: 18px; }}
.btn span {{ color: var(--muted); font-size: 14px; }}
.btn.primary {{ background: var(--teal); border-color: var(--teal); color: #0d1b2a; }}
.btn.primary span {{ color: #0d1b2a; opacity: .8; }}
.cards {{ display: grid; gap: 12px; }}
.card {{ background: var(--panel); border: 1px solid var(--rule); border-left: 5px solid var(--teal); border-radius: 10px; padding: 14px 16px; }}
.card.RED {{ border-left-color: var(--red); }} .card.AMBER {{ border-left-color: var(--amber); }} .card.GREEN {{ border-left-color: var(--green); }}
.card h3 {{ margin: 6px 0; font-size: 17px; line-height: 1.3; }}
.card p {{ margin: 0; }}
.card .meta {{ margin-top: 8px; color: var(--muted); font-size: 14px; }}
.tag {{ display: flex; gap: 10px; font-size: 12px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }}
.RED .pri {{ color: var(--red); }} .AMBER .pri {{ color: var(--amber); }} .GREEN .pri {{ color: var(--green); }}
.table-wrap {{ overflow-x: auto; background: var(--panel); border: 1px solid var(--rule); border-radius: 10px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
th {{ text-align: left; font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); padding: 10px 12px; border-bottom: 1px solid var(--rule); }}
td {{ padding: 10px 12px; border-bottom: 1px solid var(--rule); vertical-align: top; }}
tr:last-child td {{ border-bottom: 0; }}
td.date {{ white-space: nowrap; font-weight: 700; }}
.kind {{ display: block; color: var(--muted); font-size: 13px; }}
a {{ color: inherit; }}
td a {{ color: var(--teal); }}
.archive {{ list-style: none; padding: 0; margin: 0; background: var(--panel); border: 1px solid var(--rule); border-radius: 10px; }}
.archive li {{ display: flex; flex-wrap: wrap; gap: 6px 16px; padding: 12px 14px; border-bottom: 1px solid var(--rule); }}
.archive li:last-child {{ border-bottom: 0; }}
.archive span {{ flex: 1 1 160px; font-weight: 600; }}
.archive a {{ color: var(--teal); font-weight: 600; padding: 2px 0; }}
.muted {{ color: var(--muted); }}
.archive small {{ display: block; font-weight: 400; color: var(--muted); font-size: 13px; }}
footer {{ margin-top: 36px; color: var(--muted); font-size: 13px; }}
@media (min-width: 640px) {{
  .downloads {{ grid-template-columns: 1fr 1fr; }}
  .cards {{ grid-template-columns: repeat(3, 1fr); }}
  h1 {{ font-size: 32px; }}
}}
</style>
</head>
<body><main>{body}
</main></body>
</html>
"""


def build() -> Path:
    weeks = load()
    reports = load_reports()
    stage_pdfs(weeks)
    stage_reports(reports)
    out = SITE / "index.html"
    out.write_text(render(weeks, reports), encoding="utf-8")
    print(f"ok  site/index.html ({len(weeks)} week(s), {len(reports)} report(s))")
    return out


if __name__ == "__main__":
    build()
