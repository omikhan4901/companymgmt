import { describe, expect, it } from "vitest";

import { suggestedName } from "./client";

describe("download names", () => {
  it("uses the server's file name when it's safe", () => {
    expect(suggestedName('attachment; filename="cha-ghor-export-20261001.zip"')).toBe("cha-ghor-export-20261001.zip");
    expect(suggestedName(null)).toBeNull();
    expect(suggestedName('attachment; filename="../../etc/passwd"')).toBeNull();
  });

  it("prefers the UTF-8 name, so Bangla file names survive", () => {
    const header = "attachment; filename=\"????.pdf\"; filename*=UTF-8''%E0%A6%A8%E0%A7%80%E0%A6%A4%E0%A6%BF.pdf";
    expect(suggestedName(header)).toBe("নীতি.pdf");
    expect(suggestedName("attachment; filename=\"a.pdf\"; filename*=UTF-8''..%2Fevil.pdf")).toBe("a.pdf");
  });
});
