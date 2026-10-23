import { NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";
import { BackendRequestError, backendFetch } from "@/lib/server-api";

// Check-in's plate scan (Chad, 2026-10-22): the plate photo, or the plate typed in, and its state go to the API's
// /vehicle/identify-plate, which reads the plate and asks the vehicle database for the VIN, year, make and model.
// Nothing is stored here; the photo is passed straight through.
const MAX_PHOTO_BYTES = 8 * 1024 * 1024;

export async function POST(request: Request) {
  const session = await auth0.getSession();
  if (!session) return NextResponse.json({ detail: "Sign in required" }, { status: 401 });

  let incoming: FormData;
  try {
    incoming = await request.formData();
  } catch {
    return NextResponse.json({ detail: "Send the plate photo or the plate and its state" }, { status: 400 });
  }
  const outgoing = new FormData();
  const state = incoming.get("state");
  const plate = incoming.get("plate");
  const image = incoming.get("image");
  if (typeof state === "string") outgoing.set("state", state);
  if (typeof plate === "string" && plate.trim()) outgoing.set("plate", plate);
  if (image instanceof File && image.size > 0) {
    if (image.size > MAX_PHOTO_BYTES) return NextResponse.json({ detail: "That photo is too large. Try again closer to the plate." }, { status: 413 });
    outgoing.set("image", image, image.name || "plate.jpg");
  }

  try {
    const response = await backendFetch("/vehicle/identify-plate", { method: "POST", body: outgoing });
    return NextResponse.json(await response.json(), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    if (error instanceof BackendRequestError) return NextResponse.json({ detail: error.detail }, { status: error.status });
    return NextResponse.json({ detail: "The vehicle lookup is unavailable. Enter the vehicle by hand." }, { status: 502 });
  }
}
