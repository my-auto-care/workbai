import { NextResponse } from "next/server";

import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ id: string }> };
type Disposition = "safety" | "maintenance" | "visit_concern" | "monitor" | "no_action" | "needs_clarification";
type Command =
  | { action: "save"; item_id: string; disposition: Disposition; rationale: string }
  | { action: "complete" };

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
    if (body.action === "complete") {
      return NextResponse.json(await backendJson(`/sessions/${id}/advisor-review/complete`, { method: "POST" }));
    }
    if (
      body.action === "save"
      && typeof body.item_id === "string"
      && typeof body.rationale === "string"
      && ["safety", "maintenance", "visit_concern", "monitor", "no_action", "needs_clarification"].includes(body.disposition)
    ) {
      return NextResponse.json(await backendJson(`/sessions/${id}/advisor-review/items/${encodeURIComponent(body.item_id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ disposition: body.disposition, rationale: body.rationale }),
      }));
    }
    return NextResponse.json({ detail: "Unsupported advisor-review command" }, { status: 400 });
  } catch (error) {
    const detail = error instanceof BackendRequestError ? error.detail : "The inspection service is unavailable";
    const status = error instanceof BackendRequestError ? error.status : 502;
    return NextResponse.json({ detail }, { status });
  }
}
