import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request(`http://localhost${path}`, { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the public intelligence overview", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /<title>SignalWatch AI<\/title>/i);
  assert.match(html, /Grounded, not amplified/i);
  assert.match(html, /PRIMARY-SOURCE AI INTELLIGENCE/i);
  assert.match(html, /Sources monitored/i);
  assert.match(html, /Items detected/i);
  assert.match(html, /Developments analysed/i);
  assert.match(html, /Verified public/i);
  assert.match(html, /Reported public/i);
  assert.match(html, /Developing\/private/i);
  assert.match(html, /Major or notable/i);
  assert.match(html, /Incremental/i);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Starter Project/i);
});

test("public sources page uses the safe projection labels", async () => {
  const response = await render("/sources");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /Active public sources|No active public sources/i);
  assert.doesNotMatch(html, /connector_config|poll_interval_minutes|last_error|reliability_level/i);
});

test("public records are uncached and detail separates factual from reported claims", async () => {
  const publicData = await readFile(new URL("../lib/public-data.ts", import.meta.url), "utf8");
  const detail = await readFile(new URL("../app/developments/[slug]/page.tsx", import.meta.url), "utf8");
  assert.match(publicData, /cache:\s*"no-store"/);
  assert.doesNotMatch(publicData, /revalidate:\s*60/);
  assert.match(detail, /Confirmed facts/);
  assert.match(detail, /Source-reported claims/);
  assert.match(detail, /have not necessarily been independently verified/i);
  assert.doesNotMatch(detail, /reported_claims\.map\(.*confirmed_claims/s);
});

test("latest feed exposes evidence, importance, and category filters", async () => {
  const response = await render("/latest");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /All public updates/i);
  assert.match(html, /Verified only/i);
  assert.match(html, /Reported only/i);
  assert.match(html, /Major/i);
  assert.match(html, /Notable/i);
  assert.match(html, /Incremental/i);
  assert.match(html, /Agents and developer tools/i);
  assert.match(html, /Policy, safety and security/i);
  const card = await readFile(new URL("../components/DevelopmentCard.tsx", import.meta.url), "utf8");
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(card, /verification_status/);
  assert.match(card, /evidence-\$\{item\.verification_status\.toLowerCase\(\)\}/);
  assert.match(css, /evidence-reported/);
  assert.match(card, /confirmed facts/);
  assert.match(card, /source-reported claims/);
  const publicData = await readFile(new URL("../lib/public-data.ts", import.meta.url), "utf8");
  assert.match(publicData, /count >= 5/);
});

test("daily page distinguishes a monitoring digest from a briefing", async () => {
  const briefing = await readFile(new URL("../app/briefing/page.tsx", import.meta.url), "utf8");
  assert.match(briefing, /Daily Monitoring Digest/);
  assert.match(briefing, /Daily Intelligence Briefing/);
  assert.match(briefing, /Daily Activity Summary/);
  assert.match(briefing, /zero public developments/);
});

test("server-renders the owner sign-in without private data", async () => {
  const response = await render("/owner-login");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /PRIVATE OWNER WORKSPACE/i);
  assert.doesNotMatch(html, /linkedin_drafts|service.role|SUPABASE_SERVICE_ROLE_KEY/i);
});
