import { addDays, daysBetween, isoWeekday, lastDayOfMonth, startOfWeek } from "./week";

describe("week helpers", () => {
  it("finds the start of a Saturday week (Bangladesh)", () => {
    // 30 Sep 2026 is a Wednesday.
    expect(isoWeekday("2026-09-30")).toBe(3);
    expect(startOfWeek("2026-09-30", 6)).toBe("2026-09-26");
    expect(startOfWeek("2026-09-26", 6)).toBe("2026-09-26");
    expect(startOfWeek("2026-09-30", 1)).toBe("2026-09-28");
  });
  it("crosses months and years", () => {
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(daysBetween("2026-02-27", "2026-03-02")).toEqual(["2026-02-27", "2026-02-28", "2026-03-01", "2026-03-02"]);
  });
  it("finds the last day of a month", () => {
    expect(lastDayOfMonth("2026-09")).toBe("2026-09-30");
    expect(lastDayOfMonth("2026-12")).toBe("2026-12-31");
    expect(lastDayOfMonth("2028-02")).toBe("2028-02-29");
  });
});
