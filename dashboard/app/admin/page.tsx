import Link from "next/link";

import { backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

type SessionSummary = { id: string; status: "pending" | "in_progress" | "completed" | "abandoned"; customer_concern?: string | null; started_at?: string | null };
type ChecklistSummary = { id: string };

async function getData(): Promise<{ sessions: SessionSummary[]; checklists: ChecklistSummary[] }> {
  try {
    const [sessions, checklists] = await Promise.all([backendJson<SessionSummary[]>("/sessions"), backendJson<ChecklistSummary[]>("/checklists")]);
    return { sessions, checklists };
  } catch { return { sessions: [], checklists: [] }; }
}

export default async function AdminPage() {
  const { sessions, checklists } = await getData();
  const stats = { total: sessions.length, active: sessions.filter((session) => session.status === "in_progress").length, completed: sessions.filter((session) => session.status === "completed").length, checklists: checklists.length };
  return <main className="min-h-screen bg-[#f1ece3] p-8 text-[#1f3a47]"><div className="mx-auto max-w-6xl"><header className="mb-8 flex items-end justify-between border-b border-[#cad7da] pb-6"><div><p className="text-xs font-bold uppercase tracking-[.13em] text-[#087e91]">Workbai · administration</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Operations overview</h1></div><Link href="/" className="text-sm font-bold text-[#087e91]">Home</Link></header><section className="grid grid-cols-2 gap-4 md:grid-cols-4">{[{ label: "Inspections", value: stats.total, tone: "text-[#1f3a47]" }, { label: "In progress", value: stats.active, tone: "text-[#087e91]" }, { label: "Completed", value: stats.completed, tone: "text-[#218849]" }, { label: "Templates", value: stats.checklists, tone: "text-[#1f3a47]" }].map((stat) => <article key={stat.label} className="rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] p-5 shadow-sm"><p className="text-sm text-[#58717b]">{stat.label}</p><p className={`mt-1 text-3xl font-semibold ${stat.tone}`}>{stat.value}</p></article>)}</section><div className="mt-8 flex flex-wrap gap-3"><Link href="/check-in" className="rounded-lg bg-[#087e91] px-5 py-3 text-sm font-bold text-white">Start check-in</Link><Link href="/admin/checklists" className="rounded-lg border border-[#9ab0b7] px-5 py-3 text-sm font-bold text-[#264957]">Manage templates</Link><Link href="/queue" className="self-center text-sm font-bold text-[#087e91]">Inspection queue</Link></div><section className="mt-10 overflow-hidden rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] shadow-sm"><div className="border-b border-[#e0e7e6] p-5"><h2 className="font-semibold">Recent inspections</h2></div>{sessions.length === 0 ? <p className="p-8 text-center text-sm text-[#58717b]">No inspections yet.</p> : sessions.slice(0, 20).map((session) => <Link key={session.id} href={`/sessions/${session.id}`} className="flex items-center justify-between gap-4 border-b border-[#e0e7e6] p-5 text-sm last:border-0 hover:bg-[#f3f9f8]"><div><p className="font-mono text-xs text-[#58717b]">{session.id.slice(0, 8)}</p><p className="mt-1 truncate text-[#355462]">{session.customer_concern || "No customer concern recorded"}</p></div><span className="font-bold capitalize text-[#087e91]">{session.status.replace("_", " ")}</span></Link>)}</section></div></main>;
}
