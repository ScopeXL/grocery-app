import { beforeEach, describe, expect, it } from "vitest";

import { clockOffset, nextTimestamp, recordClockSample, resetClockForTests } from "./clock";

beforeEach(() => {
  resetClockForTests();
});

describe("clock offset", () => {
  it("uses the lowest-latency sample", () => {
    recordClockSample(1000, 1400, 5000); // slow: offset 3800, round trip 400
    recordClockSample(2000, 2020, 5_010); // fast: offset 3000, round trip 20
    expect(clockOffset()).toBe(3000);
  });

  it("ignores impossible samples", () => {
    recordClockSample(2000, 1000, 5000);
    recordClockSample(1000, 1010, Number.NaN);
    expect(clockOffset()).toBe(0);
  });

  it("issues strictly increasing timestamps, even if the clock steps back", () => {
    const first = nextTimestamp(10_000);
    const second = nextTimestamp(9_000);
    const third = nextTimestamp(9_000);
    expect(second).toBeGreaterThan(first);
    expect(third).toBeGreaterThan(second);
  });
});
