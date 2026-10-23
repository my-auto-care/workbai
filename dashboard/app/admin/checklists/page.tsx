import Link from "next/link";

import { BackendRequestError, backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

type Checklist = {
  id: string;
  name: string;
  version: number;
  lifecycle_status: "draft" | "approved" | "retired";
  is_provisional: boolean;
  active_for_new_visits: boolean;
  source_reference: string | null;
  source_sha256: string | null;
};

async function getChecklists(): Promise<{ checklists: Checklist[]; error: string | null }> {
  try {
    return { checklists: await backendJson<Checklist[]>("/checklists"), error: null };
  } catch (error) {
    return { checklists: [], error: error instanceof BackendRequestError ? error.detail : "The template registry is temporarily unavailable." };
  }
}

function badgeStyle(template: Checklist) {
  if (template.lifecycle_status === "retired") return "border-[#c9bfc0] bg-[#f4eeee] text-[#765858]";
  if (template.active_for_new_visits) return "border-[#8dc6bd] bg-[#e3f5f1] text-[#09636e]";
  if (template.lifecycle_status === "approved") return "border-[#a7bdc6] bg-[#ecf2f4] text-[#355765]";
  return "border-[#dec28a] bg-[#fff5dc] text-[#755616]";
}

export default async function ChecklistsPage() {
  const { checklists, error } = await getChecklists();
  const active = checklists.find((template) => template.active_for_new_visits);

  return (
    <main className="min-h-screen bg-[#f1ece3] px-5 py-9 text-[#1f3a47] sm:px-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-[#c9d7d8] pb-6">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-[.14em] text-[#087e91]">Workbai · administration</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">Inspection template registry</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#58717b]">One approved, non-provisional template may be active for new Check-in sessions. Historical snapshots retain their original version.</p>
          </div>
          {!error && <div className="flex flex-wrap gap-3">
            <Link href="/admin/checklists/new" className="inline-flex min-h-12 items-center rounded-xl bg-[#087e91] px-5 text-sm font-bold text-white shadow-sm transition hover:bg-[#056f80]">Create draft</Link>
            <Link href="/admin" className="inline-flex min-h-12 items-center px-3 text-sm font-bold text-[#087e91]">Admin</Link>
          </div>}
        </header>

        {error && <section className="mb-6 rounded-2xl border border-[#d98b7e] bg-[#fff1ec] p-5 text-[#8d392e]"><p className="font-semibold">Template governance is restricted</p><p className="mt-2 text-sm leading-6">{error} This administration workspace requires an authenticated Workbai administrator.</p></section>}

        {!error && <section className="mb-6 rounded-2xl border border-[#cadadb] bg-[#fbf8f2] p-5 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-[.12em] text-[#6a8189]">New-visit control</p>
          {active ? <p className="mt-2 text-lg font-semibold">{active.name} · v{active.version} is active for new Check-in sessions.</p> : <p className="mt-2 text-lg font-semibold text-[#825335]">No approved template is active. New Check-in sessions remain blocked.</p>}
          <p className="mt-2 text-sm leading-6 text-[#58717b]">The bundled test checklist stays provisional until the verified inspection artifact, hash, and named approval are recorded.</p>
        </section>}

        {!error && (checklists.length === 0 ? (
          <section className="rounded-2xl border border-dashed border-[#a9bdc0] bg-[#fbf8f2] p-10 text-center shadow-sm">
            <p className="font-semibold">No template records yet</p>
            <p className="mt-2 text-sm text-[#58717b]">Create a draft only after you have the controlled source material ready for review.</p>
          </section>
        ) : (
          <section className="overflow-hidden rounded-2xl border border-[#cadadb] bg-[#fbf8f2] shadow-sm">
            {checklists.map((template) => (
              <Link key={template.id} href={`/admin/checklists/${template.id}`} className="block border-b border-[#e0e7e6] p-5 transition hover:bg-[#f4faf8] last:border-0">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold">{template.name}</h2><span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${badgeStyle(template)}`}>{template.active_for_new_visits ? "Active" : template.lifecycle_status === "approved" ? "Approved" : template.lifecycle_status === "retired" ? "Retired" : "Draft"}</span>{template.is_provisional && <span className="rounded-full bg-[#fff3d7] px-2.5 py-1 text-xs font-bold text-[#785914]">Provisional</span>}</div>
                    <p className="mt-2 text-sm text-[#58717b]">v{template.version} · {template.source_reference ? template.source_reference : "No controlled source reference recorded"}</p>
                    {template.source_sha256 && <p className="mt-1 truncate font-mono text-xs text-[#6a8189]">SHA-256 {template.source_sha256}</p>}
                  </div>
                  <span className="text-sm font-bold text-[#087e91]">Open record →</span>
                </div>
              </Link>
            ))}
          </section>
        ))}
      </div>
    </main>
  );
}
