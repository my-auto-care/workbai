import Link from "next/link";

import { backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

type InspectionStatus = "pending" | "in_progress" | "completed" | "abandoned";
type QueueSession = {
  id: string;
  status: InspectionStatus;
  customer_concern?: string | null;
  vehicle_year?: string | null;
  vehicle_make?: string | null;
  vehicle_model?: string | null;
  vehicle_vin?: string | null;
  vehicle_mileage?: number | null;
  started_at?: string | null;
};

async function getSessions(): Promise<QueueSession[]> {
  try {
    return await backendJson<QueueSession[]>("/sessions");
  } catch {
    return [];
  }
}

const statusStyle: Record<InspectionStatus, string> = {
  pending: "bg-amber-100 text-amber-800 ring-amber-200",
  in_progress: "bg-cyan-100 text-cyan-800 ring-cyan-200",
  completed: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  abandoned: "bg-slate-100 text-slate-600 ring-slate-200",
};

export default async function QueuePage() {
  const sessions = await getSessions();
  const sorted = [...sessions].sort((left, right) => new Date(right.started_at ?? 0).getTime() - new Date(left.started_at ?? 0).getTime());

  return (
    <main className="min-h-screen bg-[#f1ece3] px-4 py-8 text-[#1f3a47] sm:px-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-8 flex items-end justify-between gap-5 border-b border-[#cad7da] pb-6">
          <div><p className="mb-2 text-xs font-bold uppercase tracking-[0.13em] text-[#087e91]">Workbai · operations</p><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Inspection queue</h1></div>
          <Link href="/check-in" className="rounded-lg bg-[#087e91] px-4 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-[#046e80]">Start check-in</Link>
        </header>

        {sorted.length === 0 ? (
          <section className="rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] p-10 text-center shadow-sm"><h2 className="text-lg font-semibold">No inspections are waiting</h2><p className="mt-2 text-sm leading-6 text-[#58717b]">A new visit appears here after a service advisor creates a pending inspection and assigns a technician.</p></section>
        ) : (
          <section className="overflow-hidden rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] shadow-sm">
            {sorted.map((session) => {
              const vehicle = [session.vehicle_year, session.vehicle_make, session.vehicle_model].filter(Boolean).join(" ");
              const date = session.started_at ? new Date(session.started_at).toLocaleString() : "Awaiting timestamp";
              return <Link key={session.id} href={`/sessions/${session.id}`} className="block border-b border-[#e0e7e6] p-5 transition last:border-0 hover:bg-[#f3f9f8]">
                <div className="flex items-start justify-between gap-4"><div className="min-w-0"><p className="truncate text-lg font-semibold">{vehicle || "Vehicle details pending"}</p>{session.vehicle_vin && <p className="mt-1 font-mono text-xs text-[#63808a]">VIN {session.vehicle_vin}</p>}{session.customer_concern && <p className="mt-2 line-clamp-2 text-sm italic leading-6 text-[#58717b]">&ldquo;{session.customer_concern}&rdquo;</p>}<p className="mt-2 text-xs text-[#718990]">{date}</p></div><span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold capitalize ring-1 ${statusStyle[session.status]}`}>{session.status.replace("_", " ")}</span></div>
              </Link>;
            })}
          </section>
        )}
      </div>
    </main>
  );
}
