import type { ReactNode } from "react";

import { BellMark } from "../../ui/BellMark";

/*
 * Line drawings for the install guide (docs/UX.md §3 "Installed app", §7 "Fridge door"): a phone
 * in ink on paper, with the spot to tap circled by a green marker loop (the basil marker color).
 * - They are decorative (the step text carries the meaning), so every drawing is aria-hidden.
 * - Colors come only from token classes, so both themes work; there is no inline style.
 * - Every drawing shares one 96×160 box drawn at 1:1, so a stroke width is in CSS pixels.
 */

type Kind = "iphone" | "android";

interface Loop {
  cx: number;
  cy: number;
  rx: number;
  ry: number;
  /** Degrees; a hand-drawn loop is rarely level. */
  tilt?: number;
}

/** Where the loop starts: an angle (degrees, clockwise from 3 o'clock) and a radius scale. */
const LOOP_START: readonly [number, number] = [-125, 0.86];
/** Where it goes: a little lopsided, round once, then past its start with a flick outwards. */
const LOOP_NODES: readonly (readonly [number, number])[] = [
  [-35, 1.04],
  [55, 0.97],
  [145, 1.04],
  [235, 1.05],
  [270, 1.1],
  [305, 1.27],
];

/** A target circled quickly with a marker, as one path of cubic Béziers (same input, same path). */
function markerLoop({ cx, cy, rx, ry, tilt = -8 }: Loop): string {
  const turn = (tilt * Math.PI) / 180;
  // A point on the unit circle, pushed `ahead` along the clockwise tangent, then stretched to the
  // ellipse, tilted and moved to the centre.
  const at = (deg: number, scale: number, ahead = 0) => {
    const a = (deg * Math.PI) / 180;
    const u = rx * scale * (Math.cos(a) - ahead * Math.sin(a));
    const v = ry * scale * (Math.sin(a) + ahead * Math.cos(a));
    const x = cx + u * Math.cos(turn) - v * Math.sin(turn);
    const y = cy + u * Math.sin(turn) + v * Math.cos(turn);
    return `${x.toFixed(1)} ${y.toFixed(1)}`;
  };
  let [fromDeg, fromScale] = LOOP_START;
  let d = `M${at(fromDeg, fromScale)}`;
  for (const [toDeg, toScale] of LOOP_NODES) {
    // Handle length for a circular arc of this sweep.
    const k = (4 / 3) * Math.tan(((toDeg - fromDeg) * Math.PI) / 720);
    d += ` C${at(fromDeg, fromScale, k)} ${at(toDeg, toScale, -k)} ${at(toDeg, toScale)}`;
    [fromDeg, fromScale] = [toDeg, toScale];
  }
  return d;
}

/** The phone: body and screen, what's on it, camera and home bar, then the marker loop on top. */
function Phone({
  kind,
  dim = false,
  loop,
  children,
}: {
  kind: Kind;
  /** A darker screen, for a page behind a sheet. */
  dim?: boolean;
  loop: Loop;
  children: ReactNode;
}) {
  return (
    <svg
      viewBox="0 0 96 160"
      width="96"
      height="160"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <rect
        x="6"
        y="4"
        width="84"
        height="152"
        rx={kind === "iphone" ? "17" : "12"}
        className={`${dim ? "fill-counter" : "fill-paper"} stroke-ink`}
        strokeWidth="2.5"
      />
      {children}
      {kind === "iphone" ? (
        <rect x="38.5" y="10" width="19" height="6" rx="3" className="fill-ink" />
      ) : (
        <circle cx="48" cy="11" r="2.5" className="fill-ink" />
      )}
      <path d="M39 150h18" className="stroke-ink" strokeWidth="2" strokeLinecap="round" />
      <path
        d={markerLoop(loop)}
        className="marker-basil stroke-[var(--marker)]"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** A web page: a heading and a few lines of text, quiet on purpose. */
function Page({ y, lines = [64, 58, 62, 36] }: { y: number; lines?: number[] }) {
  return (
    <g className="fill-rule">
      <rect x="16" y={y} width="34" height="7" rx="3.5" />
      {lines.map((width, i) => (
        <rect key={i} x="16" y={y + 14 + i * 8} width={width} height="4" rx="2" />
      ))}
    </g>
  );
}

/** iPhone, step 1: Safari's bar at the bottom (iOS 26): back, the address, and •••, circled. */
export function SafariBarArt() {
  return (
    <Phone kind="iphone" loop={{ cx: 74, cy: 132, rx: 11.5, ry: 11 }}>
      <Page y={26} />
      <Page y={78} lines={[60, 64, 30]} />
      <circle cx="19" cy="132" r="7" className="fill-paper stroke-ink-soft" strokeWidth="1.5" />
      <path
        d="M20.7 128.8 17.5 132l3.2 3.2"
        className="stroke-ink-soft"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect
        x="29.5"
        y="125"
        width="34"
        height="14"
        rx="7"
        className="fill-paper stroke-ink-soft"
        strokeWidth="1.5"
      />
      <rect x="37.5" y="130.5" width="18" height="3" rx="1.5" className="fill-ink-soft" />
      <circle cx="74" cy="132" r="7" className="fill-paper stroke-ink" strokeWidth="1.75" />
      <g className="fill-ink">
        <circle cx="70.8" cy="132" r="1.15" />
        <circle cx="74" cy="132" r="1.15" />
        <circle cx="77.2" cy="132" r="1.15" />
      </g>
    </Phone>
  );
}

/** The middle of the Add to Home Screen row in the share sheet. */
const ADD_ROW = 131;

/** iPhone, step 2: the share sheet, with the Add to Home Screen row (a plus in a square) circled. */
export function ShareSheetArt() {
  return (
    <Phone kind="iphone" dim loop={{ cx: 48, cy: ADD_ROW, rx: 34, ry: 10, tilt: -3 }}>
      <Page y={26} lines={[64]} />
      <rect
        x="10"
        y="50"
        width="76"
        height="97"
        rx="12"
        className="fill-paper stroke-ink-soft"
        strokeWidth="1.5"
      />
      <g className="fill-rule">
        <rect x="17" y="57" width="11" height="11" rx="3" />
        <rect x="32" y="58" width="30" height="4" rx="2" />
        <rect x="32" y="64" width="20" height="3" rx="1.5" />
        <circle cx="22.5" cy="82" r="5.5" />
        <circle cx="39.5" cy="82" r="5.5" />
        <circle cx="56.5" cy="82" r="5.5" />
        <circle cx="73.5" cy="82" r="5.5" />
        <rect x="19" y="97" width="20" height="4" rx="2" />
        <rect x="19" y="111" width="28" height="4" rx="2" />
      </g>
      <g className="stroke-rule" strokeWidth="1">
        <path d="M19 106h58" />
        <path d="M19 120h58" />
      </g>
      <g className="stroke-ink-soft" strokeWidth="1.25">
        <rect x="69" y="95.5" width="7" height="7" rx="1.5" />
        <circle cx="72.5" cy="113" r="3.5" />
      </g>
      <rect x="19" y={ADD_ROW - 2} width="34" height="4" rx="2" className="fill-ink" />
      <g className="stroke-ink" strokeWidth="1.4" strokeLinecap="round">
        <rect x="68.5" y={ADD_ROW - 4} width="8" height="8" rx="2" />
        <path d={`M72.5 ${ADD_ROW - 1.8}v3.6M70.7 ${ADD_ROW}h3.6`} />
      </g>
    </Phone>
  );
}

const ICON_X = [12.5, 31.5, 50.5, 69.5];
const ICON_Y = [24, 45, 66, 87];
const DOCK_X = [14.6, 32.2, 49.8, 67.4];
/** Dinner Bell's place on the home screen: second row, third column. */
const BELL = { x: 50.5, y: 45 };

/** Step 3 on both phones: a home screen, with the Dinner Bell icon circled. */
export function HomeScreenArt({ kind }: { kind: Kind }) {
  return (
    <Phone kind={kind} loop={{ cx: BELL.x + 7, cy: BELL.y + 7, rx: 13.5, ry: 13.5 }}>
      <g className="fill-rule">
        {ICON_Y.flatMap((y) =>
          ICON_X.map((x) =>
            x === BELL.x && y === BELL.y ? null : (
              <rect key={`${x} ${y}`} x={x} y={y} width="14" height="14" rx="4" />
            ),
          ),
        )}
      </g>
      <rect x="11" y="125" width="74" height="22" rx="9" className="fill-counter stroke-rule" />
      <g className="fill-rule">
        {DOCK_X.map((x) => (
          <rect key={x} x={x} y="129" width="14" height="14" rx="4" />
        ))}
      </g>
      {/* A nested viewport places the mark; it fills it, as it has no size of its own. */}
      <svg x={BELL.x} y={BELL.y} width="14" height="14">
        <BellMark />
      </svg>
    </Phone>
  );
}

/** The top of Chrome on Android: the address and the tab count (the ⋮ menu is drawn per step). */
function ChromeBar() {
  return (
    <>
      <rect
        x="13"
        y="18"
        width="37"
        height="14"
        rx="7"
        className="fill-paper stroke-ink-soft"
        strokeWidth="1.5"
      />
      <circle cx="19.5" cy="25" r="2" className="fill-ink-soft" />
      <rect x="24" y="23.5" width="18" height="3" rx="1.5" className="fill-ink-soft" />
      <rect
        x="56"
        y="19.5"
        width="11"
        height="11"
        rx="2.5"
        className="stroke-ink-soft"
        strokeWidth="1.5"
      />
    </>
  );
}

/** Android, step 1: Chrome's bar at the top, with the ⋮ menu circled. */
export function ChromeBarArt() {
  const menu = { x: 77.5, y: 25 };
  return (
    <Phone kind="android" loop={{ cx: menu.x, cy: menu.y, rx: 7.5, ry: 11.5 }}>
      <ChromeBar />
      <g className="fill-ink">
        <circle cx={menu.x} cy={menu.y - 4.5} r="1.3" />
        <circle cx={menu.x} cy={menu.y} r="1.3" />
        <circle cx={menu.x} cy={menu.y + 4.5} r="1.3" />
      </g>
      <Page y={44} />
      <Page y={96} lines={[60, 64, 30]} />
    </Phone>
  );
}

/** The middle of the Install app row in Chrome's menu, and the rows around it. */
const INSTALL_ROW = 103;
const MENU_ROWS = [
  { y: 38, width: 22 },
  { y: 48, width: 28 },
  { y: 58, width: 16 },
  { y: 68, width: 26 },
  { y: 78, width: 20 },
  { y: 88, width: 24 },
  { y: 118, width: 18 },
  { y: 128, width: 24 },
];

/** Android, step 2: Chrome's menu, with the Install app row (a phone) circled. */
export function ChromeMenuArt() {
  return (
    <Phone kind="android" loop={{ cx: 56, cy: INSTALL_ROW, rx: 21, ry: 8, tilt: -3 }}>
      <ChromeBar />
      <Page y={44} />
      <Page y={96} lines={[60, 64, 30]} />
      <rect
        x="34"
        y="14"
        width="52"
        height="126"
        rx="7"
        className="fill-paper stroke-ink-soft"
        strokeWidth="1.5"
      />
      <g className="fill-rule">
        {[42, 51, 60, 69, 78].map((cx) => (
          <circle key={cx} cx={cx} cy="23" r="2.2" />
        ))}
        {MENU_ROWS.map(({ y, width }) => (
          <g key={y}>
            <rect x="40" y={y - 2.25} width="4.5" height="4.5" rx="1.2" />
            <rect x="49" y={y - 1.75} width={width} height="3.5" rx="1.75" />
          </g>
        ))}
      </g>
      <path d="M38 31h44" className="stroke-rule" strokeWidth="1" />
      <rect
        x="40.25"
        y={INSTALL_ROW - 3.5}
        width="4"
        height="7"
        rx="1"
        className="stroke-ink"
        strokeWidth="1.25"
      />
      <rect x="49" y={INSTALL_ROW - 1.75} width="22" height="3.5" rx="1.75" className="fill-ink" />
    </Phone>
  );
}
