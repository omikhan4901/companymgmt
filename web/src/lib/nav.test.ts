import { safeNext } from "./nav";

describe("safeNext", () => {
  it("keeps same-site paths", () => {
    expect(safeNext("/app/people?tab=departments")).toBe("/app/people?tab=departments");
  });
  it("rejects other sites", () => {
    for (const bad of ["//evil.example", "https://evil.example", "/\\evil.example", "javascript:alert(1)", null, ""]) {
      expect(safeNext(bad)).toBe("/app");
    }
  });
});
