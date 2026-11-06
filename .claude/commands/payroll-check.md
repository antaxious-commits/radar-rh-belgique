---
description: Changements de paie belges de ce mois et du mois prochain – 1 PDF
argument-hint: "[précisions facultatives]"
---
Following CLAUDE.md (Belgium only, French output), list every payroll-relevant change taking effect this month and next month: précompte professionnel, indexation per commission paritaire (and the cap above 4 000 EUR), RMMMG / bonus à l'emploi, ONSS contributions and reductions, salaire garanti / incapacité, chèques-repas / éco-chèques, mobility, pécule de vacances, regional measures. $ARGUMENTS
For each: level, effective date, what changes, RED/AMBER/GREEN, what payroll must verify, source. Add a short section "Aucun changement identifié" for areas searched without result, and a payroll sign-off order.
Write reports/payroll_<today>.json matching radar/report_schema.json with title "RH BELGIQUE | CONTRÔLE DE PAIE" and a one-sentence `summary`, build it with `python -m radar.build_report <file>`, verify the PDF, and give me a 3-line summary.
