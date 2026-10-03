import { createHandler } from "../functions/storyfx-agent-download/handler.ts";
import { createResolver } from "../functions/storyfx-agent-download/release_catalog.ts";
import { type Release } from "../functions/storyfx-agent-download/contract.ts";

const asset: Release = { platform: "storyfx_agent_android", version: "0.2.0", minimum_version: "0.2.0",
  version_code: 2, download_url: "https://api.formafx.com/downloads/storyfx-android/StoryFX-Android-0.2.0-v2.apk",
  sha256: "a".repeat(64), byte_size: 2000000 };
const base = "https://api.formafx.com/functions/v1/storyfx-agent-download?platform=storyfx_agent_android&channel=stable&version=latest&asset_type=apk";
function assert(value: unknown) { if (!value) throw new Error("assertion_failed"); }

Deno.test("latest redirects only to verified StoryFX release, without cache", async () => {
  let requested = "";
  const response = await createHandler(async version => { requested = version; return asset; })(new Request(base));
  assert(requested === "latest" && response.status === 302);
  assert(response.headers.get("Location") === asset.download_url);
  assert(response.headers.get("Cache-Control")?.includes("no-store"));
});
Deno.test("metadata and HEAD expose safe hash/version only", async () => {
  const handler = createHandler(async () => asset);
  const response = await handler(new Request(base + "&metadata=1"));
  const data = await response.json();
  assert(data.sha256 === asset.sha256 && data.publishing_enabled === false);
  const head = await handler(new Request(base, { method: "HEAD" }));
  assert(head.status === 302 && (await head.text()) === "");
});
Deno.test("rejects unknown platforms, duplicate parameters, injection and unsafe assets", async () => {
  const handler = createHandler(async () => asset);
  for (const url of [base.replace("storyfx_agent_android", "android"), base + "&version=0.2.0", base + "&redirect=https://example.invalid"]) {
    assert((await handler(new Request(url))).status === 400);
  }
  assert((await handler(new Request(base, { method: "POST" }))).status === 405);
  const unsafe = createHandler(async () => ({ ...asset, download_url: "https://example.invalid/file.apk" }));
  assert((await unsafe(new Request(base))).status === 503);
});
Deno.test("latest re-reads app_versions and cross-checks release catalog", async () => {
  let calls = 0;
  const resolver = createResolver(name => name === "SUPABASE_URL" ? "https://api.formafx.com" : "synthetic-server-key",
    ((input: RequestInfo | URL) => {
      calls++;
      const url = new URL(String(input));
      const row = url.pathname.endsWith("app_versions") ? {
        platform: asset.platform, latest_version: asset.version, min_version: asset.minimum_version, download_url: asset.download_url,
      } : asset;
      return Promise.resolve(Response.json([row]));
    }) as typeof fetch);
  assert((await resolver("latest")).sha256 === asset.sha256 && calls === 2);
  await resolver("latest");
  assert(calls === 4);
});
