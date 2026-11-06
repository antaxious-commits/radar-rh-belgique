"""Optional: email both PDFs with the Top 3 in the body via Resend (stdlib only).

Env: RESEND_API_KEY, TO_EMAIL (comma-separated allowed), FROM_EMAIL (optional,
must be a sender on a domain verified in Resend; default onboarding@resend.dev,
which Resend only delivers to the account owner's own address), SITE_URL (optional).

Usage:  python -m radar.send_email briefings/2026-11-02_2026-11-08
"""
from __future__ import annotations

import base64
import html
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from radar.build_pdfs import ACTION_PDF, NEWS_PDF, long_date

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        print(__doc__)
        return 2
    folder = ROOT / argv[0]
    b = json.loads((folder / "briefing.json").read_text(encoding="utf-8"))
    window = f"du {long_date(b['window']['start'])} au {long_date(b['window']['end'])}"
    e = html.escape

    top3 = "".join(
        f"<li><b style='color:{ {'RED': '#C0392B', 'AMBER': '#B7791F', 'GREEN': '#2F855A'}[t['priority']] }'>"
        f"{ {'RED': 'ROUGE', 'AMBER': 'ORANGE', 'GREEN': 'VERT'}[t['priority']] }</b> <b>{e(t['headline'])}</b><br>{e(t['why_it_matters'])}</li>"
        for t in b["top3"]
    )
    site = os.environ.get("SITE_URL", "")
    body = (
        f"<p>Radar RH Belgique, semaine {e(window)}.</p><p><b>Les 3 points clés</b></p><ol>{top3}</ol>"
        "<p>Les deux PDF sont joints (Actualités et Plan d’action).</p>"
        + (f"<p>Archives : <a href='{e(site)}'>{e(site)}</a></p>" if site else "")
    )
    attachments = [
        {"filename": f, "content": base64.b64encode((folder / f).read_bytes()).decode()}
        for f in (NEWS_PDF, ACTION_PDF)
    ]
    payload = {
        "from": os.environ.get("FROM_EMAIL") or "Radar RH Belgique <onboarding@resend.dev>",
        "to": [x.strip() for x in os.environ["TO_EMAIL"].split(",") if x.strip()],
        "subject": f"Radar RH Belgique | semaine {window}",
        "html": body,
        "attachments": attachments,
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "Content-Type": "application/json",
                 "User-Agent": "hr-europe-radar"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"ok  email sent: {r.read().decode()}")
    except urllib.error.HTTPError as err:
        print(f"ERROR: Resend returned {err.code}: {err.read().decode()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
