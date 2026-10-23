import { NextResponse } from "next/server";

import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ id: string }> };
type ProgressCode = "checked_in" | "inspection_underway" | "team_reviewing" | "shop_update_available";
type Command =
  | { action: "prepare"; human_owner_user_id?: string }
  | { action: "approve" }
  | { action: "activate-counter" }
  | { action: "revoke"; reason: "customer_requested" | "wrong_recipient" | "privacy_request" | "other" }
  | { action: "request-progress"; status_code: ProgressCode }
  | { action: "approve-progress" };

function validId(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function errorResponse(error: unknown) {
  const detail = error instanceof BackendRequestError ? error.detail : "The Current Visit service is unavailable";
  const status = error instanceof BackendRequestError ? error.status : 502;
  return NextResponse.json({ detail }, { status });
}

export async function GET(_request: Request, { params }: Context) {
  const { id } = await params;
  if (!validId(id)) return NextResponse.json({ detail: "Invalid inspection identifier" }, { status: 400 });
  try {
    return NextResponse.json(await backendJson(`/sessions/${id}/current-visit`));
  } catch (error) {
    return errorResponse(error);
  }
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
    if (body.action === "prepare") {
      return NextResponse.json(await backendJson(`/sessions/${id}/current-visit/prepare`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ human_owner_user_id: body.human_owner_user_id }) }));
    }
    if (body.action === "approve") return NextResponse.json(await backendJson(`/sessions/${id}/current-visit/approve`, { method: "POST" }));
    if (body.action === "activate-counter") return NextResponse.json(await backendJson(`/sessions/${id}/current-visit/activate-counter`, { method: "POST" }));
    if (body.action === "revoke" && ["customer_requested", "wrong_recipient", "privacy_request", "other"].includes(body.reason)) {
      return NextResponse.json(await backendJson(`/sessions/${id}/current-visit/revoke`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reason: body.reason }) }));
    }
    if (body.action === "request-progress" && ["checked_in", "inspection_underway", "team_reviewing", "shop_update_available"].includes(body.status_code)) {
      return NextResponse.json(await backendJson(`/sessions/${id}/current-visit/progress/request`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status_code: body.status_code }) }));
    }
    if (body.action === "approve-progress") return NextResponse.json(await backendJson(`/sessions/${id}/current-visit/progress/approve`, { method: "POST" }));
    return NextResponse.json({ detail: "Unsupported Current Visit command" }, { status: 400 });
  } catch (error) {
    return errorResponse(error);
  }
}
