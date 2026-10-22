import Link from "next/link";

import { backendJson } from "@/lib/server-api";

export const dynamic = "force-dynamic";

type Checklist = { id: string; name: string; version: number; vehicle_filter?: Record<string, unknown> | null };

async function getChecklists(): Promise<Checklist[]> {
  try { return await backendJson<Checklist[]>("/checklists"); } catch { return []; }
}

export default async function ChecklistsPage() {
  const checklists = await getChecklists();
  return <main className="min-h-screen bg-[#f1ece3] p-8 text-[#1f3a47]"><div className="mx-auto max-w-4xl"><header className="mb-8 flex items-center justify-between"><div><p className="text-xs font-bold uppercase tracking-[.13em] text-[#087e91]">Workbai · administration</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Inspection templates</h1></div><div className="flex gap-3"><Link href="/admin/checklists/new" className="rounded-lg bg-[#087e91] px-4 py-3 text-sm font-bold text-white">New template</Link><Link href="/admin" className="self-center text-sm font-bold text-[#087e91]">Admin</Link></div></header>{checklists.length === 0 ? <section className="rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] p-10 text-center shadow-sm"><p className="font-semibold">No templates are available</p><Link href="/admin/checklists/new" className="mt-3 inline-block text-sm font-bold text-[#087e91]">Create a template</Link></section> : <section className="overflow-hidden rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] shadow-sm">{checklists.map((checklist) => <div key={checklist.id} className="flex items-center justify-between gap-5 border-b border-[#e0e7e6] p-5 last:border-0"><div><p className="font-semibold">{checklist.name}</p><p className="mt-1 text-sm text-[#58717b]">v{checklist.version} · {checklist.vehicle_filter && Object.keys(checklist.vehicle_filter).length ? JSON.stringify(checklist.vehicle_filter) : "All vehicles"}</p></div><Link href={`/admin/checklists/${checklist.id}`} className="text-sm font-bold text-[#087e91]">Edit</Link></div>)}</section>}</div></main>;
}
