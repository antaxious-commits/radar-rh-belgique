---
description: Quels changements récents exigent une information-consultation des organes de concertation – confirmé ou conditionnel – 1 PDF
argument-hint: "[liste de sujets facultative]"
---
Following CLAUDE.md (Belgium only, French output), take the items from the latest briefing in briefings/ (or $ARGUMENTS if given) and assess which ones require or may require information or consultation of Belgian employee representatives: conseil d'entreprise, CPPT, délégation syndicale (and the European works council where relevant).
Separate: CONSULTATION LÉGALE CONFIRMÉE / OBLIGATION CONDITIONNELLE (depends on entity, thresholds, technology, CCT) / AUCUNE.
Verify each conclusion with a fresh external legal source (never cite the briefing itself). Write reports/works-council_<today>.json matching radar/report_schema.json with title "RH BELGIQUE | ORGANES DE CONCERTATION" and a one-sentence `summary`, build it with `python -m radar.build_report <file>`, verify the PDF, and summarise in 3 lines.
