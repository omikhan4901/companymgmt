import assert from "node:assert/strict";
import crypto from "node:crypto";
import { test } from "node:test";

import { CompanyMgmt, CompanyMgmtError, verifyWebhook } from "./index.ts";

test("verifyWebhook matches the server's signature", async () => {
  const body = '{"id":"1"}';
  const t = 1_700_000_000;
  const v1 = crypto.createHmac("sha256", "whsec_abc").update(`${t}.${body}`).digest("hex");
  assert.equal(await verifyWebhook("whsec_abc", body, `t=${t},v1=${v1}`, 300, t + 10), true);
  assert.equal(await verifyWebhook("whsec_abc", body + " ", `t=${t},v1=${v1}`, 300, t + 10), false);
  assert.equal(await verifyWebhook("whsec_abc", body, `t=${t},v1=${v1}`, 300, t + 1000), false);
});

test("writes retry with the same idempotency key, errors carry the code", async () => {
  const keys: string[] = [];
  let calls = 0;
  const fake = (async (_url: URL, init: RequestInit) => {
    calls++;
    keys.push((init.headers as Record<string, string>)["Idempotency-Key"]);
    if (calls === 1) return new Response("", { status: 503, headers: { "retry-after": "0" } });
    if (calls === 2) return new Response(JSON.stringify({ id: "b1" }), { status: 201, headers: { "content-type": "application/json" } });
    return new Response(JSON.stringify({ status: 422, code: "validation" }), { status: 422 });
  }) as unknown as typeof fetch;
  const cm = new CompanyMgmt({ apiKey: "cmk_x_y", fetch: fake });
  assert.deepEqual(await cm.post("/branches", { name: "Uttara" }), { id: "b1" });
  assert.equal(keys[0], keys[1]);
  await assert.rejects(cm.post("/branches", {}), (e: unknown) => e instanceof CompanyMgmtError && e.code === "validation");
});
