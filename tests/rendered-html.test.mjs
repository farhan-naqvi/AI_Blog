import assert from "node:assert/strict";
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
  assert.match(html, /Verified, not amplified/i);
  assert.match(html, /PRIMARY-SOURCE AI INTELLIGENCE/i);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Starter Project/i);
});

test("server-renders the owner sign-in without private data", async () => {
  const response = await render("/owner-login");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /PRIVATE OWNER WORKSPACE/i);
  assert.doesNotMatch(html, /linkedin_drafts|service.role|SUPABASE_SERVICE_ROLE_KEY/i);
});
