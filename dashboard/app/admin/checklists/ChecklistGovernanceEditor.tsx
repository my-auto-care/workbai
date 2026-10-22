"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type Lifecycle = "draft" | "approved" | "retired";

type TemplateRecord = {
  id: string;
  name: string;
  version: number;
  items: unknown;
  lifecycle_status: Lifecycle;
  is_provisional: boolean;
  locked_provisional: boolean;
  active_for_new_visits: boolean;
  source_reference: string | null;
  source_sha256: string | null;
  approved_at: string | null;
  retired_at: string | null;
};

const exampleDocument = JSON.stringify(
  {
    name: "Controlled inspection draft",
    description: "Draft content only. Do not treat as an approved inspection sheet.",
    sections: [
      {
        id: "section_1",
        name: "Section name",
        items: [{ id: "item_1", name: "Item name", type: "condition", allow_na: false }],
      },
    ],
  },
  null,
  2,
);

function detail(body: unknown, fallback: string) {
  if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") return body.detail;
  return fallback;
}

function statusLabel(status: Lifecycle) {
  return status === "approved" ? "Approved" : status === "retired" ? "Retired" : "Draft";
}

export function ChecklistGovernanceEditor({ templateId }: { templateId?: string }) {
  const router = useRouter();
  const [record, setRecord] = useState<TemplateRecord | null>(null);
  const [name, setName] = useState("");
  const [documentText, setDocumentText] = useState(exampleDocument);
  const [isProvisional, setIsProvisional] = useState(true);
  const [sourceReference, setSourceReference] = useState("");
  const [sourceHash, setSourceHash] = useState("");
  const [state, setState] = useState<"loading" | "idle" | "saving" | "error">(templateId ? "loading" : "idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!templateId) return;
    fetch(`/api/checklists/${templateId}`, { cache: "no-store" })
      .then(async (response) => {
        const body = (await response.json()) as TemplateRecord | { detail?: string };
        if (!response.ok) throw new Error(detail(body, "Unable to load this template."));
        return body as TemplateRecord;
      })
      .then((template) => {
        setRecord(template);
        setName(template.name);
        setDocumentText(JSON.stringify(template.items, null, 2));
        setIsProvisional(template.is_provisional);
        setSourceReference(template.source_reference ?? "");
        setSourceHash(template.source_sha256 ?? "");
        setState("idle");
      })
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : "Unable to load this template.");
        setState("error");
      });
  }, [templateId]);

  const editable = !record || record.lifecycle_status === "draft";
  const validHash = /^[a-f0-9]{64}$/.test(sourceHash.trim().toLowerCase());
  const canApprove = !!record && record.lifecycle_status === "draft" && !record.locked_provisional && !isProvisional && sourceReference.trim().length >= 3 && validHash;
  const sourceState = useMemo(() => {
    if (record?.locked_provisional) return "Legacy/provisional content is permanently ineligible for approval. Create a new controlled draft from the verified artifact.";
    if (isProvisional) return "Provisional: never eligible for new live visits.";
    if (!sourceReference.trim() || !validHash) return "A source reference and exact SHA-256 are required before approval.";
    return "Artifact provenance is complete. An administrator may approve this immutable version.";
  }, [isProvisional, record?.locked_provisional, sourceReference, validHash]);

  async function saveDraft() {
    let items: unknown;
    try {
      items = JSON.parse(documentText);
    } catch {
      setState("error");
      setMessage("Template JSON is not valid. Correct it before saving.");
      return;
    }
    setState("saving");
    setMessage("");
    const payload = {
      name,
      items,
      is_provisional: isProvisional,
      source_reference: sourceReference || null,
      source_sha256: sourceHash ? sourceHash.trim().toLowerCase() : null,
    };
    try {
      const response = await fetch(templateId ? `/api/checklists/${templateId}` : "/api/checklists", {
        method: templateId ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await response.json()) as TemplateRecord | { detail?: string };
      if (!response.ok) throw new Error(detail(body, "Unable to save the template draft."));
      const saved = body as TemplateRecord;
      if (!templateId) router.replace(`/admin/checklists/${saved.id}`);
      else {
        setRecord(saved);
        setDocumentText(JSON.stringify(saved.items, null, 2));
        setState("idle");
        setMessage("Draft saved. It is not active for new visits.");
      }
    } catch (error: unknown) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Unable to save the template draft.");
    }
  }

  async function lifecycle(action: "approve" | "retire") {
    if (!templateId) return;
    const confirmation = action === "approve"
      ? "Approve this non-provisional, source-hashed template as the only active template for new visits?"
      : "Retire this template? It will remain readable for historical inspection records but cannot start a new visit.";
    if (!window.confirm(confirmation)) return;
    setState("saving");
    setMessage("");
    try {
      const response = await fetch(`/api/checklists/${templateId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(action === "approve" ? { action, confirm_controlled_artifact: true } : { action, confirm_retirement: true }),
      });
      const body = (await response.json()) as TemplateRecord | { detail?: string };
      if (!response.ok) throw new Error(detail(body, "Unable to update the template lifecycle."));
      setRecord(body as TemplateRecord);
      setState("idle");
      setMessage(action === "approve" ? "Approved and made active for new visits." : "Template retired. Historical snapshots remain available.");
    } catch (error: unknown) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Unable to update the template lifecycle.");
    }
  }

  if (state === "loading") return <main className="workbai-home"><section><p className="home-kicker">Workbai · template governance</p><h1>Loading template record</h1></section></main>;
  if (state === "error" && !record) return <main className="workbai-home"><section><p className="home-kicker">Workbai · template governance</p><h1>Template unavailable</h1><p className="home-copy">{message}</p><Link className="home-secondary" href="/admin/checklists">Return to templates</Link></section></main>;

  return (
    <main className="min-h-screen bg-[#f1ece3] px-5 py-9 text-[#1f3a47] sm:px-8">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-[#c9d7d8] pb-6">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-[.14em] text-[#087e91]">Workbai · controlled template</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">{record ? record.name : "Create template draft"}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#58717b]">A draft is editable. Only a non-provisional template with recorded artifact provenance can be approved and activated.</p>
          </div>
          <Link className="text-sm font-bold text-[#087e91]" href="/admin/checklists">Template registry</Link>
        </header>

        {record && <section className="mb-6 grid gap-3 rounded-2xl border border-[#cadadb] bg-[#fbf8f2] p-5 shadow-sm sm:grid-cols-3">
          <div><p className="text-xs font-bold uppercase tracking-[.11em] text-[#6a8189]">Lifecycle</p><p className="mt-2 font-semibold">{statusLabel(record.lifecycle_status)}{record.active_for_new_visits ? " · active for new visits" : ""}</p></div>
          <div><p className="text-xs font-bold uppercase tracking-[.11em] text-[#6a8189]">Template version</p><p className="mt-2 font-semibold">v{record.version}</p></div>
          <div><p className="text-xs font-bold uppercase tracking-[.11em] text-[#6a8189]">Customer impact</p><p className="mt-2 font-semibold">No customer release</p></div>
        </section>}

        {message && <p className={`mb-5 rounded-xl border px-4 py-3 text-sm ${state === "error" ? "border-[#d98b7e] bg-[#fff1ec] text-[#8d392e]" : "border-[#96c8c3] bg-[#e7f4f1] text-[#175d62]"}`} role="status">{message}</p>}

        <section className="rounded-2xl border border-[#cadadb] bg-[#fbf8f2] p-5 shadow-sm sm:p-7">
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="grid gap-2 text-sm font-semibold">Template name
              <input disabled={!editable || state === "saving"} value={name} onChange={(event) => setName(event.target.value)} className="min-h-12 rounded-xl border border-[#adc3c7] bg-white px-3 text-[#1f3a47] disabled:cursor-not-allowed disabled:bg-[#edf1ef]" />
            </label>
            <label className="grid gap-2 text-sm font-semibold">Lifecycle status
              <output className="flex min-h-12 items-center rounded-xl border border-[#d4dfdf] bg-[#eef5f4] px-3 font-medium text-[#305863]">{record ? statusLabel(record.lifecycle_status) : "Draft on creation"}</output>
            </label>
          </div>

          <fieldset className="mt-6 border-0 p-0" disabled={!editable || state === "saving"}>
            <legend className="text-sm font-semibold">Template classification</legend>
            <label className="mt-3 flex gap-3 rounded-xl border border-[#cadadb] bg-white p-4 text-sm leading-6">
              <input className="mt-1 size-4 accent-[#087e91]" type="checkbox" disabled={record?.locked_provisional} checked={isProvisional} onChange={(event) => setIsProvisional(event.target.checked)} />
              <span><strong>{record?.locked_provisional ? "Legacy provisional content (locked)" : "Provisional test content"}</strong><br /><span className="text-[#58717b]">{record?.locked_provisional ? "This pre-governance template is preserved only for record continuity and can never become active." : "Keep checked until the approved inspection artifact is retrieved, hashed, and reviewed. Provisional content cannot become active for new visits."}</span></span>
            </label>
          </fieldset>

          <div className="mt-6 grid gap-5 sm:grid-cols-[1fr_220px]">
            <label className="grid gap-2 text-sm font-semibold">Controlled source reference
              <input disabled={!editable || state === "saving"} value={sourceReference} onChange={(event) => setSourceReference(event.target.value)} placeholder="Controlled library record or artifact reference" className="min-h-12 rounded-xl border border-[#adc3c7] bg-white px-3 text-[#1f3a47] disabled:cursor-not-allowed disabled:bg-[#edf1ef]" />
            </label>
            <label className="grid gap-2 text-sm font-semibold">Artifact SHA-256
              <input disabled={!editable || state === "saving"} value={sourceHash} onChange={(event) => setSourceHash(event.target.value.toLowerCase())} placeholder="64 lowercase hex" maxLength={64} className="min-h-12 rounded-xl border border-[#adc3c7] bg-white px-3 font-mono text-xs text-[#1f3a47] disabled:cursor-not-allowed disabled:bg-[#edf1ef]" />
            </label>
          </div>
          <p className="mt-2 text-sm text-[#58717b]">{sourceState}</p>

          <label className="mt-7 grid gap-2 text-sm font-semibold">Template document JSON
            <textarea disabled={!editable || state === "saving"} value={documentText} onChange={(event) => setDocumentText(event.target.value)} rows={18} spellCheck={false} className="min-h-80 rounded-xl border border-[#adc3c7] bg-[#fdfcf8] p-4 font-mono text-xs leading-5 text-[#234651] disabled:cursor-not-allowed disabled:bg-[#edf1ef]" />
          </label>
          <p className="mt-2 text-sm leading-6 text-[#58717b]">Workbai validates section/item identity and option structure. This screen does not infer unverified form rows, torque values, or thresholds.</p>

          <div className="mt-7 flex flex-wrap gap-3 border-t border-[#d9e3e2] pt-6">
            {editable && <button type="button" onClick={saveDraft} disabled={state === "saving"} className="min-h-12 rounded-xl bg-[#087e91] px-5 text-sm font-bold text-white shadow-sm transition hover:bg-[#056f80] disabled:cursor-not-allowed disabled:opacity-50">{state === "saving" ? "Saving…" : record ? "Save draft" : "Create draft"}</button>}
            {canApprove && <button type="button" onClick={() => lifecycle("approve")} disabled={state === "saving"} className="min-h-12 rounded-xl border border-[#087e91] bg-[#e5f4f2] px-5 text-sm font-bold text-[#075b69] hover:bg-[#d6eeeb] disabled:cursor-not-allowed disabled:opacity-50">Approve & activate</button>}
            {record?.lifecycle_status === "approved" && <button type="button" onClick={() => lifecycle("retire")} disabled={state === "saving"} className="min-h-12 rounded-xl border border-[#b48938] bg-[#fff6df] px-5 text-sm font-bold text-[#795a18] hover:bg-[#ffedbf] disabled:cursor-not-allowed disabled:opacity-50">Retire template</button>}
          </div>
        </section>
      </div>
    </main>
  );
}
