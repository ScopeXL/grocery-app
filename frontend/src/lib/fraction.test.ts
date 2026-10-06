import { describe, expect, it } from "vitest";

import { add, parseFraction, toMixed, toText } from "./fraction";

describe("fractions for the steppers", () => {
  it.each([
    ["3/8", "3/8"],
    ["2", "2"],
    ["0.5", "1/2"],
    ["1 1/2", "3/2"],
    ["16.9", "169/10"],
    [".25", "1/4"],
  ])("reads %s exactly", (text, expected) => {
    const value = parseFraction(text);
    expect(value && toText(value)).toBe(expected);
  });

  it.each(["", ".", "1/0", "half", "-1", "1e3", "1.2.3"])("refuses %j", (text) => {
    expect(parseFraction(text)).toBeNull();
  });

  it("steps by halves without drifting", () => {
    let value = parseFraction("1/2");
    const step = parseFraction("1/2");
    if (!value || !step) throw new Error("parse failed");
    for (let i = 0; i < 5; i++) value = add(value, step);
    expect(toMixed(value)).toBe("3");
    expect(toMixed(add(value, step))).toBe("3 1/2");
  });
});
