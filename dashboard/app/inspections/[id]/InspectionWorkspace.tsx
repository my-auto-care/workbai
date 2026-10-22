"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import styles from "./inspection.module.css";

type Condition = "good" | "fair" | "poor" | "na";

type TemplateItem = {
  id: string;
  name: string;
  type?: "condition" | "measurement";
  unit?: string;
  options?: string[];
};

type TemplateSection = { id: string; name: string; items: TemplateItem[] };

type ItemResponse = {
  id: string;
  template_item_id: string;
  condition: Condition;
  note?: string | null;
  measurement?: string | null;
  selected_option?: string | null;
  recorded_at?: string | null;
};

type Session = {
  id: string;
  status: "pending" | "in_progress" | "submitted" | "completed" | "abandoned";
  vehicle_year?: string | null;
  vehicle_make?: string | null;
  vehicle_model?: string | null;
  vehicle_vin?: string | null;
  vehicle_mileage?: number | null;
  customer_concern?: string | null;
  presence_mode?: "waiter" | "dropoff" | null;
  template_version?: number | null;
};

export type InspectionWorkspaceData = {
  session: Session;
  template: { id: string; version?: number | null; name: string; description?: string | null; sections: TemplateSection[] };
  responses: ItemResponse[];
  summary: { item_count: number; response_count: number };
  can_record: boolean;
  can_submit: boolean;
};

type CommandResult = ItemResponse | { session: Session; message: string } | Session;

function vehicleLabel(session: Session) {
  return [session.vehicle_year, session.vehicle_make, session.vehicle_model].filter(Boolean).join(" ") || "Vehicle details pending";
}

function conditionLabel(condition: Condition) {
  return condition === "good" ? "Good" : condition === "na" ? "N/A" : "Needs attention";
}

async function command(sessionId: string, body: Record<string, unknown>): Promise<CommandResult> {
  const response = await fetch(`/api/inspections/${sessionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = (await response.json()) as CommandResult | { detail?: string };
  if (!response.ok) throw new Error("detail" in payload && payload.detail ? payload.detail : "The inspection service could not save this result.");
  return payload as CommandResult;
}

function ItemCard({ item, saved, writable, onSave }: { item: TemplateItem; saved?: ItemResponse; writable: boolean; onSave: (payload: { condition: Condition; note: string; measurement: string; selected_option: string }) => Promise<void> }) {
  const [condition, setCondition] = useState<Condition>(saved?.condition ?? "good");
  const [note, setNote] = useState(saved?.note ?? "");
  const [measurement, setMeasurement] = useState(saved?.measurement ?? "");
  const [selectedOption, setSelectedOption] = useState(saved?.selected_option ?? "");
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");
  const [message, setMessage] = useState("");
  const needsNote = condition !== "good";

  async function save() {
    if (needsNote && !note.trim()) {
      setState("error");
      setMessage("Add a written note before saving Needs attention or N/A.");
      return;
    }
    setState("saving");
    setMessage("");
    try {
      await onSave({ condition, note, measurement, selected_option: selectedOption });
      setState("idle");
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Unable to save this result.");
    }
  }

  return (
    <article className={`${styles.itemCard} ${saved ? styles.itemCardSaved : ""}`}>
      <div className={styles.itemHead}>
        <div><p className={styles.itemId}>{item.id}</p><h3>{item.name}</h3></div>
        {saved && <span className={`${styles.resultTag} ${styles[`tag${saved.condition}`]}`}>{conditionLabel(saved.condition)}</span>}
      </div>
      {writable ? (
        <div className={styles.itemBody}>
          <fieldset className={styles.conditionChoices}>
            <legend>Result</legend>
            <label className={condition === "good" ? styles.choiceGoodActive : styles.choice}><input type="radio" name={`${item.id}-condition`} checked={condition === "good"} onChange={() => setCondition("good")} /><span>Good</span></label>
            <label className={condition === "poor" ? styles.choiceAttentionActive : styles.choice}><input type="radio" name={`${item.id}-condition`} checked={condition === "poor"} onChange={() => setCondition("poor")} /><span>Needs attention</span></label>
            <label className={condition === "na" ? styles.choiceNaActive : styles.choice}><input type="radio" name={`${item.id}-condition`} checked={condition === "na"} onChange={() => setCondition("na")} /><span>N/A</span></label>
          </fieldset>
          <div className={styles.itemFields}>
            {item.type === "measurement" && <label>Measurement{item.unit ? <span> · {item.unit}</span> : null}<input value={measurement} onChange={(event) => setMeasurement(event.target.value)} inputMode="decimal" placeholder={item.unit ? `Enter ${item.unit}` : "Enter value"} /></label>}
            {item.options && item.options.length > 0 && <label>Observation<select value={selectedOption} onChange={(event) => setSelectedOption(event.target.value)}><option value="">Select an observation</option>{item.options.map((option) => <option value={option} key={option}>{option}</option>)}</select></label>}
            <label className={styles.noteField}>Written note {needsNote ? <strong>required</strong> : <span>optional</span>}<textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} placeholder={needsNote ? "State what was observed and why it needs attention or is not applicable." : "Add a concise observation if useful."} /></label>
          </div>
          {message && <p className={styles.itemError} role="alert">{message}</p>}
          <button className={styles.saveButton} type="button" disabled={state === "saving"} onClick={save}>{state === "saving" ? "Saving…" : saved ? "Update result" : "Save result"}</button>
        </div>
      ) : saved ? (
        <div className={styles.readOnly}><p>{saved.selected_option && <><strong>Observation:</strong> {saved.selected_option}<br /></>}{saved.measurement && <><strong>Measurement:</strong> {saved.measurement}<br /></>}{saved.note ?? "No written note was recorded."}</p></div>
      ) : <p className={styles.readOnly}>No result recorded.</p>}
    </article>
  );
}

export function InspectionWorkspace({ initialWorkspace }: { initialWorkspace: InspectionWorkspaceData }) {
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const [selectedSection, setSelectedSection] = useState(initialWorkspace.template.sections[0]?.id ?? "");
  const [notice, setNotice] = useState("");
  const [submissionState, setSubmissionState] = useState<"idle" | "working" | "error">("idle");

  const responseMap = useMemo(() => new Map(workspace.responses.map((response) => [response.template_item_id, response])), [workspace.responses]);
  const activeSection = workspace.template.sections.find((section) => section.id === selectedSection) ?? workspace.template.sections[0];
  const total = workspace.summary.item_count;
  const completed = workspace.responses.length;
  const pending = Math.max(total - completed, 0);
  const active = workspace.session.status === "in_progress";
  const vehicle = vehicleLabel(workspace.session);

  async function startInspection() {
    setSubmissionState("working");
    setNotice("");
    try {
      const result = await command(workspace.session.id, { action: "start" }) as Session;
      setWorkspace((current) => ({ ...current, session: { ...current.session, ...result }, can_submit: true }));
      setNotice("Inspection started. Record each applicable item before submitting for advisor review.");
      setSubmissionState("idle");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to start inspection.");
      setSubmissionState("error");
    }
  }

  async function saveItem(itemId: string, payload: { condition: Condition; note: string; measurement: string; selected_option: string }) {
    const response = await command(workspace.session.id, { action: "record", item_id: itemId, ...payload }) as ItemResponse;
    setWorkspace((current) => {
      const prior = current.responses.filter((item) => item.template_item_id !== response.template_item_id);
      return { ...current, responses: [...prior, response], summary: { ...current.summary, response_count: prior.length + 1 } };
    });
  }

  async function submitInspection() {
    setSubmissionState("working");
    setNotice("");
    try {
      const result = await command(workspace.session.id, { action: "submit" }) as { session: Session; message: string };
      setWorkspace((current) => ({ ...current, session: { ...current.session, ...result.session }, can_submit: false }));
      setNotice(result.message);
      setSubmissionState("idle");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to submit inspection.");
      setSubmissionState("error");
    }
  }

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <div><p className={styles.eyebrow}>Workbai · technician workspace</p><h1>{vehicle}</h1><p className={styles.subhead}>Original concern: <strong>{workspace.session.customer_concern || "Not recorded"}</strong></p></div>
        <Link href="/queue" className={styles.backLink}>Inspection queue</Link>
      </header>

      <section className={styles.context} aria-label="Inspection context">
        <div><span>Arrival</span><strong>{workspace.session.presence_mode === "waiter" ? "Waiter" : workspace.session.presence_mode === "dropoff" ? "Drop-off" : "Not recorded"}</strong></div>
        <div><span>Template</span><strong>{workspace.template.name} · v{workspace.template.version ?? "—"}</strong></div>
        <div><span>Coverage</span><strong>{completed} of {total} rated</strong></div>
        <div><span>Status</span><strong className={styles.status}>{workspace.session.status === "submitted" ? "Submitted for advisor review" : workspace.session.status.replace("_", " ")}</strong></div>
      </section>

      <section className={styles.provisional}>
        <strong>Provisional template workflow</strong><span>This is a versioned test template, not the approved final inspection sheet. It cannot send a customer report, create an estimate, or authorize work.</span>
      </section>

      {workspace.session.status === "pending" && workspace.can_record && <section className={styles.startPanel}><div><p className={styles.eyebrow}>Vehicle ready</p><h2>Start the assigned inspection</h2><p>The customer’s original concern stays visible while you rate the controlled template.</p></div><button className={styles.primaryAction} type="button" disabled={submissionState === "working"} onClick={startInspection}>{submissionState === "working" ? "Starting…" : "Start inspection"}</button></section>}

      {notice && <p className={submissionState === "error" ? styles.noticeError : styles.notice} role={submissionState === "error" ? "alert" : "status"}>{notice}</p>}

      {workspace.session.status !== "pending" && activeSection && <>
        <nav className={styles.sectionNav} aria-label="Inspection sections">
          {workspace.template.sections.map((section) => {
            const count = section.items.filter((item) => responseMap.has(item.id)).length;
            return <button className={selectedSection === section.id ? styles.sectionActive : styles.sectionButton} type="button" onClick={() => setSelectedSection(section.id)} key={section.id}>{section.name}<span>{count}/{section.items.length}</span></button>;
          })}
        </nav>
        <section className={styles.workspace} aria-labelledby="section-title">
          <header className={styles.workspaceHead}><p className={styles.eyebrow}>Section {workspace.template.sections.findIndex((section) => section.id === activeSection.id) + 1}</p><h2 id="section-title">{activeSection.name}</h2><p>Record a result for each item. Needs attention and N/A require a written note. An unfilled item is never treated as Good.</p></header>
          <div className={styles.itemList}>
            {activeSection.items.map((item) => <ItemCard key={item.id} item={item} saved={responseMap.get(item.id)} writable={workspace.can_record && active} onSave={(payload) => saveItem(item.id, payload)} />)}
          </div>
        </section>
      </>}

      {workspace.can_submit && active && <section className={styles.submitPanel}><div><p className={styles.eyebrow}>Advisor handoff</p><h2>{pending === 0 ? "Every template item has a result" : `${pending} item${pending === 1 ? "" : "s"} still need${pending === 1 ? "s" : ""} a result`}</h2><p>Submitting records this inspection for advisor review only. It does not send customer communication, create an estimate, approve repairs, or close the visit.</p></div><button className={styles.primaryAction} type="button" disabled={pending > 0 || submissionState === "working"} onClick={submitInspection}>{submissionState === "working" ? "Submitting…" : "Submit for advisor review"}</button></section>}
    </main>
  );
}
