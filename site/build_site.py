"""Regenerate the website in site/ from briefings/, reports/ and data/.

Tabs: Semaine · Transport · Congés · Échéances · Rapports · Infos.
- briefings/*/briefing.json  -> latest week (Top 3, all items, PDFs, archive)
- reports/*.json + .pdf      -> Rapports tab; the latest deadlines_*.json feeds the Échéances tab
- data/transport.json        -> announced strikes/works, access, live links (live SNCB feed is fetched in the browser)
- data/conges.json           -> public holidays, school holidays, retail peaks
Writes site/index.html, site/echeances.ics, site/conges.ics, site/manifest.webmanifest and copies PDFs.

Usage:  python site/build_site.py
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEFINGS = ROOT / "briefings"
REPORTS = ROOT / "reports"
DATA = ROOT / "data"
SITE = ROOT / "site"
PDFS = ("RH_Belgique_Actualites.pdf", "RH_Belgique_Plan_d_action.pdf")
LEVELS = {"federal": "Fédéral", "flanders": "Flandre", "wallonia": "Wallonie", "brussels": "Bruxelles",
          "german_community": "Communauté germanophone"}
PRI_FR = {"RED": "ROUGE", "AMBER": "ORANGE", "GREEN": "VERT"}
CONSULT = {"confirmed": "information-consultation confirmée",
           "conditional": "obligation possible selon l’entité, les seuils ou la CCT applicable", "none": ""}
COMMUNITIES = {"fr": "Fédération Wallonie-Bruxelles", "nl": "Communauté flamande", "de": "Communauté germanophone"}
DAILY = ("pre-paie", "retail", "bruxelles", "transport")  # report slugs shown under "Au quotidien"
OVERVIEW = ("retro-90", "deadlines", "annee")
OFFICIAL = [
    ("Moniteur belge", "https://www.ejustice.just.fgov.be/cgi/welcome.pl", "textes publiés"),
    ("SPF Emploi, Travail et Concertation sociale", "https://emploi.belgique.be/fr", "droit du travail, CCT, salaires minimums"),
    ("ONSS / Sécurité sociale", "https://www.socialsecurity.be/site_fr/employer/index.htm", "cotisations, réductions, instructions"),
    ("SPF Finances – précompte professionnel", "https://finances.belgium.be/fr/entreprises/personnel_et_remuneration", "barèmes, fiches"),
    ("Conseil national du Travail", "https://cnt-nar.be/fr", "CCT interprofessionnelles, avis"),
    ("INAMI", "https://www.inami.fgov.be/fr", "incapacité de travail, réintégration"),
    ("Forem", "https://www.leforem.be/", "aides à l’emploi en Wallonie"),
    ("Actiris", "https://www.actiris.brussels/fr/employeurs/", "aides à l’emploi à Bruxelles"),
    ("VDAB", "https://www.vdab.be/werkgevers", "aides à l’emploi en Flandre"),
]
MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MONTHS_LONG = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
               "novembre", "décembre"]
DAYS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]

e = html.escape


SOCIAL = re.compile(r"grève|greve|manifestation|action syndicale|préavis|staking", re.I)


class SiteError(Exception):
    pass


def d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def fmt(s: str, year=True, weekday=False) -> str:
    x = d(s)
    day = "1er" if x.day == 1 else str(x.day)
    out = f"{day} {MONTHS[x.month - 1]}" + (f" {x.year}" if year else "")
    return f"{DAYS[x.weekday()]} {out}" if weekday else out


def fmt_range(a: str, b: str) -> str:
    if a == b:
        return fmt(a, weekday=True)
    return f"{fmt(a, year=d(a).year != d(b).year)} → {fmt(b)}"


def span(w: dict) -> str:
    return f"{fmt(w['start'], year=d(w['start']).year != d(w['end']).year)} au {fmt(w['end'])}"


def parse_fr_date(text: str) -> tuple[str | None, bool]:
    """'13 novembre 2026' -> ('2026-11-13', True); 'Décembre 2026' -> ('2026-12-01', False)."""
    t = text.lower().replace("1er", "1")
    m = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS_LONG) + r")\s+(\d{4})", t)
    if m:
        return dt.date(int(m[3]), MONTHS_LONG.index(m[2]) + 1, int(m[1])).isoformat(), True
    m = re.search(r"(" + "|".join(MONTHS_LONG) + r")\s+(\d{4})", t)
    if m:
        return dt.date(int(m[2]), MONTHS_LONG.index(m[1]) + 1, 1).isoformat(), False
    return None, False


# ---------------------------------------------------------------- loading

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


def load_data(name: str) -> dict | None:
    p = DATA / f"{name}.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    ids = {s["id"] for s in data.get("sources", [])}
    for key, rows in data.items():
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and "source_id" in row and row["source_id"] not in ids:
                    raise SiteError(f"data/{name}.json: {key}: unknown source_id {row['source_id']}")
    rr = data.get("replacement_rule")
    if rr and rr.get("source_id") not in ids:
        raise SiteError(f"data/{name}.json: replacement_rule: unknown source_id")
    data["_src"] = {s["id"]: s for s in data.get("sources", [])}
    return data


def latest(reports: list[dict], slug: str) -> dict | None:
    return next((r for r in reports if r.get("slug") == slug), None)


def deadline_rows(reports: list[dict], w: dict | None) -> list[dict]:
    """Rows for the Échéances tab: the latest 90-day report, else the briefing's radar."""
    rep = latest(reports, "deadlines")
    rows = []
    if rep:
        src = {s["id"]: s for s in rep["sources"]}
        for s in rep["sections"]:
            t = s.get("table")
            if not t or [c.lower() for c in t["columns"][:2]] != ["date", "niveau"]:
                continue
            for r in t["rows"]:
                iso, exact = parse_fr_date(r["cells"][0])
                rows.append({"date": iso, "exact": exact, "label": r["cells"][0], "level": r["cells"][1],
                             "what": r["cells"][2], "kind": r["cells"][3] if len(r["cells"]) > 3 else "",
                             "priority": r.get("priority"),
                             "links": [src[i] for i in r.get("source_ids", []) if i in src]})
    elif w:
        src = {s["id"]: s for s in w["sources"]}
        for x in w["deadlines_90d"]:
            rows.append({"date": x["date"], "exact": True, "label": fmt(x["date"]),
                         "level": LEVELS.get(x["level"], x["level"]), "what": x["description"],
                         "kind": "Échéance légale" if x["type"] == "legal_deadline" else "Date d’application",
                         "priority": None, "links": [src[x["source_id"]]] if x["source_id"] in src else []})
    return sorted(rows, key=lambda r: (r["date"] or "9999", r["label"]))


# ---------------------------------------------------------------- staging

def stage_reports(reports: list[dict]) -> None:
    out = SITE / "reports"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for r in reports:
        shutil.copy2(REPORTS / r["_pdf"], out / r["_pdf"])


def stage_pdfs(weeks: list[dict]) -> None:
    out = SITE / "briefings"
    if out.exists():
        shutil.rmtree(out)
    for w in weeks:
        dst = out / w["_dir"]
        dst.mkdir(parents=True)
        for f in PDFS:
            shutil.copy2(BRIEFINGS / w["_dir"] / f, dst / f)


# ---------------------------------------------------------------- html pieces

def src_link(s: dict | None, text: str = "source") -> str:
    return f' <a class="src" href="{e(s["url"])}" rel="noopener noreferrer">{e(text)}</a>' if s else ""


def report_link(reports: list[dict], slug: str, text: str) -> str:
    r = latest(reports, slug)
    return f'<a class="more" href="reports/{e(r["_pdf"])}">{e(text)} (PDF)</a>' if r else ""


def reports_list(reports: list[dict]) -> str:
    def li(r):
        title = r["title"].split("|", 1)[-1].strip().capitalize()
        summary = f'<small>{e(r["summary"])}</small>' if r.get("summary") else ""
        return (f'<li><span>{e(title)}<small>{e(r["period"])} · {e(fmt(r["date"]))}</small>{summary}</span>'
                f'<a href="reports/{e(r["_pdf"])}">PDF</a></li>')

    if not reports:
        return '<ul class="list"><li class="muted">Aucun rapport thématique pour le moment.</li></ul>'
    groups = {"overview": [], "daily": [], "other": []}
    seen = set()
    for r in reports:  # newest first; keep only the latest per slug in the main lists
        key = r.get("slug") or r["_pdf"]
        base = "annee" if key.startswith("annee") else key
        if base in seen:
            continue
        seen.add(base)
        groups["overview" if base in OVERVIEW else "daily" if base in DAILY else "other"].append(r)
    shown = [r for g in groups.values() for r in g]
    older = [r for r in reports if r not in shown]
    out = ""
    for k, label in (("overview", "Vue d’ensemble : avant, après, cette année"), ("daily", "Au quotidien au magasin"),
                     ("other", "Paie et droit du travail")):
        if groups[k]:
            out += f'<h3 class="sub-h">{label}</h3><ul class="list">' + "".join(map(li, groups[k])) + "</ul>"
    if older:
        out += ('<details class="older"><summary>Versions précédentes</summary><ul class="list">'
                + "".join(map(li, older)) + "</ul></details>")
    return out


def week_panel(w: dict | None, weeks: list[dict]) -> tuple[str, str]:
    """Returns (cards+items+archive html, downloads html)."""
    if not w:
        return '<p class="muted">Aucune note publiée pour le moment.</p>', ""
    items = {i["id"]: i for i in w["items"]}
    src = {s["id"]: s for s in w["sources"]}
    base = f"briefings/{e(w['_dir'])}"
    downloads = f"""
    <div class="downloads">
      <a class="btn primary" href="{base}/{PDFS[0]}"><b>Actualités</b><span>Ce qui change et impact potentiel · PDF</span></a>
      <a class="btn" href="{base}/{PDFS[1]}"><b>Plan d’action</b><span>Actions priorisées et échéances · PDF</span></a>
    </div>"""
    cards = []
    for t in w["top3"]:
        it = items.get(t["item_id"], {})
        lvl = it.get("level", "")
        cards.append(f"""
      <article class="card {e(t['priority'])}">
        <div class="tag"><span class="pri">{PRI_FR[t['priority']]}</span><span>{e(LEVELS.get(lvl, lvl))}</span></div>
        <h3>{e(t['headline'])}</h3>
        <p>{e(t['why_it_matters'])}</p>
        {f'<p class="meta">{e(it["status"])} · {e(it["effective_date"])}</p>' if it else ''}
      </article>""")
    order = list(LEVELS)
    all_items = []
    for it in sorted(w["items"], key=lambda i: order.index(i["level"]) if i["level"] in order else 99):
        links = " ".join(f'<a href="{e(src[i]["url"])}" rel="noopener noreferrer">[{i}] {e(src[i]["publisher"])}</a>'
                         for i in it["source_ids"] if i in src)
        cons = CONSULT.get(it.get("consultation", "none"), "")
        all_items.append(f"""
      <details class="item">
        <summary><span class="lvl">{e(LEVELS.get(it['level'], it['level']))}</span>{e(it['topic'])}
          <small>{e(it['status'])} · {e(it['effective_date'])}</small></summary>
        <p><b>Ce qui change :</b> {e(it['what_changed'])}</p>
        <p class="impact"><b>Impact potentiel :</b> {e(it['potential_impact'])}</p>
        {f'<p class="meta"><b>Concertation :</b> {cons}</p>' if cons else ''}
        <p class="meta"><b>Pertinence :</b> {e(' | '.join(it['relevance_tags']))}</p>
        <p class="meta"><b>Sources :</b> {links}</p>
      </details>""")
    if not all_items:
        all_items.append(f'<p class="muted">{e(w.get("quiet_week_note") or "Aucun point cette semaine.")}</p>')
    quiet = (f'<p class="muted note">{e(w["quiet_week_note"])}</p>' if w.get("quiet_week_note") and w["items"] else "")
    archive = "".join(
        f'<li><span>{e(span(a["window"]))}</span>'
        f'<a href="briefings/{e(a["_dir"])}/{PDFS[0]}">Actualités</a>'
        f'<a href="briefings/{e(a["_dir"])}/{PDFS[1]}">Plan d’action</a></li>'
        for a in weeks[1:]) or '<li class="muted">Les semaines précédentes apparaîtront ici.</li>'
    example = ('<p class="example">DONNÉES D’EXEMPLE – aperçu de la mise en page.</p>' if w.get("example") else "")
    body = f"""{example}
    <h2>Les 3 points clés</h2>
    <div class="cards">{''.join(cards)}
    </div>
    <h2>Tous les points de la semaine <small>touchez pour ouvrir</small></h2>
    <div class="items">{''.join(all_items)}
    </div>
    {quiet}
    <h2>Semaines précédentes</h2>
    <ul class="list">{archive}</ul>"""
    return body, downloads


def transport_panel(t: dict | None, reports: list[dict]) -> str:
    live = """
    <h2>Trains SNCB en ce moment <small id="live-time"></small></h2>
    <div class="live" id="live">
      <label class="toggle"><input type="checkbox" id="live-bxl" checked> Seulement autour de Bruxelles</label>
      <ul class="list" id="live-list"><li class="muted">Chargement des perturbations SNCB…</li></ul>
      <details class="older" id="live-planned-wrap"><summary>Travaux planifiés SNCB</summary><ul class="list" id="live-planned"></ul></details>
      <p class="muted small">Données en direct : iRail (API ouverte basée sur les données SNCB). En cas de doute, vérifiez sur sncb.be.</p>
    </div>"""
    if not t:
        return live + '<p class="muted">Aucune perturbation annoncée enregistrée.</p>'
    src = t["_src"]
    ann = []
    for a in sorted(t.get("announced", []), key=lambda a: a["start"]):
        ann.append(f"""
      <article class="event{' social' if SOCIAL.search(a['title'] + ' ' + a['detail']) else ''}" data-start="{e(a['start'])}" data-end="{e(a['end'])}">
        <div class="when">{e(fmt_range(a['start'], a['end']))}</div>
        <div><span class="op">{e(a['operator'])}</span> <span class="status">{e(a['status'])}</span>
          <h3>{e(a['title'])}</h3><p>{e(a['detail'])}{src_link(src.get(a['source_id']))}</p></div>
      </article>""")
    access = "".join(
        f'<li><span>{e(x["mode"])} · {e(x["lines"])}<small>{e(x["note"])}</small></span>'
        f'{src_link(src.get(x.get("source_id")), "source")}</li>' for x in t.get("access", []))
    links = "".join(
        f'<li><span>{e(x["label"])}<small>{e(x["why"])}</small></span>'
        f'<a href="{e(x["url"])}" rel="noopener noreferrer">Ouvrir</a></li>' for x in t.get("links", []))
    rep = report_link(reports, "transport", "Grève ou retard : quelles règles de paie ? Le rapport complet")
    return f"""
    <h2>Grèves et travaux annoncés</h2>
    <div class="events" id="announced">{''.join(ann) or '<p class="muted">Rien d’annoncé pour l’instant.</p>'}
    </div>
    <p class="muted small">Liste vérifiée au {e(fmt(t['updated']))}, mise à jour chaque lundi. Les dates passées disparaissent d’elles-mêmes.</p>
    {rep}
    {live}
    <h2>Suivre en direct</h2>
    <ul class="list">{links}</ul>
    <h2>Accès au magasin (Porte de Namur)</h2>
    <ul class="list">{access}</ul>"""


def holidays_panel(c: dict | None) -> str:
    if not c:
        return '<p class="muted">Calendrier non disponible.</p>'
    src = c["_src"]
    ph = "".join(
        f'<li class="hol" data-date="{e(h["date"])}"><span>{e(h["name"])}<small>{e(h.get("note") or "")}</small></span>'
        f'<b class="d">{e(fmt(h["date"], weekday=True))}</b><em class="cd"></em></li>'
        for h in sorted(c.get("public_holidays", []), key=lambda h: h["date"]))
    ph_src = {h["source_id"] for h in c.get("public_holidays", [])}
    ph_links = " ".join(src_link(src.get(i), src[i]["publisher"]) for i in sorted(ph_src) if i in src)
    rr = c.get("replacement_rule")
    rule = (f'<p class="guide-p"><b>Jour férié un dimanche ?</b> {e(rr["text"])}{src_link(src.get(rr["source_id"]))}</p>'
            if rr else "")
    school = []
    for code, name in COMMUNITIES.items():
        rows = [s for s in c.get("school_holidays", []) if s["community"] == code]
        if not rows:
            continue
        lis = "".join(
            f'<li class="range" data-start="{e(s["start"])}" data-end="{e(s["end"])}"><span>{e(s["name"])}</span>'
            f'<b class="d">{e(fmt_range(s["start"], s["end"]))}</b>{src_link(src.get(s["source_id"]))}</li>'
            for s in sorted(rows, key=lambda s: s["start"]))
        school.append(f'<details class="older" {"open" if code == "fr" else ""}><summary>{e(name)}</summary>'
                      f'<ul class="list">{lis}</ul></details>')
    peaks = "".join(
        f'<li class="range" data-start="{e(p["start"])}" data-end="{e(p["end"])}"><span>{e(p["name"])} '
        f'<i class="status">{e(p["status"])}</i><small>{e(p.get("note") or "")}</small></span>'
        f'<b class="d">{e(fmt_range(p["start"], p["end"]))}</b>{src_link(src.get(p["source_id"]))}</li>'
        for p in sorted(c.get("retail_peaks", []), key=lambda p: p["start"]))
    return f"""
    <h2>Prochains jours fériés</h2>
    <ul class="list" id="holidays">{ph}</ul>
    <p class="muted small">Sources :{ph_links}</p>
    {rule}
    <a class="cal" href="conges.ics">Ajouter jours fériés, vacances scolaires et temps forts à mon agenda (.ics)</a>
    <h2>Temps forts du commerce</h2>
    <ul class="list">{peaks}</ul>
    <h2>Vacances scolaires 2026-2027 <small>utile pour les étudiants et les demandes de congé</small></h2>
    {''.join(school)}
    <p class="muted small">Calendrier vérifié au {e(fmt(c['updated']))}.</p>"""


def deadlines_panel(rows: list[dict], reports: list[dict]) -> str:
    lis = []
    for r in rows:
        pri = f'<span class="pri pri-{e(r["priority"])}">{PRI_FR[r["priority"]]}</span> ' if r["priority"] else ""
        links = " ".join(f'<a href="{e(s["url"])}" rel="noopener noreferrer">{e(s["publisher"])}</a>' for s in r["links"])
        lis.append(f'<li class="dl" data-date="{e(r["date"] or "")}" data-exact="{1 if r["exact"] else 0}">'
                   f'<b class="d">{e(r["label"])}</b>{pri}'
                   f'<p>{e(r["what"])}</p><small>{e(r["level"])} · {e(r["kind"])}{" · " + links if links else ""}</small></li>')
    if not lis:
        lis.append('<li class="muted">Aucune échéance identifiée.</li>')
    rep = report_link(reports, "deadlines", "Le rapport complet avec le détail de chaque échéance")
    return f"""
    <h2>Échéances légales et dates d’application <small>les dates passées sont masquées</small></h2>
    <ul class="list" id="deadlines">{''.join(lis)}</ul>
    <a class="cal" href="echeances.ics">Ajouter ces échéances à mon agenda (.ics)</a>
    {rep}"""


GUIDE = """
    <h2>Mode d’emploi</h2>
    <div class="guide">
      <p><b>Chaque lundi</b>, la semaine écoulée (lundi–dimanche) est analysée : législation fédérale et régionale, paie et sécurité sociale, CCT (dont la CP 311), jurisprudence, Bruxelles. Deux PDF en sortent :</p>
      <ul>
        <li><b>Actualités</b> : ce qui change, le statut, la date d’effet et l’impact potentiel, sans tâches. À transmettre tel quel.</li>
        <li><b>Plan d’action</b> : ce qu’il faut faire, dans quel ordre, avec un responsable et une échéance interne <i>proposés</i>. Les dates légales sont indiquées à part.</li>
      </ul>
      <p class="legend"><span class="pri pri-RED">ROUGE</span> action requise (souvent la paie du mois) · <span class="pri pri-AMBER">ORANGE</span> préparer avant une date légale ou une concertation · <span class="pri pri-GREEN">VERT</span> suivre.</p>
      <p><b>Onglets</b> : <i>Transport</i> (grèves annoncées, trains en direct, liens STIB, De Lijn, TEC), <i>Congés</i> (jours fériés, vacances scolaires, soldes), <i>Échéances</i> (dates légales, à ajouter à l’agenda), <i>Rapports</i> (fiches pratiques en PDF).</p>
      <p><b>Sur téléphone</b> : menu du navigateur → « Ajouter à l’écran d’accueil » pour l’ouvrir comme une application.</p>
      <p>Chaque fait renvoie à une source officielle ou professionnelle cliquable ; les annonces non adoptées sont signalées comme telles. L’impact potentiel est une évaluation et non un avis juridique.</p>
    </div>"""

LINKS = "\n    <h2>Sites officiels</h2>\n    <ul class=\"list\">" + "".join(
    f'<li><span>{e(n)}<small>{e(why)}</small></span><a href="{e(u)}" rel="noopener noreferrer">Ouvrir</a></li>'
    for n, u, why in OFFICIAL) + "</ul>"


def render(weeks, reports, transport, conges) -> str:
    w = weeks[0] if weeks else None
    week_body, downloads = week_panel(w, weeks)
    rows = deadline_rows(reports, w)
    today = dt.date.today().isoformat()
    next_dl = next((r for r in rows if r["date"] and r["exact"] and r["date"] >= today), None)
    next_hol = next((h for h in sorted((conges or {}).get("public_holidays", []), key=lambda h: h["date"])
                     if h["date"] >= today), None)
    ann_live = [a for a in sorted((transport or {}).get("announced", []), key=lambda a: a["start"]) if a["end"] >= today]
    next_ann = next((a for a in ann_live if SOCIAL.search(a["title"] + " " + a["detail"])), None) or         next(iter(ann_live), None)
    tiles = f"""
    <div class="tiles">
      <a class="tile" href="#transport"><small>Trains SNCB · Bruxelles</small><b id="tile-live">…</b><span>perturbation(s) en cours</span></a>
      <a class="tile" href="#transport"><small>Prochaine grève / action</small><b>{e(fmt(next_ann['start'], year=False)) if next_ann else '—'}</b><span>{e(next_ann['title']) if next_ann else 'rien d’annoncé'}</span></a>
      <a class="tile" href="#conges"><small>Prochain jour férié</small><b>{e(fmt(next_hol['date'], year=False)) if next_hol else '—'}</b><span>{e(next_hol['name']) if next_hol else ''}</span></a>
      <a class="tile" href="#echeances"><small>Prochaine échéance</small><b>{e(fmt(next_dl['date'], year=False)) if next_dl else '—'}</b><span>{e(next_dl['what'][:90] + ('…' if len(next_dl['what']) > 90 else '')) if next_dl else ''}</span></a>
    </div>"""
    heading = f"Semaine du {e(span(w['window']))}" if w else "Radar RH Belgique"
    built = dt.datetime.now(dt.timezone(dt.timedelta(hours=1))).strftime("%d/%m/%Y")
    body = f"""
  <header class="top">
    <p class="eyebrow">Radar RH Belgique</p>
    <h1>{heading}</h1>
    <p class="sub">Droit social, paie et RH en Belgique, avec un accent sur le commerce de détail (CP 311) et Bruxelles.</p>
  </header>
  <nav class="tabs" role="tablist">
    <a href="#semaine" role="tab">Semaine</a><a href="#transport" role="tab">Transport</a><a href="#conges" role="tab">Congés</a><a href="#echeances" role="tab">Échéances</a><a href="#rapports" role="tab">Rapports</a><a href="#infos" role="tab">Infos</a>
  </nav>
  <section class="panel" id="semaine" role="tabpanel">
    <h2 class="sr">En un coup d’œil</h2>
    {tiles}
    {downloads}
    {week_body}
  </section>
  <section class="panel" id="transport" role="tabpanel">{transport_panel(transport, reports)}
  </section>
  <section class="panel" id="conges" role="tabpanel">{holidays_panel(conges)}
  </section>
  <section class="panel" id="echeances" role="tabpanel">{deadlines_panel(rows, reports)}
  </section>
  <section class="panel" id="rapports" role="tabpanel">
    <h2>Rapports thématiques</h2>
    {reports_list(reports)}
  </section>
  <section class="panel" id="infos" role="tabpanel">{GUIDE}{LINKS}
  </section>
  <footer>L’impact potentiel est une évaluation et non un avis juridique. L’applicabilité dépend de l’entité, de la commission paritaire, du personnel et de la CCT applicable. Site généré le {built}.</footer>"""
    title = f"Radar RH Belgique – {e(span(w['window']))}" if w else "Radar RH Belgique"
    return PAGE.replace("{title}", title).replace("{body}", body)


# ---------------------------------------------------------------- calendars

def _esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    out, b = [], line.encode("utf-8")
    while len(b) > 73:
        cut = 73
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b[cut:]
    out.append(b.decode("utf-8"))
    return "\r\n ".join(out)


def ics(name: str, events: list[dict], alarm_days: int | None = 7) -> str:
    """events: {start, end (inclusive), summary, desc, url, uid}"""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Radar RH Belgique//FR", "CALSCALE:GREGORIAN",
             _fold("X-WR-CALNAME:" + _esc(name))]
    for ev in events:
        a, b = d(ev["start"]), d(ev["end"])
        lines += ["BEGIN:VEVENT", f"UID:{ev['uid']}@radar-rh-belgique", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{a:%Y%m%d}", f"DTEND;VALUE=DATE:{b + dt.timedelta(days=1):%Y%m%d}",
                  _fold("SUMMARY:" + _esc(ev["summary"])), _fold("DESCRIPTION:" + _esc(ev["desc"]))]
        if ev.get("url"):
            lines.append(_fold("URL:" + ev["url"]))
        if alarm_days:
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Rappel", f"TRIGGER:-P{alarm_days}D", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def deadline_events(rows: list[dict]) -> list[dict]:
    return [{"start": r["date"], "end": r["date"], "uid": f"dl-{r['date']}-{k}",
             "summary": r["what"][:120], "desc": f"{r['kind']} – {r['level']}. {r['what']}",
             "url": r["links"][0]["url"] if r["links"] else ""}
            for k, r in enumerate(rows) if r["date"] and r["exact"]]


def holiday_events(c: dict) -> list[dict]:
    src = c["_src"]
    ev = []
    for h in c.get("public_holidays", []):
        ev.append({"start": h["date"], "end": h["date"], "uid": f"ph-{h['date']}",
                   "summary": f"Jour férié : {h['name']}", "desc": h.get("note") or "Jour férié légal.",
                   "url": src.get(h["source_id"], {}).get("url", "")})
    for s in c.get("school_holidays", []):
        ev.append({"start": s["start"], "end": s["end"], "uid": f"sh-{s['community']}-{s['start']}",
                   "summary": f"Vacances scolaires ({s['community'].upper()}) : {s['name']}",
                   "desc": COMMUNITIES.get(s["community"], s["community"]),
                   "url": src.get(s["source_id"], {}).get("url", "")})
    for p in c.get("retail_peaks", []):
        ev.append({"start": p["start"], "end": p["end"], "uid": f"rp-{p['start']}-{abs(hash(p['name'])) % 10000}",
                   "summary": p["name"], "desc": f"{p['status']}. {p.get('note') or ''}",
                   "url": src.get(p["source_id"], {}).get("url", "")})
    return ev


# ---------------------------------------------------------------- page

PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#1F2A44">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="icon-192.png">
<meta name="apple-mobile-web-app-title" content="Radar RH">
<title>{title}</title>
<style>
:root {
  --bg: #f6f7f9; --panel: #ffffff; --ink: #1d2433; --muted: #5b6475; --rule: #dfe3ea;
  --navy: #1F2A44; --teal: #3FB8AF; --teal-ink: #1f7f78; --teal-fill: #E8F6F5;
  --red: #C0392B; --amber: #B7791F; --green: #2F855A;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #10151f; --panel: #182030; --ink: #e7ebf2; --muted: #9aa5b8; --rule: #2a3447;
          --teal-ink: #5fd0c7; --teal-fill: #15302f; --red: #ef7a6c; --amber: #e3b25b; --green: #6cc795; }
}
* { box-sizing: border-box; }
html { scroll-padding-top: 64px; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 860px; margin: 0 auto; padding: 0 16px 48px; }
.top { background: var(--navy); color: #fff; margin: 0 -16px; padding: 24px 16px 18px; }
.eyebrow { margin: 0; color: var(--teal); font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
h1 { margin: 6px 0 4px; font-size: 24px; line-height: 1.2; }
.sub { margin: 0; color: #c9d2e3; font-size: 14px; }
.tabs { position: sticky; top: 0; z-index: 5; display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none;
  margin: 0 -16px; padding: 8px 12px; background: var(--navy); border-bottom: 3px solid var(--teal); }
.tabs::-webkit-scrollbar { display: none; }
.tabs a { flex: 0 0 auto; color: #c9d2e3; text-decoration: none; font-weight: 600; font-size: 15px;
  padding: 10px 14px; border-radius: 999px; min-height: 44px; display: flex; align-items: center; }
.tabs a[aria-selected="true"] { background: var(--teal); color: #0d1b2a; }
.tabs a:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
.js .panel { display: none; } .js .panel.on { display: block; }
.panel { padding-top: 4px; }
h2 { font-size: 13px; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin: 28px 0 10px; }
h2 small { text-transform: none; letter-spacing: 0; font-weight: 400; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.sub-h { font-size: 16px; margin: 22px 0 8px; }
.example { border: 2px solid var(--red); color: var(--red); font-weight: 700; padding: 10px 12px; border-radius: 8px; }
.tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 16px; }
.tile { display: flex; flex-direction: column; gap: 2px; background: var(--panel); border: 1px solid var(--rule);
  border-radius: 12px; padding: 12px; text-decoration: none; color: var(--ink); min-height: 96px; }
.tile small { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.tile b { font-size: 22px; line-height: 1.2; }
.tile span { font-size: 13px; color: var(--muted); line-height: 1.35; }
.tile.alert { border-color: var(--red); } .tile.alert b { color: var(--red); }
.downloads { display: grid; gap: 10px; margin-top: 14px; }
.btn { display: block; padding: 14px 16px; border-radius: 12px; text-decoration: none; color: var(--ink);
  background: var(--panel); border: 1px solid var(--rule); min-height: 64px; }
.btn b { display: block; font-size: 17px; }
.btn span { color: var(--muted); font-size: 14px; }
.btn.primary { background: var(--teal); border-color: var(--teal); color: #0d1b2a; }
.btn.primary span { color: #0d1b2a; opacity: .8; }
.cards { display: grid; gap: 10px; }
.card { background: var(--panel); border: 1px solid var(--rule); border-left: 5px solid var(--teal); border-radius: 10px; padding: 14px 16px; }
.card.RED { border-left-color: var(--red); } .card.AMBER { border-left-color: var(--amber); } .card.GREEN { border-left-color: var(--green); }
.card h3 { margin: 6px 0; font-size: 17px; line-height: 1.3; }
.card p { margin: 0; }
.card .meta { margin-top: 8px; color: var(--muted); font-size: 14px; }
.tag { display: flex; gap: 10px; font-size: 12px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
.RED .pri { color: var(--red); } .AMBER .pri { color: var(--amber); } .GREEN .pri { color: var(--green); }
.pri { font-weight: 700; font-size: 12px; letter-spacing: .06em; }
.pri-RED { color: var(--red); } .pri-AMBER { color: var(--amber); } .pri-GREEN { color: var(--green); }
.table-wrap { overflow-x: auto; background: var(--panel); border: 1px solid var(--rule); border-radius: 10px; }
table { width: 100%; border-collapse: collapse; font-size: 15px; }
th { text-align: left; font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); padding: 10px 12px; border-bottom: 1px solid var(--rule); }
td { padding: 10px 12px; border-bottom: 1px solid var(--rule); vertical-align: top; }
tr:last-child td { border-bottom: 0; }
tr.past { display: none; }
td.date { white-space: nowrap; font-weight: 700; width: 1%; }
.kind { display: block; color: var(--muted); font-size: 13px; margin-top: 2px; }
a { color: inherit; }
td a, .src, .item a, .more, .cal { color: var(--teal-ink); }
.src { font-size: 13px; white-space: nowrap; }
.list { list-style: none; padding: 0; margin: 0; background: var(--panel); border: 1px solid var(--rule); border-radius: 10px; }
.list li { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 14px; padding: 12px 14px; border-bottom: 1px solid var(--rule); }
.list li:last-child { border-bottom: 0; }
.list span { flex: 1 1 200px; font-weight: 600; }
.list a { color: var(--teal-ink); font-weight: 600; padding: 4px 0; }
.list small { display: block; font-weight: 400; color: var(--muted); font-size: 13px; }
.list .d { font-weight: 700; white-space: nowrap; }
.list li.dl { display: block; }
.list li.dl .d { display: inline-block; margin-right: 8px; }
.list li.dl p { margin: 4px 0; font-weight: 400; }
.list li.dl small { display: block; }
.list li.dl small a { padding: 0; font-weight: 600; }
.list .cd { font-style: normal; font-size: 13px; color: var(--teal-ink); font-weight: 700; }
.list li.soon { background: var(--teal-fill); }
.list li.now { background: var(--teal-fill); box-shadow: inset 4px 0 0 var(--teal); }
.list li.past { display: none; }
.status { display: inline-block; font-style: normal; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: var(--muted); border: 1px solid var(--rule); border-radius: 999px; padding: 1px 8px; }
.muted { color: var(--muted); }
.small { font-size: 13px; }
.note { font-size: 14px; margin-top: 10px; }
.cal, .more { display: inline-block; margin-top: 12px; font-weight: 600; min-height: 44px; padding: 10px 0; }
.more { display: block; }
.items { display: grid; gap: 8px; }
.item { background: var(--panel); border: 1px solid var(--rule); border-radius: 10px; padding: 0 14px; }
.item summary { cursor: pointer; padding: 12px 0; font-weight: 600; }
.item summary small { display: block; font-weight: 400; color: var(--muted); font-size: 13px; }
.item .lvl { display: inline-block; margin-right: 8px; font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--teal-ink); }
.item p { margin: 0 0 10px; }
.item .impact { background: var(--teal-fill); border-left: 3px solid var(--teal); padding: 8px 10px; border-radius: 4px; }
.item .meta { color: var(--muted); font-size: 14px; }
.older { margin-top: 10px; }
.older summary { cursor: pointer; font-weight: 600; padding: 10px 0; min-height: 44px; }
.events { display: grid; gap: 8px; }
.event { display: grid; grid-template-columns: 1fr; gap: 4px; background: var(--panel); border: 1px solid var(--rule);
  border-left: 5px solid var(--amber); border-radius: 10px; padding: 12px 14px; }
.event.social { border-left-color: var(--red); }
.event.social .op::after { content: ' · ACTION SOCIALE'; color: var(--red); }
.event.now .when::after { content: ' · en cours'; color: var(--teal-ink); font-weight: 600; }
.event.past { display: none; }
.event .when { font-weight: 700; }
.event .op { font-weight: 700; color: var(--teal-ink); font-size: 13px; }
.event h3 { margin: 4px 0; font-size: 16px; }
.event p { margin: 0; font-size: 15px; }
.live .toggle { display: flex; align-items: center; gap: 8px; min-height: 44px; font-size: 15px; }
.live .toggle input { width: 20px; height: 20px; }
.live li p { margin: 4px 0 0; font-size: 14px; color: var(--muted); flex-basis: 100%; }
.guide { background: var(--panel); border: 1px solid var(--rule); border-radius: 10px; padding: 4px 16px; }
.guide ul { padding-left: 20px; }
.guide-p { background: var(--panel); border: 1px solid var(--rule); border-radius: 10px; padding: 12px 14px; font-size: 15px; }
footer { margin-top: 36px; color: var(--muted); font-size: 13px; }
@media (min-width: 640px) {
  .tiles { grid-template-columns: repeat(4, 1fr); }
  .downloads { grid-template-columns: 1fr 1fr; }
  .cards { grid-template-columns: repeat(3, 1fr); }
  .event { grid-template-columns: 170px 1fr; gap: 14px; }
  h1 { font-size: 30px; }
}
</style>
</head>
<body><main>{body}
</main>
<script>
(function () {
  document.documentElement.classList.add('js');
  var ids = ['semaine', 'transport', 'conges', 'echeances', 'rapports', 'infos'];
  document.addEventListener('click', function (ev) {
    var a = ev.target.closest && ev.target.closest('a[href^="#"]'); if (!a) return;
    var id = a.getAttribute('href').slice(1); if (ids.indexOf(id) < 0) return;
    ev.preventDefault();
    try { history.pushState(null, '', '#' + id); } catch (err) {}
    show(id); window.scrollTo(0, 0);
  });
  window.addEventListener('popstate', function () { show(); });
  function show(force) {
    var h = force || location.hash.slice(1); if (ids.indexOf(h) < 0) h = 'semaine';
    ids.forEach(function (id) { document.getElementById(id).classList.toggle('on', id === h); });
    document.querySelectorAll('.tabs a').forEach(function (a) {
      var on = a.getAttribute('href') === '#' + h; a.setAttribute('aria-selected', on);
      if (on && a.scrollIntoView) a.scrollIntoView({block: 'nearest', inline: 'center'});
    });
  }
  window.addEventListener('hashchange', function () { show(); });
  show();

  // Dates: hide what is over, highlight what is current or close.
  function iso(d) { return d.toISOString().slice(0, 10); }
  var now = new Date(); var today = iso(new Date(now.getTime() - now.getTimezoneOffset() * 60000));
  function days(a) { return Math.round((new Date(a) - new Date(today)) / 86400000); }
  document.querySelectorAll('[data-end]').forEach(function (el) {
    var end = el.getAttribute('data-end'), start = el.getAttribute('data-start') || '';
    if (end < today) el.classList.add('past');
    else if (start && start <= today) el.classList.add('now');
  });
  document.querySelectorAll('.event[data-end]').forEach(function (el) {
    var t = el.querySelector('.when'); if (!t || el.classList.contains('past')) return;
  });
  document.querySelectorAll('li.hol').forEach(function (el) {
    var n = days(el.getAttribute('data-date')), cd = el.querySelector('.cd');
    if (n < 0) { el.classList.add('past'); return; }
    cd.textContent = n === 0 ? "aujourd’hui" : n === 1 ? 'demain' : 'dans ' + n + ' jours';
    if (n <= 14) el.classList.add('soon');
  });
  document.querySelectorAll('#deadlines li[data-date]').forEach(function (tr) {
    var dd = tr.getAttribute('data-date'); if (!dd) return;
    var exact = tr.getAttribute('data-exact') === '1';
    if (exact ? dd < today : dd.slice(0, 7) < today.slice(0, 7)) tr.classList.add('past');
  });

  // Live SNCB disruptions (iRail open API).
  var BXL = /brux|brus|bxl|etterbeek|schaerbeek|schaarbeek|jette|uccle|ukkel|anderlecht|evere|forest|vorst|boitsfort|bosvoorde|watermael|zaventem|halle|vilvoorde|ottignies|louvain|leuven|nivelles|braine|waterloo|denderleeuw|liedekerke|mechelen|malines|alost|aalst|dilbeek|merode|schuman|luxembourg|luxemburg|midi|zuid|nord|noord|central|centraal|toute|ensemble|national|grève|staking/i;
  var all = [];
  function li(x) {
    var el = document.createElement('li');
    var s = document.createElement('span'); s.textContent = x.title; el.appendChild(s);
    var t = document.createElement('small'); t.className = 'd';
    var dt = new Date(Number(x.timestamp) * 1000);
    t.textContent = dt.toLocaleString('fr-BE', {weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
    el.appendChild(t);
    var p = document.createElement('p'); p.textContent = (x.description || '').split('\\n')[0]; el.appendChild(p);
    if (x.link) { var a = document.createElement('a'); a.href = x.link; a.rel = 'noopener noreferrer'; a.textContent = 'Détail SNCB'; el.appendChild(a); }
    return el;
  }
  function draw() {
    var only = document.getElementById('live-bxl').checked;
    var live = all.filter(function (x) { return x.type !== 'planned' && (!only || BXL.test(x.title + ' ' + x.description)); });
    var planned = all.filter(function (x) { return x.type === 'planned' && (!only || BXL.test(x.title + ' ' + x.description)); });
    var ul = document.getElementById('live-list'); ul.innerHTML = '';
    if (!live.length) { var e = document.createElement('li'); e.className = 'muted'; e.textContent = 'Aucune perturbation SNCB signalée' + (only ? ' autour de Bruxelles' : '') + '.'; ul.appendChild(e); }
    live.forEach(function (x) { ul.appendChild(li(x)); });
    var pl = document.getElementById('live-planned'); pl.innerHTML = '';
    planned.forEach(function (x) { pl.appendChild(li(x)); });
    document.querySelector('#live-planned-wrap summary').textContent = 'Travaux planifiés SNCB (' + planned.length + ')';
    var bx = all.filter(function (x) { return x.type !== 'planned' && BXL.test(x.title + ' ' + x.description); }).length;
    var tile = document.getElementById('tile-live'); tile.textContent = bx;
    if (bx > 0) tile.parentNode.classList.add('alert');
  }
  document.getElementById('live-bxl').addEventListener('change', draw);
  fetch('https://api.irail.be/v1/disturbances/?format=json&lang=fr')
    .then(function (r) { if (!r.ok) throw r; return r.json(); })
    .then(function (d) {
      all = d.disturbance || []; draw();
      document.getElementById('live-time').textContent = 'mis à jour à ' + new Date().toLocaleTimeString('fr-BE', {hour: '2-digit', minute: '2-digit'});
    })
    .catch(function () {
      document.getElementById('live-list').innerHTML = '<li class="muted">Données en direct indisponibles. <a href="https://www.belgiantrain.be/fr/travel-info/current-traffic">Voir l’info trafic SNCB</a></li>';
      document.getElementById('tile-live').textContent = '?';
    });
})();
</script>
</body>
</html>
"""

MANIFEST = {
    "name": "Radar RH Belgique", "short_name": "Radar RH", "lang": "fr", "start_url": "./", "scope": "./",
    "display": "standalone", "background_color": "#1F2A44", "theme_color": "#1F2A44",
    "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}],
}


def build() -> Path:
    weeks = load()
    reports = load_reports()
    transport = load_data("transport")
    conges = load_data("conges")
    stage_pdfs(weeks)
    stage_reports(reports)
    out = SITE / "index.html"
    out.write_text(render(weeks, reports, transport, conges), encoding="utf-8")
    (SITE / "manifest.webmanifest").write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = deadline_rows(reports, weeks[0] if weeks else None)
    for name, title, events in (
            ("echeances.ics", "Radar RH Belgique – échéances", deadline_events(rows)),
            ("conges.ics", "Radar RH Belgique – congés et temps forts", holiday_events(conges) if conges else [])):
        p = SITE / name
        if events:
            p.write_bytes(ics(title, events, alarm_days=7 if name == "echeances.ics" else 3).encode("utf-8"))
        elif p.exists():
            p.unlink()
    print(f"ok  site/index.html ({len(weeks)} week(s), {len(reports)} report(s), "
          f"transport={'yes' if transport else 'no'}, conges={'yes' if conges else 'no'})")
    return out


if __name__ == "__main__":
    build()
