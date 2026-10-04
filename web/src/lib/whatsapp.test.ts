import { describe, expect, it } from "vitest";

import { whatsappLink } from "./whatsapp";

describe("whatsappLink", () => {
  it("turns local Bangladeshi numbers into international ones", () => {
    expect(whatsappLink("01711-000000", "Hi", "BD")).toBe("https://wa.me/8801711000000?text=Hi");
  });
  it("keeps international numbers and reads Bangla digits", () => {
    expect(whatsappLink("+৮৮০১৭১১০০০০০০", "Hi", "BD")).toBe("https://wa.me/8801711000000?text=Hi");
    expect(whatsappLink("0044 20 7946 0000", "Hi", "GB")).toBe("https://wa.me/442079460000?text=Hi");
  });
  it("encodes the message and refuses empty numbers", () => {
    expect(whatsappLink("+8801711000000", "You owe ৳500 & more", "BD")).toContain("text=You%20owe%20%E0%A7%B3500%20%26%20more");
    expect(whatsappLink("  ", "Hi", "BD")).toBeNull();
  });
});
