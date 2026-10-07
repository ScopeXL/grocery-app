# ADR 0012: Visual direction "Fridge door"

- **Status:** Accepted (chosen by the owner from two directions); sizes, the action color and motion are superseded by ADR 0027
- **Date:** 2026-10-06

## Context

The brief asked for a warm, food-friendly identity that doesn't look like a template, set with the frontend-design plugin before any UI is built.

**Requirements:**
- phone-first, one-handed use;
- base text of 17 px or more;
- tap targets of 48 px or more;
- WCAG AA contrast;
- light and dark themes.

**Kroger constraints:**
- product photos must be shown uncropped, with no overlays;
- no logo resembling Kroger's (avoid Kroger blue and the oval).

**The look to avoid:** the generic "warm food app": a cream background, a serif display face, a terracotta accent, and a grid of soft-shadowed cards.

**The two directions offered:**
- **"Fridge door":** the shared list on the fridge, with marker colors per person.
- **"Corner market":** aisle-sign plates and shelf tags, in condensed type.

## Decision

"Fridge door" ([UX §7](../UX.md#7-visual-direction-fridge-door)):

- **Concept:** the shared list on the fridge, where everyone writes in their own marker color.
- **Signature, the one bold element:** checking an item draws a slightly wobbly marker stroke through it in the checker's color. The same marker colors show who added something.
- **Palette:**
  - backgrounds: counter `#F3F4F1`, paper `#FFFFFF`;
  - aubergine ink `#2B1D30`;
  - basil `#1E6B45` for actions;
  - lemon `#FFDB3D` for sale tags;
  - tomato `#C2381E` for missed and destructive actions;
  - a matched dark theme, "night kitchen".
- **No blue anywhere.**
- **Type:** Atkinson Hyperlegible Next only, self-hosted, at 400, 600 and 800. It is chosen for legibility at a glance in an aisle.
- **Layout:** ruled paper lists instead of a grid of shadowed cards. Corner radius follows hierarchy. Meta information is stacked on separate lines, not joined with dots, and sentence case is used throughout.
- **Images:** product photos sit on white tiles at `contain`, never cropped and never covered. Household meal photos may be cropped.
- **Enforcement:** a unit test asserts every token text/background pair meets AA in both themes.

## Consequences

- The design is distinctive without hurting legibility. The bold moment is functional: it shows who did what, and when.
- Choosing a single typeface trades some display personality for legibility. That matches the top priority: easy for a non-technical person on a phone.
