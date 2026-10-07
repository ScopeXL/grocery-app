# ADR 0027: Crisper type, an ink accent, compact targets, and motion that answers taps

- **Status:** Accepted (the owner's choices after a week of use on a phone, 2026-10-07)
- **Date:** 2026-10-07

## Context

After the first week of real use, the owner found the app too big and too green:
- Text and controls felt large everywhere.
- The basil-green buttons, pills and links didn't feel right.
- Nothing moved when tapped, so the app didn't feel like it was doing anything.

Measuring found the cause of the size. The page's base font was 18 px. Tailwind sizes every spacing class from that base, so every button, pill and row rendered 12.5% larger than its class name: a `min-h-14` button was 63 px, not 56.

ADR 0012 set the "Fridge door" direction. This record keeps its concept, palette and signature marker stroke, and changes the sizes, the action color and the motion rules.

## Decision

**Type and base** (supersedes ADR 0012's "base text of 17 px or more"):
- The page base is the browser default: `font-size: 100%`, 16 px on phones. Type tokens are in rem, so a larger default text setting scales everything.
- The scale:

  | Token | Size / line height |
  |---|---|
  | caption | 13 / 18 |
  | secondary | 14 / 20 |
  | body | 16 / 24 |
  | row | 18 / 24 |
  | title | 24 / 30 |
  | total | 30 / 36 |

- Weights are 400, 600, 700 and 800.
- Anything a person types into stays at 16 px or more, so iPhones don't zoom in on it.

**Targets** (supersedes ADR 0012's "48 px or more"):

| Element | Size |
|---|---|
| Primary buttons | 48 px |
| Other buttons, icon buttons, text links | 44 px |
| Chips and segmented options | 40 px |
| List rows | 56 px or more |
| Shopping checkbox | 48 px, in a 72 × 80 px tap area |

All of these are well above WCAG 2.2's 24 px minimum, which the axe checks enforce.

**Action color** (supersedes ADR 0012's "basil for actions"):
- Primary buttons, selected pills, links, progress bars and the focus ring use the ink: `#2B1D30` with white text in light mode, and `#F3ECF4` with `#1A121E` text in dark mode.
- The tokens are named by role (`--accent`, `--on-accent`), with `--accent: var(--ink)`. Any later change is one line.
- Color now comes only from lemon (the bell and sale tags), tomato (missed items, errors and destructive actions), and the family's marker colors. `--marker-basil` stays a person's color.
- Text links that stand alone get an underline, because color no longer marks them. The active tab is a filled pill.
- Still no blue anywhere.

**Motion** (refines UX §7.6):
- Motion answers what someone did:
  - a press scales the control slightly;
  - sheets slide up and away;
  - toasts ease in and out;
  - selections fill;
  - a checked shopping item folds into Done after its marker stroke;
  - rows added later ease in;
  - a total that changes pops once.
- Nothing animates on first paint or when switching tabs.
- **CSS only.** Everything is declared in the build's stylesheet (`styles/motion.css`). Components only toggle attributes (`data-*`, `inert`, `aria-hidden`), change a key, or wait on `getAnimations()` before calling `dialog.close()`. No animation library, no `style={}`, and no `element.animate()`, so ADR 0023's CSP rule holds.
- **Sheets don't use `overlay`/`allow-discrete` for their exit,** because Safari doesn't support `overlay`. The dialog stays open and modal while a keyframe slides it away, then the script closes it.
- **Timing:**

  | Name | Value |
  |---|---|
  | tap | 90 ms |
  | quick | 150 ms |
  | enter | 220 ms |
  | exit | 180 ms |
  | standard easing | `cubic-bezier(.2,0,0,1)` |
  | arrive easing | `cubic-bezier(.05,.7,.1,1)` |
  | leave easing | `cubic-bezier(.3,0,.8,.15)` |

- **Reduce Motion makes all of it instant,** including backdrops, delays and view transitions. Spinners and loading placeholders stop moving.

## Consequences

- Screens hold more, and they read crisper on a phone; the shopping checkbox is still a big target.
- Product photos and lemon sale tags now carry the color, and a person's marker stroke stands out more.
- A unit test checks that every color pair meets AA. Another fails on any `basil` class or inline style. End-to-end tests check that inputs stay at 16 px or more and that controls stay at 40 px or more.
- After a sheet starts closing, the page behind it takes taps again about 180 ms later.
