import { NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { BackendRequestError, backendJson } from "@/lib/server-api";

export async function POST(request: Request) {
  const session = await auth0.getSession();
  if (!session) return NextResponse.json({ detail: "Sign in required" }, { status: 401 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Provide a valid check-in request" }, { status: 400 });
  }

  try {
    const created = await backendJson("/check-in/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return NextResponse.json(created, { status: 201 });
  } catch (error) {
    if (error instanceof BackendRequestError) {
      return NextResponse.json({ detail: error.detail }, { status: error.status });
    }
    return NextResponse.json({ detail: "Inspection service is unavailable" }, { status: 502 });
  }
}
