---
description: Cette année par rapport à l'an dernier – montants et droits clés (RMMMG, CP 311, étudiants, flexi-jobs, préavis, maladie, chèques) – 1 PDF
argument-hint: "[année facultative]"
---
Following CLAUDE.md (Belgium only, French output; never name the reader or the employer), build a side-by-side reference of key amounts and rights for the current year vs the previous year, plus next year where officially known. $ARGUMENTS
Cover: RMMMG; CP 311 barèmes and indexation; student work (hours, contributions); flexi-jobs (cap, sectors, minimum wage); overtime (voluntary hours, sursalaire); notice periods and outplacement; sickness (certificates, guaranteed salary, relapse, solidarity contribution, reintegration); holidays and pécule; précompte (quotité exemptée), bonus à l'emploi; éco-chèques, chèques-repas, transport and bike allowances, telework allowance; pensions; opening hours and Sunday work.
Main table Sujet | <année-1> | <année> | <année+1 si connu> with priority and source_ids, grouped in 4–6 sections; "Ce que cela change pour le magasin"; "Points non vérifiés". Never invent a figure: write "Non vérifié".
Every number needs a fresh external source opened in this run (never a repo file). Write reports/annee-<year>_<today>.json matching radar/report_schema.json with title "RH BELGIQUE | <ANNÉE> PAR RAPPORT À <ANNÉE-1>" and a one-sentence `summary`, build it with `python -m radar.build_report <file>`.
