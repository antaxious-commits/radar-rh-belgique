---
description: Contrôles avant paie pour un magasin CP 311 – checklist mensuelle, entrées/sorties, absences, RGPD – 1 PDF
argument-hint: "[précisions facultatives]"
---
Following CLAUDE.md (Belgium only, French output; never name the reader or the employer), update the practical guide for the monthly pre-payroll check in a CP 311 store (the reader checks hours, presences, absences and contracts before the payroll provider runs pay). $ARGUMENTS
Sections: monthly checklist table (Contrôle | Pourquoi | Règle / seuil | Source) – part-time extra hours, overtime, variable schedules, Sunday/holiday work, students and Dimona STU, flexi-jobs, absence codes, guaranteed salary and medical certificates, new hires/leavers, éco-chèques/transport; start-of-employment checklist; end-of-employment checklist; absences and sickness; GDPR retention and access; "Points non vérifiés".
Every fact needs a fresh external source opened in this run (never a repo file). Write reports/pre-paie_<today>.json matching radar/report_schema.json with title "RH BELGIQUE | CONTRÔLES AVANT PAIE" and a one-sentence `summary`, build it with `python -m radar.build_report <file>`.
