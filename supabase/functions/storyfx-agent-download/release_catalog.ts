import { platform, type Release, validRelease } from "./contract.ts";

type EnvReader = (name: string) => string | undefined;

export function createResolver(env: EnvReader, fetcher: typeof fetch = fetch) {
  return async (requested: string): Promise<Release> => {
    const base = (env("SUPABASE_URL") ?? "").replace(/\/$/, "");
    const key = env("SUPABASE_SERVICE_ROLE_KEY");
    if (!key || !["http://kong:8000", "https://api.formafx.com"].includes(base)) {
      throw new Error("RELEASE_CONFIG_UNAVAILABLE");
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    const headers = { apikey: key, Authorization: `Bearer ${key}`, accept: "application/json" };
    async function lookup(table: string, parameters: Record<string, string>) {
      const url = new URL(`/rest/v1/${table}`, base);
      for (const [name, value] of Object.entries(parameters)) url.searchParams.set(name, value);
      const response = await fetcher(url, { headers, signal: controller.signal, redirect: "error" });
      if (!response.ok) throw new Error("RELEASE_LOOKUP_FAILED");
      const rows = await response.json();
      if (!Array.isArray(rows) || rows.length !== 1) throw new Error("RELEASE_NOT_FOUND");
      return rows[0];
    }
    try {
      const latest = await lookup("app_versions", {
        platform: `eq.${platform}`, select: "platform,latest_version,min_version,download_url", limit: "1",
      });
      const version = requested === "latest" ? latest.latest_version : requested;
      if (!/^\d+\.\d+\.\d+$/.test(version)) throw new Error("RELEASE_INVALID");
      const asset = await lookup("storyfx_android_releases", {
        version: `eq.${version}`, channel: "eq.stable", select: "version,version_code,download_url,sha256,byte_size", limit: "1",
      });
      const release: Release = { ...asset, platform, minimum_version: latest.min_version };
      if (!validRelease(release) || (requested === "latest" && latest.download_url !== release.download_url)) {
        throw new Error("RELEASE_INVALID");
      }
      return release;
    } finally {
      clearTimeout(timer);
    }
  };
}
