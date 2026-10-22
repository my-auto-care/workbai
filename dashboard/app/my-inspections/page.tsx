import Link from "next/link";
import { redirect } from "next/navigation";

import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

type Inspection = { id: string; status: string; vehicle_year?: string | null; vehicle_make?: string | null; vehicle_model?: string | null; customer_concern?: string | null; presence_mode?: string | null };

export default async function MyInspectionsPage() {
  let inspections: Inspection[] = [];
  try {
    inspections = await backendJson<Inspection[]>("/sessions");
  } catch (error) {
    if (error instanceof BackendRequestError && error.status === 401) redirect("/auth/login?returnTo=%2Fmy-inspections");
  }

  return (
    <main className="workbai-home">
      <section className="my-inspections">
        <p className="home-kicker">Workbai · assigned work</p>
        <h1>My inspections</h1>
        <p className="home-copy">Open one vehicle at a time. Customer concern stays first; template results stay in the inspection workspace.</p>
        <div className="inspection-links">
          {inspections.length === 0 ? <p className="home-user">No scoped inspections are available right now.</p> : inspections.map((inspection) => {
            const vehicle = [inspection.vehicle_year, inspection.vehicle_make, inspection.vehicle_model].filter(Boolean).join(" ") || "Vehicle details pending";
            return <Link key={inspection.id} href={`/inspections/${inspection.id}`} className="inspection-link"><span><strong>{vehicle}</strong><small>{inspection.customer_concern ? `“${inspection.customer_concern}”` : "No stated concern"}</small></span><em>{inspection.status === "submitted" ? "Advisor review" : inspection.status.replace("_", " ")}</em></Link>;
          })}
        </div>
        <Link className="home-secondary" href="/queue">Open full inspection queue</Link>
      </section>
    </main>
  );
}
