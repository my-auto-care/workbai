import Link from "next/link";

import { auth0 } from "@/lib/auth0";

export const dynamic = "force-dynamic";

export default async function Home() {
  const session = await auth0.getSession();
  if (!session) {
    return (
      <main className="workbai-home">
        <section>
          <p className="home-kicker">Workbai</p>
          <h1>Inspection work, ready for the bay.</h1>
          <p className="home-copy">A secure staff workspace for preparing a clear, assigned inspection before the vehicle enters service.</p>
          <a className="home-primary" href="/auth/login?returnTo=%2Fcheck-in">Sign in to Check-in</a>
        </section>
      </main>
    );
  }

  return (
    <main className="workbai-home">
      <section>
        <p className="home-kicker">Workbai · staff workspace</p>
        <h1>Ready for the next arrival.</h1>
        <p className="home-copy">Start a pending inspection with a confirmed vehicle, stated concern, active checklist, and assigned technician.</p>
        <div className="home-actions">
          <Link className="home-primary" href="/check-in">Start check-in</Link>
          <Link className="home-secondary" href="/my-inspections">My inspections</Link>
          <Link className="home-secondary" href="/queue">Open inspection queue</Link>
        </div>
        <p className="home-user">Signed in as {session.user.name ?? "staff member"} · <a href="/auth/logout">Sign out</a></p>
      </section>
    </main>
  );
}
