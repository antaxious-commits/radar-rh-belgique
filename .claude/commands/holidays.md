---
description: Jours fériés, vacances scolaires (FR, NL, DE) et temps forts du commerce – données du site (onglet Congés + agenda .ics)
argument-hint: "[année scolaire facultative]"
---
Following CLAUDE.md (Belgium only, French output), refresh data/conges.json matching radar/conges_schema.json: the Belgian legal public holidays from today to the end of next year (notes for those falling on a Sunday or Saturday), the replacement-day rule (emploi.belgique.be), the school holidays of the current and next school year for the Fédération Wallonie-Bruxelles, the Flemish Community and the German-speaking Community, and retail peaks (winter and summer sales with their waiting periods, Saint-Nicolas, Black Friday, end-of-year shopping days; status Légal / Usage commercial / Déduit). $ARGUMENTS
Every date needs a fresh external source opened in this run (never a repo file); check every URL loads. Then run `python site/build_site.py`.
