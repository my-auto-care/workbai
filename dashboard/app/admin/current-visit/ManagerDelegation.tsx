"use client";

import { useState } from "react";

type Candidate = { id: string; name: string; role: "advisor" | "admin"; current_visit_manager: boolean };
export type ManagerDelegationData = { feature_enabled: boolean; users: Candidate[] };

export function ManagerDelegation({ initial }: { initial: ManagerDelegationData }) {
  const [data, setData] = useState(initial);
  const [working, setWorking] = useState<string | null>(null);
  const [notice, setNotice] = useState("");

  async function setManager(user: Candidate, active: boolean) {
    setWorking(user.id); setNotice("");
    try {
      const response = await fetch("/api/current-visit/managers", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: user.id, active }) });
      const payload = await response.json() as { detail?: string; current_visit_manager?: boolean };
      if (!response.ok) throw new Error(payload.detail || "Unable to update manager delegation.");
      setData((current) => ({ ...current, users: current.users.map((candidate) => candidate.id === user.id ? { ...candidate, current_visit_manager: Boolean(payload.current_visit_manager) } : candidate) }));
      setNotice(`${user.name} is ${active ? "now" : "no longer"} a Current Visit manager.`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to update manager delegation."); }
    finally { setWorking(null); }
  }

  return <section className="mt-8 overflow-hidden rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] shadow-sm"><header className="border-b border-[#e0e7e6] p-5"><p className="text-xs font-bold uppercase tracking-[.13em] text-[#087e91]">Current Visit control</p><h2 className="mt-2 text-xl font-semibold tracking-tight">Explicit manager delegation</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-[#58717b]">Delegation permits a staff member to approve, activate, revoke, and publish a limited customer Current Visit update. Advisor or administrator role alone does not grant that authority.</p></header>{!data.feature_enabled ? <p className="m-5 rounded-xl border-l-4 border-[#e29337] bg-[#fdf5e6] p-4 text-sm leading-6 text-[#76534a]">Current Visit release is disabled in this environment. Delegations are shown for preparation only; no customer link, text, or email can be created.</p> : <div className="divide-y divide-[#e0e7e6]">{data.users.map((user) => <div key={user.id} className="flex flex-wrap items-center justify-between gap-4 p-5"><div><p className="font-semibold text-[#294a55]">{user.name}</p><p className="mt-1 text-xs font-bold uppercase tracking-wide text-[#617a83]">{user.role} · {user.current_visit_manager ? "Delegated manager" : "No release delegation"}</p></div><button type="button" disabled={working === user.id} onClick={() => void setManager(user, !user.current_visit_manager)} className={user.current_visit_manager ? "rounded-lg border border-[#c87d75] px-4 py-2.5 text-sm font-bold text-[#9a3d36] disabled:opacity-60" : "rounded-lg bg-[#087e91] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60"}>{working === user.id ? "Saving…" : user.current_visit_manager ? "Remove delegation" : "Delegate manager"}</button></div>)}</div>}{notice && <p className="m-5 rounded-lg bg-[#eaf6f4] p-3 text-sm font-medium text-[#286a43]" role="status">{notice}</p>}</section>;
}
