import { NextResponse } from "next/server";

import { BackendRequestError, backendJson } from "@/lib/server-api";

function failure(error: unknown) {
  if (error instanceof BackendRequestError) return NextResponse.json({ detail: error.detail }, { status: error.status });
  return NextResponse.json({ detail: "Checklist service is unavailable" }, { status: 502 });
}

export async function GET() {
  try {
    return NextResponse.json(await backendJson("/checklists"));
  } catch (error) {
    return failure(error);
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    return NextResponse.json(await backendJson("/checklists", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }), { status: 201 });
  } catch (error) {
    return failure(error);
  }
}
