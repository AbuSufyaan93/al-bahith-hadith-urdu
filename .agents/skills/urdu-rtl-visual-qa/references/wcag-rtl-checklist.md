# Mobile (390x844) & Desktop RTL / Nastaliq / WCAG 2.2 AA Checklist

- [x] `<html dir="rtl" lang="ur|ar">` updated dynamically with language toggle.
- [x] Custom CSS uses logical properties (`margin-inline`, `padding-inline`, `border-inline-start`, `inset-inline`).
- [x] `NotoNastaliqUrdu` (variable 400–700) & `JameelNooriNastaleeq` self-hosted; `line-height >= 2.25` with zero `overflow: hidden` clipping on `ک/گ`.
- [x] Normal text contrast `>= 4.5:1` and UI border/badge contrast `>= 3.0:1` in both Light and Dark themes.
- [x] Visible `:focus-visible` ring and `>= 48x48px` mobile touch targets (`@media (pointer: coarse)`).
- [x] Prune temporary browser recording artifacts post-QA to prevent disk bloat.
