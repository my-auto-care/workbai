import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const session = await auth0.getSession();
  if (!session) return NextResponse.json({ detail: "Sign in required" }, { status: 401 });
  let body: { query?: unknown };
  try { body = await request.json() as { query?: unknown }; } catch { return NextResponse.json({ detail: "Enter at least two characters" }, { status: 422 }); }
  const query = typeof body.query === "string" ? body.query.trim() : "";
  if (query.length < 2 || query.length > 100) return NextResponse.json({ detail: "Enter at least two characters" }, { status: 422 });
  try {
    return NextResponse.json(await backendJson("/check-in/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }) }));
  } catch (error) {
    const detail = error instanceof BackendRequestError ? error.detail : "Customer lookup is unavailable";
    const status = error instanceof BackendRequestError ? error.status : 503;
    return NextResponse.json({ detail }, { status });
  }
}
