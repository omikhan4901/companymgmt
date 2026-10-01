import { describe, expect, it } from "vitest";

import { fromMinor, toMinor } from "./money";

describe("money inputs", () => {
  it("reads amounts in either script, with or without separators", () => {
    expect(toMinor("20,800")).toBe(2_080_000);
    expect(toMinor("২০৮০০")).toBe(2_080_000);
    expect(toMinor("1250.5")).toBe(125_050);
    expect(toMinor(" ")).toBe(0);
    expect(toMinor("-2")).toBe(-200);
  });

  it("rejects what isn't a number", () => {
    expect(toMinor("12a")).toBeNull();
    expect(toMinor("1.234")).toBeNull();
  });

  it("round-trips for inputs", () => {
    expect(fromMinor(2_080_000)).toBe("20800");
    expect(fromMinor(125_050)).toBe("1250.50");
    expect(fromMinor(null)).toBe("");
  });
});
