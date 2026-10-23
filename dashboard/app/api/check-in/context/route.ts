import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const session = await auth0.getSession();
  if (!session) return NextResponse.json({ detail: "Sign in required" }, { status: 401 });
  const customerId = request.nextUrl.searchParams.get("customer_id");
  const vehicleId = request.nextUrl.searchParams.get("vehicle_id");
  if (!customerId && !vehicleId) return NextResponse.json({ detail: "Choose a customer or vehicle first" }, { status: 422 });
  const query = new URLSearchParams();
  if (customerId) query.set("customer_id", customerId);
  if (vehicleId) query.set("vehicle_id", vehicleId);
  try {
    return NextResponse.json(await backendJson(`/check-in/context?${query.toString()}`));
  } catch (error) {
    const detail = error instanceof BackendRequestError ? error.detail : "Customer context is unavailable";
    const status = error instanceof BackendRequestError ? error.status : 503;
    return NextResponse.json({ detail }, { status });
  }
}
