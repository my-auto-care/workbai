import "server-only";

import { auth0 } from "@/lib/auth0";

export class BackendRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail);
  }
}

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new BackendRequestError(503, `${name} is not configured`);
  return value;
}

function urlFor(path: string): string {
  const base = required("WORKBAI_BACKEND_INTERNAL_URL").replace(/\/$/, "");
  if (!path.startsWith("/")) throw new BackendRequestError(500, "Internal API path must start with /");
  return `${base}${path}`;
}

async function token(): Promise<string> {
  const session = await auth0.getSession();
  if (!session) throw new BackendRequestError(401, "Sign in required");
  const { token } = await auth0.getAccessToken({ audience: required("AUTH0_API_AUDIENCE") });
  return token;
}

export async function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(urlFor(path), {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${await token()}`,
      ...init.headers,
    },
  });
  if (!response.ok) {
    let detail = "The inspection service could not complete this request";
    try {
      const body = (await response.json()) as { detail?: string | { message?: string } };
      if (typeof body.detail === "string") detail = body.detail;
      if (body.detail && typeof body.detail === "object" && typeof body.detail.message === "string") detail = body.detail.message;
    } catch {
      // Preserve a safe, generic message for malformed upstream responses.
    }
    throw new BackendRequestError(response.status, detail);
  }
  return response;
}

export async function backendJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await backendFetch(path, init)).json() as Promise<T>;
}
