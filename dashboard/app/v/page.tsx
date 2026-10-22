import { CurrentVisitClient } from "./CurrentVisitClient";

// The proxy creates a unique CSP nonce for each request. This page must be
// dynamically rendered so Next attaches that nonce to its hydration scripts.
export const dynamic = "force-dynamic";

export default function PublicCurrentVisitPage() {
  return <CurrentVisitClient />;
}
