import { describe, expect, it } from "vitest";

import { suggestItemName, tidyName } from "./itemName";

const CHEDDAR = "Sample Shredded Cheddar Cheese";

describe("item names", () => {
  it("finishes a half-typed last word from the product's name", () => {
    expect(suggestItemName("Shredd", CHEDDAR)).toBe("Shredded");
    expect(suggestItemName("shredded ched", CHEDDAR)).toBe("Shredded cheddar");
    expect(suggestItemName("chee", "Sample Aged Gouda Cheese")).toBe("Cheese");
  });

  it("keeps what was typed when it's whole, done, or not in the name", () => {
    expect(suggestItemName("cheddar", CHEDDAR)).toBe("Cheddar");
    expect(suggestItemName("shredd ", CHEDDAR)).toBe("Shredd"); // a space: the word was done
    expect(suggestItemName("queso", CHEDDAR)).toBe("Queso");
  });

  it("ignores case, accents and punctuation", () => {
    expect(suggestItemName("jalapen", "Sample Sliced Jalapeño Peppers")).toBe("Jalapeño");
    expect(suggestItemName("ground be", "Sample Ground Beef 80% Lean")).toBe("Ground beef");
    expect(suggestItemName("80", "Sample Ground Beef 80% Lean")).toBe("80");
  });

  it("stays within 80 characters and tidies spaces", () => {
    expect(suggestItemName("a".repeat(90), CHEDDAR)).toHaveLength(80);
    expect(tidyName("  two   words ")).toBe("Two words");
  });
});
