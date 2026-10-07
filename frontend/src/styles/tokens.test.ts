/**
 * Every text/background token pair must meet WCAG AA (4.5:1) in both themes
 * (docs/UX.md §7.2). Reads the real tokens.css, so a color change can't slip through.
 */
import { describe, expect, it } from "vitest";

import css from "./tokens.css?raw";

function block(source: string, start: number): string {
  const open = source.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === "{") depth++;
    if (source[i] === "}") depth--;
    if (depth === 0) return source.slice(open + 1, i);
  }
  throw new Error("unbalanced braces");
}

function tokens(source: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const match of source.matchAll(/--([a-z-]+):\s*(#[0-9a-f]{6})\s*;/gi)) {
    const [, name, value] = match;
    if (name && value) out[name] = value;
  }
  return out;
}

const light = tokens(block(css, css.indexOf(":root")));
const darkMedia = block(css, css.indexOf("(prefers-color-scheme: dark)"));
const dark = { ...light, ...tokens(block(darkMedia, darkMedia.indexOf(":root"))) };

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

const TEXT = ["ink", "ink-soft", "basil", "tomato"];
const SURFACES = ["paper", "counter"];
const MARKERS = ["basil", "tomato", "carrot", "eggplant", "beet", "olive", "cocoa", "plum"];

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme", (_name, theme) => {
  const color = (name: string) => {
    const value = theme[name];
    if (!value) throw new Error(`missing token --${name}`);
    return value;
  };

  it.each(TEXT.flatMap((text) => SURFACES.map((surface) => [text, surface])))(
    "%s text on %s passes AA",
    (text, surface) => {
      expect(contrast(color(text), color(surface))).toBeGreaterThanOrEqual(4.5);
    },
  );

  it.each(MARKERS.flatMap((marker) => SURFACES.map((surface) => [marker, surface])))(
    "marker %s on %s passes AA",
    (marker, surface) => {
      expect(contrast(color(`marker-${marker}`), color(surface))).toBeGreaterThanOrEqual(4.5);
    },
  );

  it("button and tag text pass AA", () => {
    expect(contrast(color("on-basil"), color("basil"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(color("on-lemon"), color("lemon"))).toBeGreaterThanOrEqual(4.5);
  });
});
