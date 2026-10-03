export const platform = "storyfx_agent_android";
export const channel = "stable";
export const publicPrefix = "https://api.formafx.com/downloads/storyfx-android/";

export type Release = {
  platform: string;
  version: string;
  minimum_version: string;
  version_code: number;
  download_url: string;
  sha256: string;
  byte_size: number;
};

export function validRelease(value: Release): boolean {
  if (value.platform !== platform || !/^\d+\.\d+\.\d+$/.test(value.version) ||
      !/^\d+\.\d+\.\d+$/.test(value.minimum_version) ||
      !Number.isSafeInteger(value.version_code) || value.version_code < 1 ||
      !Number.isSafeInteger(value.byte_size) || value.byte_size < 1 ||
      !/^[a-fA-F0-9]{64}$/.test(value.sha256)) return false;
  return value.download_url === publicPrefix +
    `StoryFX-Android-${value.version}-v${value.version_code}.apk`;
}

export function parseRequest(url: URL): { version: string; metadata: boolean } | null {
  const allowed = new Set(["platform", "channel", "version", "asset_type", "metadata"]);
  for (const key of url.searchParams.keys()) {
    if (!allowed.has(key) || url.searchParams.getAll(key).length !== 1) return null;
  }
  if (url.searchParams.get("platform") !== platform ||
      url.searchParams.get("channel") !== channel ||
      url.searchParams.get("asset_type") !== "apk") return null;
  const version = url.searchParams.get("version");
  if (version !== "latest" && !/^\d+\.\d+\.\d+$/.test(version ?? "")) return null;
  if (url.searchParams.has("metadata") && url.searchParams.get("metadata") !== "1") return null;
  return { version: version!, metadata: url.searchParams.get("metadata") === "1" };
}
