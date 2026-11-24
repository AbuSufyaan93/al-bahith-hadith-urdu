---
name: urdu-rtl-visual-qa
description: Audits RTL/BiDi markup, CSS Logical Properties, Noto/Jameel Nastaliq non-clipping line-height, WCAG 2.2 AA contrast (>= 4.5:1), keyboard focus visibility, and >= 48px mobile touch targets on 390x844 and desktop viewports.
---
# Urdu & Arabic RTL, Nastaliq & WCAG 2.2 AA Visual QA Skill

1. Run `python3 .agents/skills/urdu-rtl-visual-qa/scripts/audit_rtl_css.py` to verify CSS logical properties, non-clipping Nastaliq line-height (`>= 2.2`), `:focus-visible` states, and coarse-pointer `>= 48px` touch targets.
2. Verify `<html dir="rtl" lang="ur">` (or `lang="ar"`), `dir="auto"` on search/lexicon inputs, and `<bdi>` around embedded Latin/URL/numeric tokens.
3. Clean up any temporary browser QA screenshots/recordings after gate sign-off (`references/wcag-rtl-checklist.md`).
