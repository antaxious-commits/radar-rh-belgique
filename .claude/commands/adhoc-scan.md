---
description: Scan ponctuel sur une période et des niveaux au choix – 2 PDF, non publiés (défaut : 30 derniers jours, toute la Belgique)
argument-hint: "[jours] [niveaux]  ex. 30 flandre wallonie"
---
Run an ad-hoc Radar RH Belgique scan following CLAUDE.md (Belgium only, French output).
Period and levels: $ARGUMENTS. If empty: the last 30 days, all levels (federal, Flanders, Wallonia, Brussels, German-speaking Community).
Write briefings/adhoc_<today>/briefing.json (window = the chosen period), build both PDFs with `python -m radar.weekly --input briefings/adhoc_<today>/briefing.json --no-site`, verify them, and give me a 3-line summary in French. Ad-hoc scans are not shown on the website; do not publish unless I ask.
