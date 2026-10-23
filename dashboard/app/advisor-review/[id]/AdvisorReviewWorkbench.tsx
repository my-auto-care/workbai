"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import styles from "./advisor-review.module.css";

type Disposition = "safety" | "maintenance" | "visit_concern" | "monitor" | "no_action" | "needs_clarification";
type ProgressCode = "checked_in" | "inspection_underway" | "team_reviewing" | "shop_update_available";
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
type CurrentVisitReadiness = {
  ready_for_future_customer_access: boolean;
  customer_access_enabled: false;
  reasons: string[];
};

export type AdvisorReviewData = {
  session: Session;
  attention_items: AttentionItem[];
  summary: { attention_count: number; decisions_saved: number; good_count: number; na_count: number };
  can_review: boolean;
  customer_release_available: false;
  current_visit_readiness: CurrentVisitReadiness;
};

export type CurrentVisitReleaseData = {
  feature_enabled: boolean;
  internal_readiness: CurrentVisitReadiness;
  manager_delegated: boolean;
  release: null | {
    state: "draft" | "manager_approved" | "active" | "revoked";
    human_owner_user_id: string;
    prepared_at: string | null;
    approved_at: string | null;
    active_projection: null | { revision: number; status_code: ProgressCode };
    pending_projection: null | { revision: number; status_code: ProgressCode };
    active_counter_link_expires_at: string | null;
    contact: { present: boolean; channel: "sms" | "email" | null; verification_state: string | null; consents: Record<string, string> };
  };
  outbound_delivery: { enabled: false; reason: string };
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

const progressLabel: Record<ProgressCode, string> = {
  checked_in: "Checked in",
  inspection_underway: "Inspection underway",
  team_reviewing: "Team reviewing",
  shop_update_available: "Advisor follow-up requested",
};

function vehicleLabel(session: Session) {
  return [session.vehicle_year, session.vehicle_make, session.vehicle_model].filter(Boolean).join(" ") || "Vehicle details pending";
}

const readinessCopy: Record<string, string> = {
  advisor_review_incomplete: "Complete the internal advisor review first.",
  advisor_review_audit_missing: "The advisor-review audit record is incomplete.",
  template_snapshot_missing: "This visit does not retain a controlled template snapshot.",
  template_reference_missing: "This visit has no controlled template reference.",
  template_provenance_missing: "This visit is missing verified template provenance.",
  template_approval_missing: "This visit is missing template approval attribution.",
  template_record_missing: "The referenced controlled template record is unavailable.",
  template_provenance_unverified: "The retained template record no longer verifies this visit’s controlled provenance.",
};

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

function CurrentVisitControl({ initial, sessionId, sessionStatus }: { initial: CurrentVisitReleaseData; sessionId: string; sessionStatus: Session["status"] }) {
  const [currentVisit, setCurrentVisit] = useState(initial);
  const [state, setState] = useState<"idle" | "working" | "error">("idle");
  const [notice, setNotice] = useState("");
  const [counterLink, setCounterLink] = useState<{ url: string; expires_at: string } | null>(null);
  const [progress, setProgress] = useState<ProgressCode>("shop_update_available");

  async function refresh() {
    const response = await fetch(`/api/current-visit/${sessionId}`, { cache: "no-store" });
    const payload = (await response.json()) as CurrentVisitReleaseData | { detail?: string };
    if (!response.ok) throw new Error("detail" in payload && payload.detail ? payload.detail : "Unable to load Current Visit status.");
    setCurrentVisit(payload as CurrentVisitReleaseData);
  }

  useEffect(() => {
    let disposed = false;
    void fetch(`/api/current-visit/${sessionId}`, { cache: "no-store" })
      .then(async (response) => ({ response, payload: await response.json() as CurrentVisitReleaseData | { detail?: string } }))
      .then(({ response, payload }) => {
        if (response.ok && !disposed) setCurrentVisit(payload as CurrentVisitReleaseData);
      })
      .catch(() => undefined);
    return () => { disposed = true; };
  }, [sessionId, sessionStatus]);

  async function run(action: "prepare" | "approve" | "activate-counter" | "revoke" | "request-progress" | "approve-progress", extra: Record<string, string> = {}) {
    setState("working");
    setNotice("");
    setCounterLink(null);
    try {
      const response = await fetch(`/api/current-visit/${sessionId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, ...extra }) });
      const payload = (await response.json()) as CurrentVisitReleaseData | { url: string; expires_at: string; message: string } | { detail?: string };
      if (!response.ok) throw new Error("detail" in payload && payload.detail ? payload.detail : "Unable to update Current Visit.");
      if ("url" in payload) {
        setCounterLink({ url: payload.url, expires_at: payload.expires_at });
        setNotice(payload.message);
        await refresh();
      } else {
        setCurrentVisit(payload as CurrentVisitReleaseData);
        setNotice(action === "prepare" ? "Current Visit is prepared for manager review. No customer link or message has been created." : "Current Visit state recorded.");
      }
      setState("idle");
    } catch (error) {
      setState("error");
      setNotice(error instanceof Error ? error.message : "Unable to update Current Visit.");
    }
  }

  const release = currentVisit.release;
  const ready = currentVisit.internal_readiness.ready_for_future_customer_access;
  const description = !currentVisit.feature_enabled
    ? "This test environment has the Current Visit release feature turned off. No customer link, QR, text, or email can be created."
    : !ready
      ? "Finish the internal advisor review and controlled-template record before customer access can be considered."
      : !release
        ? "Prepare a minimal view-only visit update. A manager must approve it before any link can be activated."
        : release.state === "draft"
          ? "A manager must approve this exact customer-safe update before a counter view can be activated."
          : release.state === "manager_approved"
            ? "A manager may activate one private 15-minute counter link. It is view-only and is not a text or email."
            : release.state === "active"
              ? `The active counter view expires ${release.active_counter_link_expires_at ? new Date(release.active_counter_link_expires_at).toLocaleString() : "soon"}.`
              : "This customer view is no longer active. A new manager-reviewed release is required to re-open it.";
  const heading = !currentVisit.feature_enabled ? "Customer access is disabled" : !ready ? "Internal record still needs work" : !release ? "Ready to prepare for manager review" : release.state === "draft" ? "Awaiting manager release review" : release.state === "manager_approved" ? "Approved for a counter view" : release.state === "active" ? "Customer counter view is active" : "Customer access was revoked";

  return (
    <section className={styles.currentVisit} aria-label="Current Visit release">
      <div><p className={styles.eyebrow}>Current Visit</p><h2>{heading}</h2><p>{description}</p></div>
      {currentVisit.feature_enabled && ready && <div className={styles.currentVisitActions}>
        {!release && <button className={styles.saveButton} type="button" disabled={state === "working"} onClick={() => void run("prepare")}>Prepare for manager review</button>}
        {release?.state === "draft" && (currentVisit.manager_delegated ? <button className={styles.completeButton} type="button" disabled={state === "working"} onClick={() => void run("approve")}>Approve customer view</button> : <p className={styles.controlHint}>Awaiting an explicitly delegated Current Visit manager.</p>)}
        {release?.state === "manager_approved" && (currentVisit.manager_delegated ? <button className={styles.completeButton} type="button" disabled={state === "working"} onClick={() => void run("activate-counter")}>Activate 15-minute counter view</button> : <p className={styles.controlHint}>A delegated manager must activate the counter view.</p>)}
        {release?.state === "active" && <>
          <div className={styles.progressControls}><label>Next customer update<select value={progress} onChange={(event) => setProgress(event.target.value as ProgressCode)}>{(Object.keys(progressLabel) as ProgressCode[]).map((code) => <option key={code} value={code}>{progressLabel[code]}</option>)}</select></label><button className={styles.saveButton} type="button" disabled={state === "working" || Boolean(release.pending_projection)} onClick={() => void run("request-progress", { status_code: progress })}>{release.pending_projection ? "Manager review pending" : "Request manager update review"}</button></div>
          {release.pending_projection && currentVisit.manager_delegated && <button className={styles.completeButton} type="button" disabled={state === "working"} onClick={() => void run("approve-progress")}>Publish manager-approved update</button>}
          {currentVisit.manager_delegated && <button className={styles.revokeButton} type="button" disabled={state === "working"} onClick={() => void run("revoke", { reason: "other" })}>Revoke customer access</button>}
        </>}
        {release?.state === "revoked" && <button className={styles.saveButton} type="button" disabled={state === "working"} onClick={() => void run("prepare")}>Prepare replacement for review</button>}
      </div>}
      {counterLink && <section className={styles.counterLink}><strong>Private counter link — show once</strong><a href={counterLink.url} target="_blank" rel="noreferrer">Open Current Visit</a><span>Expires {new Date(counterLink.expires_at).toLocaleString()}. It was not sent to the customer.</span></section>}
      {currentVisit.feature_enabled && <p className={styles.deliveryHold}><strong>Outbound customer messaging is held.</strong> {currentVisit.outbound_delivery.reason}</p>}
      {notice && <p className={state === "error" ? styles.error : styles.notice} role={state === "error" ? "alert" : "status"}>{notice}</p>}
    </section>
  );
}

export function AdvisorReviewWorkbench({ initialReview, initialCurrentVisit }: { initialReview: AdvisorReviewData; initialCurrentVisit: CurrentVisitReleaseData }) {
  const [review, setReview] = useState(initialReview);
  const [notice, setNotice] = useState("");
  const [completionState, setCompletionState] = useState<"idle" | "working" | "error">("idle");
  const saved = useMemo(() => review.attention_items.filter((item) => item.advisor_decision).length, [review.attention_items]);
  const remaining = review.attention_items.length - saved;

  function onDecision(itemId: string, decision: Decision) {
    setReview((current) => ({ ...current, summary: { ...current.summary, decisions_saved: current.attention_items.some((item) => item.item.id === itemId && item.advisor_decision) ? current.summary.decisions_saved : current.summary.decisions_saved + 1 }, attention_items: current.attention_items.map((item) => item.item.id === itemId ? { ...item, advisor_decision: decision } : item) }));
  }

  async function complete() {
    setCompletionState("working");
    setNotice("");
    try {
      const result = await command(review.session.id, { action: "complete" }) as { session: Session; message: string; current_visit_readiness: CurrentVisitReadiness };
      setReview((current) => ({ ...current, session: result.session, can_review: false, current_visit_readiness: result.current_visit_readiness }));
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
      <section className={styles.boundary}><strong>Internal decision preparation only</strong><span>No estimate, repair authorization, work release, AI recommendation, or outbound customer message is available in this workspace.</span></section>
      <CurrentVisitControl initial={initialCurrentVisit} sessionId={review.session.id} sessionStatus={review.session.status} />
      {!review.current_visit_readiness.ready_for_future_customer_access && <section className={styles.readinessReasons} aria-label="Current Visit internal prerequisites"><ul>{review.current_visit_readiness.reasons.map((reason) => <li key={reason}>{readinessCopy[reason] ?? "An internal access prerequisite is incomplete."}</li>)}</ul></section>}
      <section className={styles.quietResults}><div><p className={styles.eyebrow}>Contained inspection record</p><h2>{review.summary.attention_count === 0 ? "No Needs attention items require triage" : "Triage only the items that need attention"}</h2><p>Good: {review.summary.good_count} · N/A: {review.summary.na_count}. They remain a quiet completed-work record—not an upsell list.</p></div></section>
      {review.attention_items.length ? <section className={styles.itemList} aria-label="Advisor disposition items">{review.attention_items.map((item) => <ReviewItem key={item.item.id} item={item} sessionId={review.session.id} writable={review.can_review} onSaved={(decision) => onDecision(item.item.id, decision)} />)}</section> : <section className={styles.empty}><h2>Ready for internal review completion</h2><p>The submitted inspection contains no technician-attested Needs attention items.</p></section>}
      {notice && <p className={completionState === "error" ? styles.error : styles.notice} role={completionState === "error" ? "alert" : "status"}>{notice}</p>}
      {review.can_review && <section className={styles.completePanel}><div><p className={styles.eyebrow}>Review completion</p><h2>{remaining ? `${remaining} item${remaining === 1 ? "" : "s"} still need${remaining === 1 ? "s" : ""} a disposition` : "Every attention item has a human disposition"}</h2><p>Completing this step records internal advisor review. It deliberately does not notify a customer or authorize any repair.</p></div><button className={styles.completeButton} disabled={remaining > 0 || completionState === "working"} type="button" onClick={complete}>{completionState === "working" ? "Recording…" : "Complete advisor review"}</button></section>}
    </main>
  );
}
