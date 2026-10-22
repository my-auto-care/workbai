"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import styles from "./advisor-review.module.css";

type Disposition = "safety" | "maintenance" | "visit_concern" | "monitor" | "no_action" | "needs_clarification";
type Session = {
  id: string;
  status: "submitted" | "advisor_reviewed";
  customer_concern?: string | null;
  vehicle_year?: string | null;
  vehicle_make?: string | null;
  vehicle_model?: string | null;
  vehicle_mileage?: number | null;
  presence_mode?: "waiter" | "dropoff" | null;
  template_version?: number | null;
};
type Decision = {
  id: string;
  template_item_id: string;
  disposition: Disposition;
  rationale: string;
  updated_at?: string | null;
};
type AttentionItem = {
  section_name: string;
  item: { id: string; name: string; type?: string; unit?: string; options?: string[] };
  technician_response: { condition: "poor"; note?: string | null; measurement?: string | null; selected_option?: string | null };
  advisor_decision: Decision | null;
};

export type AdvisorReviewData = {
  session: Session;
  attention_items: AttentionItem[];
  summary: { attention_count: number; decisions_saved: number; good_count: number; na_count: number };
  can_review: boolean;
  customer_release_available: false;
};

type RowDraft = { disposition: Disposition | ""; rationale: string };

const dispositionLabel: Record<Disposition, string> = {
  safety: "Safety",
  maintenance: "Maintenance",
  visit_concern: "Visit concern",
  monitor: "Monitor",
  no_action: "No action",
  needs_clarification: "Needs clarification",
};

function vehicleLabel(session: Session) {
  return [session.vehicle_year, session.vehicle_make, session.vehicle_model].filter(Boolean).join(" ") || "Vehicle details pending";
}

async function command(id: string, body: Record<string, string>): Promise<Decision | { session: Session; message: string }> {
  const response = await fetch(`/api/advisor-review/${id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const payload = (await response.json()) as Decision | { session: Session; message: string } | { detail?: string };
  if (!response.ok) throw new Error("detail" in payload && payload.detail ? payload.detail : "Unable to save advisor review.");
  return payload as Decision | { session: Session; message: string };
}

function ReviewItem({ item, sessionId, writable, onSaved }: { item: AttentionItem; sessionId: string; writable: boolean; onSaved: (decision: Decision) => void }) {
  const [draft, setDraft] = useState<RowDraft>({ disposition: item.advisor_decision?.disposition ?? "", rationale: item.advisor_decision?.rationale ?? "" });
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");
  const [notice, setNotice] = useState("");

  async function save() {
    if (!draft.disposition || draft.rationale.trim().length < 3) {
      setState("error");
      setNotice("Choose a disposition and record a concise written rationale.");
      return;
    }
    setState("saving");
    setNotice("");
    try {
      const result = await command(sessionId, { action: "save", item_id: item.item.id, disposition: draft.disposition, rationale: draft.rationale.trim() }) as Decision;
      onSaved(result);
      setState("idle");
      setNotice("Disposition saved to this internal advisor review.");
    } catch (error) {
      setState("error");
      setNotice(error instanceof Error ? error.message : "Unable to save advisor review.");
    }
  }

  return (
    <article className={styles.reviewItem}>
      <header className={styles.itemHeader}><div><p className={styles.itemMeta}>{item.section_name} · {item.item.id}</p><h3>{item.item.name}</h3></div>{item.advisor_decision && <span className={styles.dispositionTag}>{dispositionLabel[item.advisor_decision.disposition]}</span>}</header>
      <section className={styles.technicianRecord} aria-label="Technician-attested observation"><p className={styles.recordLabel}>Technician-attested observation</p>{item.technician_response.selected_option && <p><strong>Observation:</strong> {item.technician_response.selected_option}</p>}{item.technician_response.measurement && <p><strong>Measurement:</strong> {item.technician_response.measurement}{item.item.unit ? ` ${item.item.unit}` : ""}</p>}<p>{item.technician_response.note}</p></section>
      {writable ? <div className={styles.decisionForm}><label>Internal disposition<select value={draft.disposition} onChange={(event) => setDraft((current) => ({ ...current, disposition: event.target.value as Disposition }))}><option value="">Select a disposition</option>{(Object.keys(dispositionLabel) as Disposition[]).map((key) => <option key={key} value={key}>{dispositionLabel[key]}</option>)}</select></label><label>Advisor rationale<textarea rows={3} value={draft.rationale} onChange={(event) => setDraft((current) => ({ ...current, rationale: event.target.value }))} placeholder="Record the human review rationale. This is not customer-facing language." /></label>{notice && <p role={state === "error" ? "alert" : "status"} className={state === "error" ? styles.error : styles.saved}>{notice}</p>}<button className={styles.saveButton} type="button" disabled={state === "saving"} onClick={save}>{state === "saving" ? "Saving…" : item.advisor_decision ? "Update disposition" : "Save disposition"}</button></div> : item.advisor_decision ? <section className={styles.lockedDecision}><p className={styles.recordLabel}>Advisor disposition · {dispositionLabel[item.advisor_decision.disposition]}</p><p>{item.advisor_decision.rationale}</p></section> : <p className={styles.unreviewed}>No advisor disposition was recorded.</p>}
    </article>
  );
}

export function AdvisorReviewWorkbench({ initialReview }: { initialReview: AdvisorReviewData }) {
  const [review, setReview] = useState(initialReview);
  const [notice, setNotice] = useState("");
  const [completionState, setCompletionState] = useState<"idle" | "working" | "error">("idle");
  const saved = useMemo(() => review.attention_items.filter((item) => item.advisor_decision).length, [review.attention_items]);
  const remaining = review.attention_items.length - saved;

  function onDecision(itemId: string, decision: Decision) {
    setReview((current) => ({ ...current, summary: { ...current.summary, decisions_saved: current.attention_items.some((item) => item.item.id === itemId && item.advisor_decision) ? current.summary.decisions_saved : current.summary.decisions_saved + 1, }, attention_items: current.attention_items.map((item) => item.item.id === itemId ? { ...item, advisor_decision: decision } : item) }));
  }

  async function complete() {
    setCompletionState("working");
    setNotice("");
    try {
      const result = await command(review.session.id, { action: "complete" }) as { session: Session; message: string };
      setReview((current) => ({ ...current, session: result.session, can_review: false }));
      setNotice(result.message);
      setCompletionState("idle");
    } catch (error) {
      setCompletionState("error");
      setNotice(error instanceof Error ? error.message : "Unable to complete advisor review.");
    }
  }

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}><div><p className={styles.eyebrow}>Workbai · advisor workbench</p><h1>{vehicleLabel(review.session)}</h1><p className={styles.concern}><span>Original concern</span>{review.session.customer_concern || "Not recorded"}</p></div><Link className={styles.backLink} href="/queue">Inspection queue</Link></header>
      <section className={styles.context}><div><span>Arrival</span><strong>{review.session.presence_mode === "waiter" ? "Waiter" : "Drop-off"}</strong></div><div><span>Inspection state</span><strong>{review.session.status === "advisor_reviewed" ? "Advisor reviewed" : "Submitted by technician"}</strong></div><div><span>Attention items</span><strong>{review.summary.attention_count}</strong></div><div><span>Decisions saved</span><strong>{saved} of {review.summary.attention_count}</strong></div></section>
      <section className={styles.boundary}><strong>Internal decision preparation only</strong><span>Customer reporting, estimates, messages, repair authorization, work release, and AI recommendations are unavailable in this workspace.</span></section>
      <section className={styles.quietResults}><div><p className={styles.eyebrow}>Contained inspection record</p><h2>{review.summary.attention_count === 0 ? "No Needs attention items require triage" : "Triage only the items that need attention"}</h2><p>Good: {review.summary.good_count} · N/A: {review.summary.na_count}. They remain a quiet completed-work record—not an upsell list.</p></div></section>
      {review.attention_items.length ? <section className={styles.itemList} aria-label="Advisor disposition items">{review.attention_items.map((item) => <ReviewItem key={item.item.id} item={item} sessionId={review.session.id} writable={review.can_review} onSaved={(decision) => onDecision(item.item.id, decision)} />)}</section> : <section className={styles.empty}><h2>Ready for internal review completion</h2><p>The submitted inspection contains no technician-attested Needs attention items.</p></section>}
      {notice && <p className={completionState === "error" ? styles.error : styles.notice} role={completionState === "error" ? "alert" : "status"}>{notice}</p>}
      {review.can_review && <section className={styles.completePanel}><div><p className={styles.eyebrow}>Review completion</p><h2>{remaining ? `${remaining} item${remaining === 1 ? "" : "s"} still need${remaining === 1 ? "s" : ""} a disposition` : "Every attention item has a human disposition"}</h2><p>Completing this step records internal advisor review. It deliberately does not notify a customer or authorize any repair.</p></div><button className={styles.completeButton} disabled={remaining > 0 || completionState === "working"} type="button" onClick={complete}>{completionState === "working" ? "Recording…" : "Complete advisor review"}</button></section>}
    </main>
  );
}
