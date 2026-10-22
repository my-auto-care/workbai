import Link from "next/link";
import { redirect } from "next/navigation";

import { BackendRequestError, backendJson } from "@/lib/server-api";

import { ManagerDelegation, type ManagerDelegationData } from "./ManagerDelegation";

export const dynamic = "force-dynamic";

export default async function CurrentVisitAdminPage() {
  let data: ManagerDelegationData | null = null;
  let error = "Current Visit manager settings are unavailable.";
  try { data = await backendJson<ManagerDelegationData>("/current-visit/manager-grants"); }
  catch (cause) {
    if (cause instanceof BackendRequestError && cause.status === 401) redirect("/auth/login?returnTo=%2Fadmin%2Fcurrent-visit");
    error = cause instanceof BackendRequestError ? cause.detail : error;
  }
  return <main className="min-h-screen bg-[#f1ece3] p-8 text-[#1f3a47]"><div className="mx-auto max-w-4xl"><header className="flex flex-wrap items-end justify-between gap-4 border-b border-[#cad7da] pb-6"><div><p className="text-xs font-bold uppercase tracking-[.13em] text-[#087e91]">Workbai · administration</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Current Visit access</h1></div><Link href="/admin" className="text-sm font-bold text-[#087e91]">Administration overview</Link></header>{data ? <ManagerDelegation initial={data} /> : <section className="mt-8 rounded-2xl border border-[#e2aaa5] bg-[#fbeceb] p-6"><h2 className="font-semibold text-[#87352f]">Manager settings unavailable</h2><p className="mt-2 text-sm leading-6 text-[#8a4a45]">{error}</p></section>}<section className="mt-6 rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] p-6 text-sm leading-6 text-[#58717b]"><strong className="text-[#294a55]">Customer delivery remains intentionally held.</strong><p className="mt-2">This page does not configure SMS or email, create an account, authorize repairs, or show a customer inspection report. A separate approved provider, consent, recipient verification, opt-out, delivery audit, rate-limit, and template-control release is required before automated messaging can be considered.</p></section></div></main>;
}
