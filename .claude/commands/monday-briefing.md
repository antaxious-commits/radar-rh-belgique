---
description: Note hebdomadaire Belgique pour la semaine lun.–dim. écoulée – 2 PDF + mise à jour du site
argument-hint: "[période facultative, ex. 2026-11-02]"
---
Run the weekly Radar RH Belgique following CLAUDE.md (Belgium only, all output in French).
1. Compute the preceding completed Monday–Sunday week in Europe/Brussels (`python -m radar.weekly --print-window`), or use this period if given: $ARGUMENTS.
2. Research Belgium (federal, Flanders, Wallonia, Brussels, German-speaking Community) with fresh external sources, searching in French and Dutch, and write briefings/<start>_<end>/briefing.json matching radar/schema.json.
3. Run `python -m radar.weekly --start <start>` to build "RH BELGIQUE | ACTUALITÉS" and "RH BELGIQUE | PLAN D'ACTION" and rebuild the site.
4. Verify both PDFs (look at the PNG renders; the build already checks "?", missing glyphs and fonts).
5. Give me a 3-line Top 3 summary in French. Ask before committing and pushing (skip asking when run as a scheduled routine).
