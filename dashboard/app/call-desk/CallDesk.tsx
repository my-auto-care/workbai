"use client";

import { useState } from "react";
import styles from "./call-desk.module.css";

type CallMatch = {
  customer: { display_name: string; contacts: Array<{ label: string }>; vehicles: Array<{ label: string }> };
  conversation_summaries: Array<{ source_label: string; summary: string; recorded_at: string }>;
  recent_visits: Array<{ vehicle_label: string; status: string; started_at: string }>;
  next_appointment: { at: string; summary: string; source_label: string } | null;
};

type CallContext = { match_count: number; matches: CallMatch[]; unverified_caller_notice: string };

export function CallDesk() {
  const [phone, setPhone] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState("");
  const [context, setContext] = useState<CallContext | null>(null);

  async function lookup(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("loading"); setMessage(""); setContext(null);
    try {
      const response = await fetch("/api/check-in/call-context", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caller_phone: phone.trim() }) });
      const body = (await response.json()) as CallContext | { detail?: string };
      if (!response.ok) throw new Error("detail" in body && body.detail ? body.detail : "Call context is unavailable");
      setContext(body as CallContext); setState("idle");
    } catch (error) { setState("error"); setMessage(error instanceof Error ? error.message : "Call context is unavailable"); }
  }

  return <main className={styles.shell}>
    <header><p className={styles.eyebrow}>Workbai · reception desk</p><h1>Incoming call context</h1><p>Paste a normalized caller number to find a protected staff candidate card. This is a manual lookup, not a caller verification or a live phone integration.</p></header>
    <form onSubmit={lookup} className={styles.search}><label>Caller number<input value={phone} onChange={(event) => setPhone(event.target.value)} inputMode="tel" placeholder="+15551234567" required /></label><button disabled={state === "loading"} type="submit">{state === "loading" ? "Finding context…" : "Find call context"}</button></form>
    {state === "error" && <p className={styles.error} role="alert">{message}</p>}
    {context && <section className={styles.results} aria-live="polite"><p className={styles.notice}>{context.unverified_caller_notice}</p>{context.match_count === 0 ? <div className={styles.empty}><h2>No protected customer candidate</h2><p>Continue with normal caller verification and manual Check-in. No new profile or appointment was created.</p></div> : context.matches.map((match, index) => <article className={styles.card} key={`${match.customer.display_name}-${index}`}><div className={styles.title}><div><p className={styles.eyebrow}>Staff candidate</p><h2>{match.customer.display_name}</h2><p>{match.customer.contacts.map((contact) => contact.label).join(" · ")}</p></div><span>{match.customer.vehicles.map((vehicle) => vehicle.label).join(" · ") || "No confirmed vehicle"}</span></div>{match.next_appointment && <section className={styles.appointment}><strong>Upcoming appointment</strong><span>{new Date(match.next_appointment.at).toLocaleString()}</span><p>{match.next_appointment.summary}</p></section>}<div className={styles.columns}><section><h3>Conversation context</h3>{match.conversation_summaries.length ? <ul>{match.conversation_summaries.map((summary, row) => <li key={`${summary.source_label}-${row}`}><strong>{summary.source_label}</strong><span>{summary.summary}</span></li>)}</ul> : <p>No reviewed conversation summary.</p>}</section><section><h3>Recent visit history</h3>{match.recent_visits.length ? <ul>{match.recent_visits.map((visit, row) => <li key={`${visit.vehicle_label}-${row}`}><strong>{visit.vehicle_label}</strong><span>{visit.status.replaceAll("_", " ")}</span></li>)}</ul> : <p>No linked visits.</p>}</section></div><p className={styles.boundary}>No raw transcript, findings, diagnosis, repair authorization, estimate, customer message, or public Glovebox detail is shown here.</p></article>)}</section>}
  </main>;
}
