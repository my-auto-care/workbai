import { NextResponse } from "next/server";

import { BackendRequestError, publicCurrentVisitJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

function unavailable() {
  return NextResponse.json({ detail: "Visit link is unavailable" }, { status: 404, headers: { "Cache-Control": "no-store, private, max-age=0" } });
}

export async function POST(request: Request) {
  // Nginx owns this header. Its dedicated location overwrites—not appends—the value,
  // and access logging is disabled for both /v and this resolver path.
  if (request.headers.get("x-workbai-public-edge-verified") !== "1") return unavailable();
  let secret: unknown;
  try { secret = (await request.json() as { secret?: unknown }).secret; } catch { return unavailable(); }
  if (typeof secret !== "string" || !/^[A-Za-z0-9_-]{32,256}$/.test(secret)) return unavailable();
  try {
    const payload = await publicCurrentVisitJson(secret, request.headers.get("x-workbai-public-client-ip"));
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store, private, max-age=0", "Referrer-Policy": "no-referrer" } });
  } catch (error) {
    if (error instanceof BackendRequestError && error.status === 429) return NextResponse.json({ detail: "Visit link is unavailable" }, { status: 429, headers: { "Cache-Control": "no-store, private, max-age=0" } });
    return unavailable();
  }
}
