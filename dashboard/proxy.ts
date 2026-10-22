import { auth0 } from "./lib/auth0";
import { NextResponse } from "next/server";

function currentVisitPageResponse(request: Request) {
  const nonce = crypto.randomUUID().replaceAll("-", "");
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "base-uri 'none'",
    "object-src 'none'",
    "form-action 'none'",
  ].join("; ");
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("Cache-Control", "no-store, private, max-age=0");
  response.headers.set("Referrer-Policy", "no-referrer");
  return response;
}

export async function proxy(request: Request) {
  const pathname = new URL(request.url).pathname;
  if (pathname === "/v") return currentVisitPageResponse(request);
  if (pathname === "/api/public-current-visit/resolve") return NextResponse.next();
  return auth0.middleware(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)"],
};
