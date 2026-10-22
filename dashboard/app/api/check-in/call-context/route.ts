import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const session = await auth0.getSession();
  if (!session) return NextResponse.json({ detail: "Sign in required" }, { status: 401 });
  let body: { caller_phone?: unknown };
  try { body = await request.json() as { caller_phone?: unknown }; } catch { return NextResponse.json({ detail: "A caller number is required" }, { status: 422 }); }
  if (typeof body.caller_phone !== "string") return NextResponse.json({ detail: "A caller number is required" }, { status: 422 });
  try {
    return NextResponse.json(await backendJson("/check-in/call-context", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caller_phone: body.caller_phone }) }));
  } catch (error) {
    const detail = error instanceof BackendRequestError ? error.detail : "Call context is unavailable";
    const status = error instanceof BackendRequestError ? error.status : 503;
    return NextResponse.json({ detail }, { status });
  }
}
