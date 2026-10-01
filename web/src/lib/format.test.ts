import { describe, expect, it } from "vitest";

import { formatDay, formatYear, initials, isoToZoned, normalizeDigits, splitMinutes, todayIn, zonedToIso } from "./format";

describe("time zones", () => {
  it("converts Dhaka wall time to UTC and back", () => {
    const iso = zonedToIso("2026-03-10T22:00", "Asia/Dhaka");
    expect(iso).toBe("2026-03-10T16:00:00.000Z");
    expect(isoToZoned(iso, "Asia/Dhaka")).toBe("2026-03-10T22:00");
  });

  it("handles the daylight saving jump in London", () => {
    // 02:30 local doesn't exist on 29 March 2026; before it is GMT, after it BST.
    expect(zonedToIso("2026-03-29T00:30", "Europe/London")).toBe("2026-03-29T00:30:00.000Z");
    expect(zonedToIso("2026-03-29T04:30", "Europe/London")).toBe("2026-03-29T03:30:00.000Z");
    expect(zonedToIso("2026-10-25T12:00", "Europe/London")).toBe("2026-10-25T12:00:00.000Z");
  });

  it("finds today's date in a zone", () => {
    const utcEvening = new Date("2026-05-01T19:30:00Z");
    expect(todayIn("Asia/Dhaka", utcEvening)).toBe("2026-05-02");
    expect(todayIn("America/New_York", utcEvening)).toBe("2026-05-01");
  });

  it("shows calendar dates without shifting them", () => {
    expect(formatDay("2024-02-29")).toContain("29");
  });
});

describe("text helpers", () => {
  it("normalises Bangla digits", () => {
    expect(normalizeDigits("০১৭১১-২৩৪৫৬৭")).toBe("01711-234567");
  });

  it("builds initials from any script", () => {
    expect(initials("Rahim Uddin")).toBe("RU");
    expect(initials("  মোঃ   করিম ")).toBe("মক");
    expect(initials("")).toBe("?");
  });

  it("splits minutes and never goes negative", () => {
    expect(splitMinutes(125)).toEqual({ h: 2, m: 5 });
    expect(splitMinutes(-5)).toEqual({ h: 0, m: 0 });
  });
});

describe("years", () => {
  it("never shows a thousands separator", () => {
    expect(formatYear(2027)).toBe("2027");
  });
});
