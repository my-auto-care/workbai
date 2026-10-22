import { redirect } from "next/navigation";

import { CheckinForm, type CheckinOptions } from "./CheckinForm";
import { auth0 } from "@/lib/auth0";
import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function CheckInPage() {
  const session = await auth0.getSession();
  if (!session) redirect("/auth/login?returnTo=%2Fcheck-in");

  let options: CheckinOptions;
  try {
    options = await backendJson<CheckinOptions>("/check-in/options");
  } catch (error) {
    const detail = error instanceof BackendRequestError ? error.detail : "Check-in is temporarily unavailable.";
    return (
      <main className="checkin-shell">
        <section className="checkin-message" aria-labelledby="checkin-unavailable-title">
          <p className="eyebrow">Workbai · staff workspace</p>
          <h1 id="checkin-unavailable-title">Check-in is not ready for this account</h1>
          <p>{detail}</p>
          <p className="muted">A manager must assign active staff, a shop, and an inspection template before visits can be started.</p>
          <a className="text-link" href="/auth/logout">Sign out</a>
        </section>
      </main>
    );
  }

  return <CheckinForm options={options} userName={session.user.name ?? options.actor.name} />;
}
