---
description: Toutes les échéances légales RH belges des 90 prochains jours – 1 PDF
argument-hint: "[période facultative]"
---
Following CLAUDE.md (Belgium only, French output), list every Belgian statutory HR and employment-law deadline or effective date in the next 90 days (or the period in $ARGUMENTS), across federal and regional levels, including items announced earlier (1er janvier changes, indexations, temporary measures ending 31 décembre, consultation deadlines for the conseil d'entreprise / CPPT / délégation syndicale).
One table sorted by date with columns: Date, Niveau, Quoi, Type (échéance légale / date d'application), with a priority (RED/AMBER/GREEN) and source_ids on each row.
Write reports/deadlines_<today>.json matching radar/report_schema.json with title "RH BELGIQUE | ÉCHÉANCES À 90 JOURS" and a one-sentence `summary`, build it with `python -m radar.build_report <file>`, verify the PDF, and summarise the 3 nearest deadlines.
