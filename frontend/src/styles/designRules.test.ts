/**
 * House rules that are easy to break by accident. Reads every source file as text.
 * - No inline styles: the CSP blocks them (ADR 0023).
 * - Nothing still painted with the retired basil action color (ADR 0027). `marker-basil`, a
 *   person's marker color, is a different thing and stays.
 */
import { describe, expect, it } from "vitest";

const sources = import.meta.glob<string>(
  ["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../api/schema.d.ts"],
  { query: "?raw", import: "default", eager: true },
);

function offenders(pattern: RegExp): string[] {
  return Object.entries(sources)
    .filter(([, text]) => pattern.test(text))
    .map(([path]) => path);
}

describe("design rules", () => {
  it("reads the sources as text", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(50);
    expect(Object.values(sources).every((text) => typeof text === "string")).toBe(true);
    expect(offenders(/export function Button\(/)).toEqual(["../ui/Button.tsx"]);
  });

  it("uses no inline styles (ADR 0023)", () => {
    expect(offenders(/\sstyle=\{/)).toEqual([]);
  });

  it("paints actions with the accent, not basil (ADR 0027)", () => {
    expect(
      offenders(/\b(bg|text|border|stroke|fill|outline|ring|decoration)-(on-)?basil\b/),
    ).toEqual([]);
  });
});
