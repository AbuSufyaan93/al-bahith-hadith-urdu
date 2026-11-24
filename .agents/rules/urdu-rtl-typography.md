---
description: Enforces W3C RTL/BiDi markup, CSS Logical Properties, non-clipping Nastaliq line-height, and WCAG 2.2 AA accessibility across all HTML, CSS, and JS UI files while preserving 100% hadeeth.com visual parity.
trigger: glob
globs:
  - "**/*.css"
  - "**/*.html"
  - "backend/static/assets/*.js"
---
# Urdu & Arabic RTL, BiDi, Nastaliq & WCAG 2.2 AA Rule

1. **Semantic Directionality**: Keep `dir="rtl"` on `<html>` with dynamic `lang="ur"` / `lang="ar"`. Never rely on CSS `direction` alone for document flow.
2. **CSS Logical Properties**: Use logical properties (`margin-inline-start`, `margin-inline-end`, `padding-inline`, `padding-block`, `border-inline-start`, `inset-inline`, `text-align: start`) instead of physical `left`/`right` in all custom rules.
3. **BiDi Isolation**: Set `dir="auto"` on search/form inputs and wrap embedded Latin tokens, URLs, DOIs, or version strings inside `<bdi>` elements.
4. **Non-Clipping Nastaliq Typography**: Self-host `NotoNastaliqUrdu` / `JameelNooriNastaleeq` / `MehrNastaliqWeb` paired with `Kitab` for vocalized Arabic. Maintain `line-height >= 2.2` and vertical breathing room on Urdu containers; never clip `ک`/`گ` ascenders or descenders with tight `overflow: hidden` or `max-height`.
5. **WCAG 2.2 AA & Mobile Touch**: Guarantee `>= 4.5:1` normal text contrast, `>= 3:1` UI component contrast, visible `:focus-visible` outlines, and `>= 48x48px` coarse-pointer mobile touch targets without altering `https://hadeeth.com/`'s desktop visual geometry.
