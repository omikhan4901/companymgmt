import { describe, expect, it } from "vitest";

import { addressFor, slugFromHost } from "./address";

describe("workspace addresses", () => {
  it("reads the workspace from its own address", () => {
    expect(slugFromHost("cha-ghor.companymgmt.app")).toBe("cha-ghor");
    expect(slugFromHost("CHA-GHOR.companymgmt.app:443")).toBe("cha-ghor");
  });
  it("ignores the main site, nested names and other domains", () => {
    expect(slugFromHost("companymgmt.app")).toBeNull();
    expect(slugFromHost("www.companymgmt.app")).toBeNull();
    expect(slugFromHost("a.b.companymgmt.app")).toBeNull();
    expect(slugFromHost("cha-ghor.example.com")).toBeNull();
    expect(slugFromHost("localhost:3000")).toBeNull();
  });
  it("builds the address", () => {
    expect(addressFor("cha-ghor")).toBe("https://cha-ghor.companymgmt.app");
  });
});
