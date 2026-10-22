import { NextResponse } from "next/server";

import { BackendRequestError, backendJson } from "@/lib/server-api";

type Context = { params: Promise<{ id: string }> };

function failure(error: unknown) {
  if (error instanceof BackendRequestError) return NextResponse.json({ detail: error.detail }, { status: error.status });
  return NextResponse.json({ detail: "Checklist service is unavailable" }, { status: 502 });
}

export async function GET(_: Request, { params }: Context) {
  try {
    const { id } = await params;
    return NextResponse.json(await backendJson(`/checklists/${encodeURIComponent(id)}`));
  } catch (error) {
    return failure(error);
  }
}

export async function PATCH(request: Request, { params }: Context) {
  try {
    const { id } = await params;
    const body = await request.json();
    return NextResponse.json(await backendJson(`/checklists/${encodeURIComponent(id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }));
  } catch (error) {
    return failure(error);
  }
}
