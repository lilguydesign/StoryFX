import { parseRequest, type Release, validRelease } from "./contract.ts";

export function createHandler(resolve: (version: string) => Promise<Release>) {
  return async (request: Request): Promise<Response> => {
    const headers = new Headers({
      "Cache-Control": "no-store, max-age=0", "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer", "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS", "Content-Type": "application/json; charset=UTF-8",
    });
    const error = (status: number, code: string) => new Response(
      request.method === "HEAD" ? null : JSON.stringify({ ok: false, code }), { status, headers },
    );
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers });
    if (!["GET", "HEAD"].includes(request.method)) return error(405, "METHOD_NOT_ALLOWED");
    const parsed = parseRequest(new URL(request.url));
    if (!parsed) return error(400, "INVALID_DOWNLOAD_REQUEST");
    let release: Release;
    try {
      release = await resolve(parsed.version);
      if (!validRelease(release)) return error(503, "RELEASE_UNAVAILABLE");
    } catch {
      return error(503, "RELEASE_UNAVAILABLE");
    }
    if (parsed.metadata) {
      return new Response(request.method === "HEAD" ? null : JSON.stringify({
        ok: true, product: "storyfx", ...release, mode: "diagnostic_only", publishing_enabled: false,
      }), { status: 200, headers });
    }
    headers.set("Location", release.download_url);
    return new Response(null, { status: 302, headers });
  };
}
