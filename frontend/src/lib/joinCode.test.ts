import { describe, expect, it } from "vitest";

import { codeFromHash, displayCode, normalizeCode, spokenCode } from "./joinCode";

describe("add-a-phone codes", () => {
  it("accepts what people type", () => {
    expect(normalizeCode("4F7K9QX2")).toBe("4F7K9QX2");
    expect(normalizeCode("4f7k 9qx2")).toBe("4F7K9QX2");
    expect(normalizeCode(" 4F7K-9QX2 ")).toBe("4F7K9QX2");
  });

  it("refuses what can't be a code", () => {
    expect(normalizeCode("4F7K9QX")).toBeNull(); // too short
    expect(normalizeCode("4F7K9QX0")).toBeNull(); // 0 isn't used: it looks like O
    expect(normalizeCode("")).toBeNull();
  });

  it("reads the code from a QR link and shows it in two groups", () => {
    expect(codeFromHash("#4F7K9QX2")).toBe("4F7K9QX2");
    expect(codeFromHash("")).toBeNull();
    expect(displayCode("4F7K9QX2")).toBe("4F7K 9QX2");
    expect(spokenCode("4F7K9QX2")).toBe("4 F 7 K 9 Q X 2");
  });
});
