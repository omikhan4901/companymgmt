import { describe, expect, it } from "vitest";

import { suggestedName } from "./client";

describe("download names", () => {
  it("uses the server's file name when it's safe", () => {
    expect(suggestedName('attachment; filename="cha-ghor-export-20261001.zip"')).toBe("cha-ghor-export-20261001.zip");
    expect(suggestedName(null)).toBeNull();
    expect(suggestedName('attachment; filename="../../etc/passwd"')).toBeNull();
  });
});
