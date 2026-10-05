import { describe, expect, it } from "vitest";

import { ARTICLES, searchArticles } from "./articles";

describe("help articles", () => {
  it("have both languages with the same number of steps", () => {
    for (const a of ARTICLES) expect(a.bn.steps.length).toBe(a.en.steps.length);
  });
  it("search across languages", () => {
    expect(searchArticles("passkey", "bn").map((a) => a.id)).toContain("security");
    expect(searchArticles("ছুটি", "bn").map((a) => a.id)).toContain("leave");
    expect(searchArticles("", "en")).toHaveLength(ARTICLES.length);
  });
});
