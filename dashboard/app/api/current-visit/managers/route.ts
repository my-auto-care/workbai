import { NextResponse } from "next/server";

import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

function failure(error: unknown) {
  const detail = error instanceof BackendRequestError ? error.detail : "The Current Visit manager service is unavailable";
  const status = error instanceof BackendRequestError ? error.status : 502;
  return NextResponse.json({ detail }, { status });
}

export async function GET() {
  try {
    return NextResponse.json(await backendJson("/current-visit/manager-grants"));
  } catch (error) {
    return failure(error);
  }
}

export async function PUT(request: Request) {
  let body: { user_id?: unknown; active?: unknown };
  try { body = await request.json() as { user_id?: unknown; active?: unknown }; } catch { return NextResponse.json({ detail: "Expected a JSON command" }, { status: 400 }); }
  if (typeof body.user_id !== "string" || typeof body.active !== "boolean") return NextResponse.json({ detail: "A manager user and active state are required" }, { status: 400 });
  try {
    return NextResponse.json(await backendJson("/current-visit/manager-grants", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: body.user_id, active: body.active }) }));
  } catch (error) {
    return failure(error);
  }
}
