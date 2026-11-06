---
description: Analyse approfondie d'un thème ou d'une région belge – 30 derniers jours + 90 prochains jours – 1 PDF
argument-hint: "<thème ou région>  ex. Flandre, licenciement, voiture de société"
---
Following CLAUDE.md, produce a deep dive (in French, Belgium only) on: $ARGUMENTS (if empty, ask me which theme or region).
Cover all material developments in the last 30 days (legislation, Moniteur belge publications, rulings, CCT, payroll parameters, strikes, immigration), the statutory deadlines in the next 90 days, and "Ce que cela signifie pour le HRBP" (3–5 concrete actions). Keep original legal terms in [brackets].
Write reports/deep-dive-<theme-slug>_<today>.json matching radar/report_schema.json with title "RH BELGIQUE | APPROFONDISSEMENT <THÈME>" and a one-sentence `summary`, build it with `python -m radar.build_report <file>`, verify the PDF, and summarise in 3 lines.
