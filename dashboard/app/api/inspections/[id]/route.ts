import { NextResponse } from "next/server";

import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ id: string }> };
type Command =
  | { action: "start" }
  | { action: "submit" }
  | { action: "record"; item_id: string; condition: "good" | "poor" | "na"; note?: string; measurement?: string; selected_option?: string };

function validId(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

export async function POST(request: Request, { params }: Context) {
  const { id } = await params;
  if (!validId(id)) return NextResponse.json({ detail: "Invalid inspection identifier" }, { status: 400 });

  let body: Command;
  try {
    body = (await request.json()) as Command;
  } catch {
    return NextResponse.json({ detail: "Expected a JSON command" }, { status: 400 });
  }

  try {
    if (body.action === "start") {
      return NextResponse.json(await backendJson(`/sessions/${id}/start`, { method: "POST" }));
    }
    if (body.action === "submit") {
      return NextResponse.json(await backendJson(`/sessions/${id}/submit-inspection`, { method: "POST" }));
    }
    if (body.action === "record" && typeof body.item_id === "string") {
      const payload = {
        condition: body.condition,
        note: body.note,
        measurement: body.measurement,
        selected_option: body.selected_option,
      };
      return NextResponse.json(await backendJson(`/sessions/${id}/inspection-items/${encodeURIComponent(body.item_id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }));
    }
    return NextResponse.json({ detail: "Unsupported inspection command" }, { status: 400 });
  } catch (error) {
    const message = error instanceof BackendRequestError ? error.detail : "The inspection service is unavailable";
    const status = error instanceof BackendRequestError ? error.status : 502;
    return NextResponse.json({ detail: message }, { status });
  }
}
