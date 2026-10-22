"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import styles from "./checkin.module.css";

export type CheckinOptions = {
  actor: { name: string; role: "advisor" | "admin"; shop_id: string };
  technicians: Array<{ id: string; name: string }>;
  checklists: Array<{ id: string; name: string; version: number; vehicle_filter: Record<string, unknown> }>;
  customer_contact_capture_enabled: boolean;
  customer_context_enabled: boolean;
  common_intake_wording: string[];
};

type VehicleCandidate = { id: string; label: string; year: number; make: string; model: string; mileage?: number | null; catalog_entry_id?: string | null; customer_relationship_confirmed?: boolean };
type CustomerCandidate = { id: string; display_name: string; contacts: Array<{ channel: string; label: string }>; vehicles: VehicleCandidate[] };
type CatalogCandidate = { id: string; label: string; year: number; make: string; model: string; source: { name: string; retrieved_at: string; url: string } };
type LookupResults = { customers: CustomerCandidate[]; shop_vehicles: VehicleCandidate[]; catalog_vehicles: CatalogCandidate[] };
type Context = { history: Array<{ session_id: string; started_at: string; status: string; vehicle_label: string }>; reason_suggestions: Array<{ id: string; kind: "reviewed_context" | "curated_prompt" | "common_prompt"; label: string; source_label: string; source_type: string }> };

type FormState = {
  vehicle_year: string;
  vehicle_make: string;
  vehicle_model: string;
  vehicle_vin: string;
  vehicle_mileage: string;
  customer_concern: string;
  presence_mode: string;
  assigned_technician_id: string;
  customer_contact_channel: "sms" | "email";
  customer_contact_destination: string;
  current_visit_link_consent: "granted" | "declined" | "not_asked";
  current_visit_progress_consent: "granted" | "declined" | "not_asked";
  new_customer_name: string;
  new_customer_phone: string;
  new_customer_email: string;
};

type Result = { id: string; status: string; vehicle_year: string; vehicle_make: string; vehicle_model: string; customer_contact_recorded?: boolean; customer_profile_recorded?: boolean };

export function CheckinForm({ options, userName }: { options: CheckinOptions; userName: string }) {
  const [form, setForm] = useState<FormState>({
    vehicle_year: "", vehicle_make: "", vehicle_model: "", vehicle_vin: "", vehicle_mileage: "", customer_concern: "", presence_mode: "", assigned_technician_id: options.technicians[0]?.id ?? "", customer_contact_channel: "sms", customer_contact_destination: "", current_visit_link_consent: "not_asked", current_visit_progress_consent: "not_asked", new_customer_name: "", new_customer_phone: "", new_customer_email: "",
  });
  const [state, setState] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [lookupQuery, setLookupQuery] = useState("");
  const [lookup, setLookup] = useState<LookupResults | null>(null);
  const [lookupState, setLookupState] = useState<"idle" | "loading" | "error">("idle");
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerCandidate | null>(null);
  const [selectedVehicle, setSelectedVehicle] = useState<VehicleCandidate | null>(null);
  const [selectedCatalog, setSelectedCatalog] = useState<CatalogCandidate | null>(null);
  const [newCustomerOpen, setNewCustomerOpen] = useState(false);
  const [customerVehicleConfirmation, setCustomerVehicleConfirmation] = useState(false);
  const [context, setContext] = useState<Context | null>(null);
  const [contextState, setContextState] = useState<"idle" | "loading" | "error">("idle");
  const [selectedReason, setSelectedReason] = useState<{ kind: string; id: string } | null>(null);

  const ready = useMemo(() => options.technicians.length > 0 && options.checklists.length > 0, [options.checklists.length, options.technicians.length]);
  const hasNewCustomer = newCustomerOpen && form.new_customer_name.trim().length >= 2;
  const hasVehicleDetails = Boolean(form.vehicle_year && form.vehicle_make.trim() && form.vehicle_model.trim());
  const vehicleAlreadyLinkedToSelectedCustomer = Boolean(selectedCustomer && selectedVehicle && selectedCustomer.vehicles.some((vehicle) => vehicle.id === selectedVehicle.id && vehicle.customer_relationship_confirmed));
  const needsRelationshipConfirmation = Boolean((selectedCustomer || hasNewCustomer) && hasVehicleDetails && !vehicleAlreadyLinkedToSelectedCustomer);
  const contextKey = `${selectedCustomer?.id ?? ""}:${selectedVehicle?.id ?? ""}`;

  useEffect(() => {
    if (lookupQuery.trim().length < 2) return;
    let live = true;
    const timer = window.setTimeout(async () => {
      setLookupState("loading");
      try {
        const response = await fetch("/api/check-in/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: lookupQuery.trim() }), cache: "no-store" });
        const body = (await response.json()) as LookupResults | { detail?: string };
        if (!response.ok) throw new Error("detail" in body && body.detail ? body.detail : "Customer lookup is unavailable");
        if (live) { setLookup(body as LookupResults); setLookupState("idle"); }
      } catch {
        if (live) { setLookup(null); setLookupState("error"); }
      }
    }, 220);
    return () => { live = false; window.clearTimeout(timer); };
  }, [lookupQuery]);

  useEffect(() => {
    if (!options.customer_context_enabled || (!selectedCustomer && !selectedVehicle)) return;
    let live = true;
    const query = new URLSearchParams();
    if (selectedCustomer) query.set("customer_id", selectedCustomer.id);
    if (selectedVehicle) query.set("vehicle_id", selectedVehicle.id);
    const timer = window.setTimeout(async () => {
      setContextState("loading");
      try {
        const response = await fetch(`/api/check-in/context?${query.toString()}`, { cache: "no-store" });
        const body = (await response.json()) as Context | { detail?: string };
        if (!response.ok) throw new Error("detail" in body && body.detail ? body.detail : "Customer context is unavailable");
        if (live) { setContext(body as Context); setContextState("idle"); }
      } catch {
        if (live) { setContext(null); setContextState("error"); }
      }
    }, 100);
    return () => { live = false; window.clearTimeout(timer); };
  }, [contextKey, options.customer_context_enabled, selectedCustomer, selectedVehicle]);

  function update(key: keyof FormState, value: string) { setForm((current) => ({ ...current, [key]: value })); }
  function applyVehicle(candidate: VehicleCandidate) {
    setSelectedVehicle(candidate);
    setSelectedCatalog(null);
    setCustomerVehicleConfirmation(candidate.customer_relationship_confirmed ?? false);
    setSelectedReason(null);
    setForm((current) => ({ ...current, vehicle_year: String(candidate.year), vehicle_make: candidate.make, vehicle_model: candidate.model, vehicle_mileage: candidate.mileage ? String(candidate.mileage) : current.vehicle_mileage }));
  }
  function applyCatalog(candidate: CatalogCandidate) {
    setSelectedCatalog(candidate);
    setSelectedVehicle(null);
    setCustomerVehicleConfirmation(false);
    setSelectedReason(null);
    setForm((current) => ({ ...current, vehicle_year: String(candidate.year), vehicle_make: candidate.make, vehicle_model: candidate.model }));
  }
  function applyCustomer(customer: CustomerCandidate) {
    setSelectedCustomer(customer);
    setNewCustomerOpen(false);
    setSelectedVehicle(null);
    setSelectedCatalog(null);
    setCustomerVehicleConfirmation(false);
    setSelectedReason(null);
    if (customer.vehicles.length === 1) applyVehicle(customer.vehicles[0]);
  }
  function chooseReason(suggestion: Context["reason_suggestions"][number]) {
    setForm((current) => ({ ...current, customer_concern: suggestion.label }));
    setSelectedReason({ kind: suggestion.kind, id: suggestion.id });
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready || state === "saving") return;
    setState("saving"); setMessage("");
    const { customer_contact_channel, customer_contact_destination, current_visit_link_consent, current_visit_progress_consent, new_customer_name, new_customer_phone, new_customer_email, ...visit } = form;
    const contacts = [] as Array<{ channel: "sms" | "email"; destination: string }>;
    if (new_customer_phone.trim()) contacts.push({ channel: "sms", destination: new_customer_phone.trim() });
    if (new_customer_email.trim()) contacts.push({ channel: "email", destination: new_customer_email.trim() });
    const payload = {
      ...visit,
      vehicle_year: Number(form.vehicle_year), vehicle_mileage: form.vehicle_mileage ? Number(form.vehicle_mileage) : null, vehicle_vin: form.vehicle_vin || null,
      customer_id: selectedCustomer?.id ?? null,
      new_customer: newCustomerOpen && new_customer_name.trim() ? { display_name: new_customer_name.trim(), contacts } : null,
      vehicle_id: selectedVehicle?.id ?? null,
      vehicle_catalog_entry_id: selectedCatalog?.id ?? selectedVehicle?.catalog_entry_id ?? null,
      customer_vehicle_confirmation: customerVehicleConfirmation,
      reason_context_record_id: selectedReason?.kind === "reviewed_context" ? selectedReason.id : null,
      reason_suggestion_id: selectedReason?.kind === "curated_prompt" ? selectedReason.id : null,
      customer_contact: options.customer_contact_capture_enabled && customer_contact_destination.trim() ? { channel: customer_contact_channel, destination: customer_contact_destination.trim(), current_visit_link_consent, current_visit_progress_consent } : null,
    };
    try {
      const response = await fetch("/api/check-in", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const body = (await response.json()) as Result | { detail?: string };
      if (!response.ok) throw new Error("detail" in body && body.detail ? body.detail : "Unable to start this inspection");
      setResult(body as Result); setState("success");
    } catch (error) { setState("error"); setMessage(error instanceof Error ? error.message : "Unable to start this inspection"); }
  }

  if (state === "success" && result) {
    const vehicle = [result.vehicle_year, result.vehicle_make, result.vehicle_model].filter(Boolean).join(" ");
    return <main className={styles.shell}><section className={styles.receipt} aria-labelledby="started-title"><div className={styles.receiptMark} aria-hidden="true">✓</div><p className={styles.eyebrow}>Inspection handoff recorded</p><h1 id="started-title">{vehicle}</h1><p className={styles.receiptCopy}>{result.customer_profile_recorded ? "The internal customer and vehicle context were linked to this canonical visit. No customer message, portal link, repair approval, or DVI report was sent." : "The inspection is pending in the assigned technician’s queue. No customer message, portal link, repair approval, or DVI report was sent."}</p><div className={styles.receiptActions}><Link className={styles.primaryAction} href="/queue">Open inspection queue</Link><button className={styles.secondaryAction} onClick={() => { setResult(null); setState("idle"); setSelectedReason(null); setLookupQuery(""); setSelectedCustomer(null); setSelectedVehicle(null); setSelectedCatalog(null); setContext(null); setForm((current) => ({ ...current, vehicle_vin: "", vehicle_mileage: "", customer_concern: "", customer_contact_destination: "", new_customer_name: "", new_customer_phone: "", new_customer_email: "", current_visit_link_consent: "not_asked", current_visit_progress_consent: "not_asked" })); }}>Start another check-in</button></div></section></main>;
  }

  return <main className={styles.shell}>
    <header className={styles.topbar}><div><p className={styles.eyebrow}>Workbai · {options.actor.role}</p><h1>Start an inspection</h1></div><div className={styles.headerTools}><Link className={styles.callDeskLink} href="/call-desk">Call desk</Link><div className={styles.operator}>{userName}</div></div></header>
    <section className={styles.context} aria-label="Check-in context"><div><span className={styles.contextLabel}>Shop</span><strong>Assigned shop</strong></div><div><span className={styles.contextLabel}>Outcome</span><strong>Pending technician handoff</strong></div></section>
    {!ready && <section className={styles.blocked} role="alert"><h2>Setup is incomplete</h2>{options.checklists.length === 0 && <p>No approved, non-provisional inspection template is active. An administrator must approve the verified controlled artifact before any visit can begin.</p>}{options.technicians.length === 0 && <p>No active technician is available in this shop. Assign one before beginning Check-in.</p>}</section>}
    <form className={styles.form} onSubmit={submit}>
      <section className={styles.section}><div className={styles.sectionHead}><span className={styles.step}>01</span><div><h2>Find customer or vehicle</h2><p>Search a known customer, phone, email, 8-character VIN tail, or type a vehicle in one line—such as “2017 Toyota Highlander.” A result is a candidate, not proof of identity or ownership.</p></div></div>
        <label className={styles.fullLabel}>Rapid find<input value={lookupQuery} onChange={(event) => setLookupQuery(event.target.value)} placeholder="Customer, phone, email, VIN tail, or 2017 Toyota Highlander" autoComplete="off" /></label>{lookupState === "loading" && <p className={styles.lookupHint}>Searching available customer and vehicle records…</p>}{lookupState === "error" && <p className={styles.lookupHint}>Lookup is temporarily unavailable. Use manual entry below.</p>}{lookup && <div className={styles.lookupResults} aria-live="polite">{lookup.customers.map((customer) => <button type="button" key={customer.id} className={styles.lookupResult} onClick={() => applyCustomer(customer)}><span><strong>{customer.display_name}</strong><small>{customer.contacts.map((contact) => contact.label).join(" · ") || "Customer profile"}</small></span><em>{customer.vehicles.length === 1 ? customer.vehicles[0].label : `${customer.vehicles.length} confirmed vehicles`}</em></button>)}{lookup.shop_vehicles.map((vehicle) => <button type="button" key={vehicle.id} className={styles.lookupResult} onClick={() => applyVehicle(vehicle)}><span><strong>{vehicle.label}</strong><small>Existing shop vehicle record</small></span><em>Use vehicle</em></button>)}{lookup.catalog_vehicles.map((vehicle) => <button type="button" key={vehicle.id} className={styles.lookupResult} onClick={() => applyCatalog(vehicle)}><span><strong>{vehicle.label}</strong><small>Reference catalog · confirm before starting</small></span><em>Use details</em></button>)}</div>}{!options.customer_context_enabled && <p className={styles.note}>The reference vehicle catalog remains available. Protected customer profiles and history are not configured in this environment.</p>}
        <div className={styles.selectionRail}>{selectedCustomer && <span className={styles.selectionChip}>Customer: {selectedCustomer.display_name}<button type="button" onClick={() => { setSelectedCustomer(null); setCustomerVehicleConfirmation(false); setSelectedReason(null); }} aria-label="Clear customer">×</button></span>}{selectedVehicle && <span className={styles.selectionChip}>Vehicle: {selectedVehicle.label}<button type="button" onClick={() => { setSelectedVehicle(null); setCustomerVehicleConfirmation(false); setSelectedReason(null); }} aria-label="Clear vehicle">×</button></span>}{selectedCatalog && <span className={styles.selectionChip}>Catalog: {selectedCatalog.label}<button type="button" onClick={() => { setSelectedCatalog(null); setSelectedReason(null); }} aria-label="Clear catalog match">×</button></span>}</div>
        {options.customer_context_enabled && <button type="button" className={styles.textLink} onClick={() => { setNewCustomerOpen((current) => !current); setSelectedCustomer(null); setCustomerVehicleConfirmation(false); setSelectedReason(null); }}> {newCustomerOpen ? "Use an existing customer" : "Create a new protected customer profile"}</button>}
        {newCustomerOpen && <div className={styles.newCustomer}><div className={styles.gridThree}><label>Customer name<input required value={form.new_customer_name} onChange={(event) => update("new_customer_name", event.target.value)} placeholder="Customer name" /></label><label>Mobile <span className={styles.optional}>optional</span><input value={form.new_customer_phone} onChange={(event) => update("new_customer_phone", event.target.value)} placeholder="+15551234567" /></label><label>Email <span className={styles.optional}>optional</span><input value={form.new_customer_email} onChange={(event) => update("new_customer_email", event.target.value)} placeholder="customer@example.com" /></label></div><p className={styles.lookupHint}>Profile fields are encrypted and become searchable only for staff in this shop.</p></div>}
      </section>
      <section className={styles.section}><div className={styles.sectionHead}><span className={styles.step}>02</span><div><h2>Confirm vehicle</h2><p>Catalog results fill a starting point. Confirm or correct the actual vehicle with the customer; manual entry always remains available.</p></div></div><div className={styles.gridThree}><label>Year<input required inputMode="numeric" min="1886" max="2100" value={form.vehicle_year} onChange={(event) => { update("vehicle_year", event.target.value); setSelectedCatalog(null); setSelectedVehicle(null); setCustomerVehicleConfirmation(false); setSelectedReason(null); }} placeholder="2021" /></label><label>Make<input required value={form.vehicle_make} onChange={(event) => { update("vehicle_make", event.target.value); setSelectedCatalog(null); setSelectedVehicle(null); setCustomerVehicleConfirmation(false); setSelectedReason(null); }} placeholder="Toyota" /></label><label>Model<input required value={form.vehicle_model} onChange={(event) => { update("vehicle_model", event.target.value); setSelectedCatalog(null); setSelectedVehicle(null); setCustomerVehicleConfirmation(false); setSelectedReason(null); }} placeholder="Camry" /></label></div><div className={styles.gridTwo}><label>VIN <span className={styles.optional}>optional</span><input className={styles.mono} maxLength={17} value={form.vehicle_vin} onChange={(event) => update("vehicle_vin", event.target.value.toUpperCase())} placeholder="17-character VIN" /></label><label>Mileage <span className={styles.optional}>optional</span><input inputMode="numeric" min="0" max="2000000" value={form.vehicle_mileage} onChange={(event) => update("vehicle_mileage", event.target.value)} placeholder="48,000" /></label></div>{needsRelationshipConfirmation && <label className={styles.confirmLink}><input required type="checkbox" checked={customerVehicleConfirmation} onChange={(event) => setCustomerVehicleConfirmation(event.target.checked)} />I confirmed with the customer that this vehicle is associated with their profile. This records a shop relationship, not ownership or repair authority.</label>}<p className={styles.note}>Plate and VIN image scanning remain a separate consent-led flow. This release uses confirmed manual entry and reference catalog matching only.</p></section>
      {(selectedCustomer || selectedVehicle) && options.customer_context_enabled && <section className={styles.contextPanel}><div><p className={styles.contextLabel}>Conversation context</p><strong>{contextState === "loading" ? "Loading staff context…" : "History and customer wording"}</strong></div>{contextState === "error" && <p>Context is unavailable; continue with confirmed customer wording.</p>}{context && <><div className={styles.contextHistory}>{context.history.length > 0 ? context.history.slice(0, 3).map((visit) => <span key={visit.session_id}>{visit.vehicle_label} · {visit.status.replace("_", " ")}</span>) : <span>No linked visits yet</span>}</div><p className={styles.contextCopy}>Suggestions are drafts only. Confirm or edit the wording with the customer. They are not a diagnosis, inspection result, service recommendation, or authorization.</p><div className={styles.suggestionRail}>{context.reason_suggestions.slice(0, 10).map((suggestion) => <button type="button" key={`${suggestion.kind}-${suggestion.id}`} onClick={() => chooseReason(suggestion)} className={selectedReason?.id === suggestion.id ? styles.suggestionActive : styles.suggestion}><span>{suggestion.label}</span><small>{suggestion.source_label}</small></button>)}</div></>}</section>}
      <section className={styles.section}><div className={styles.sectionHead}><span className={styles.step}>03</span><div><h2>Reason for visit</h2><p>Capture the customer’s confirmed words. A selected prompt is a draft and never diagnoses or promises work.</p></div></div><label className={styles.fullLabel}>Customer-stated concern<textarea required minLength={3} maxLength={1000} value={form.customer_concern} onChange={(event) => update("customer_concern", event.target.value)} placeholder="Example: Steering wheel shakes while braking on the highway." rows={4} /></label>{selectedReason && <p className={styles.lookupHint}>Source retained as a staff audit trail; your edited customer wording above remains the visit’s record.</p>}</section>
      <section className={styles.section}><div className={styles.sectionHead}><span className={styles.step}>04</span><div><h2>Arrival type</h2><p>Mark the operational handoff before the vehicle goes to the technician.</p></div></div><fieldset className={styles.arrivalChoices}><legend>Is the customer waiting or dropping off?</legend><label className={form.presence_mode === "waiter" ? styles.arrivalChoiceActive : styles.arrivalChoice}><input required type="radio" name="presence_mode" value="waiter" checked={form.presence_mode === "waiter"} onChange={(event) => update("presence_mode", event.target.value)} /><span><strong>Waiter</strong><small>Needs a timely progress handoff.</small></span></label><label className={form.presence_mode === "dropoff" ? styles.arrivalChoiceActive : styles.arrivalChoice}><input required type="radio" name="presence_mode" value="dropoff" checked={form.presence_mode === "dropoff"} onChange={(event) => update("presence_mode", event.target.value)} /><span><strong>Drop-off</strong><small>Customer will not wait on site.</small></span></label></fieldset></section>
      {options.customer_contact_capture_enabled && <section className={styles.section}><div className={styles.sectionHead}><span className={styles.step}>05</span><div><h2>Customer contact & permissions <span className={styles.optional}>optional</span></h2><p>This visit-only contact record does not create or merge a customer profile.</p></div></div><div className={styles.gridTwo}><label>Contact method<select value={form.customer_contact_channel} onChange={(event) => update("customer_contact_channel", event.target.value)}><option value="sms">Mobile number</option><option value="email">Email address</option></select></label><label>{form.customer_contact_channel === "sms" ? "Mobile number" : "Email address"}<input value={form.customer_contact_destination} onChange={(event) => update("customer_contact_destination", event.target.value)} placeholder={form.customer_contact_channel === "sms" ? "+15551234567" : "customer@example.com"} /></label></div><fieldset className={styles.consentChoices}><legend>May we use this contact for this visit?</legend><p>This does not authorize repairs or promotional messages. The customer may decline and still receive service.</p><label>Private visit link<select value={form.current_visit_link_consent} onChange={(event) => update("current_visit_link_consent", event.target.value)}><option value="not_asked">Not discussed</option><option value="granted">Yes — customer agreed</option><option value="declined">No — customer declined</option></select></label><label>Visit progress updates<select value={form.current_visit_progress_consent} onChange={(event) => update("current_visit_progress_consent", event.target.value)}><option value="not_asked">Not discussed</option><option value="granted">Yes — customer agreed</option><option value="declined">No — customer declined</option></select></label></fieldset><p className={styles.note}>No message is sent at Check-in. Customer access and any delivery remain manager-controlled and require separate release checks.</p></section>}
      <section className={styles.section}><div className={styles.sectionHead}><span className={styles.step}>{options.customer_contact_capture_enabled ? "06" : "05"}</span><div><h2>Inspection handoff</h2><p>The active controlled template is selected by governance; choose the technician who will own the inspection.</p></div></div><div className={styles.gridTwo}><label>Active inspection template<select value={options.checklists[0]?.id ?? ""} disabled><option value="">{options.checklists.length === 0 ? "No approved template is active" : `${options.checklists[0].name} · v${options.checklists[0].version}`}</option></select></label><label>Assigned technician<select required value={form.assigned_technician_id} onChange={(event) => update("assigned_technician_id", event.target.value)}>{options.technicians.length === 0 ? <option value="">No active technicians</option> : options.technicians.map((technician) => <option key={technician.id} value={technician.id}>{technician.name}</option>)}</select></label></div><div className={styles.handoff}><span aria-hidden="true">→</span><p>Creates a pending Workbai inspection. The technician starts it when the vehicle enters the bay.</p></div></section>
      {state === "error" && <p className={styles.error} role="alert">{message}</p>}<div className={styles.actions}><button className={styles.primaryAction} disabled={!ready || state === "saving"} type="submit">{state === "saving" ? "Starting inspection…" : "Create pending inspection"}</button><Link className={styles.textLink} href="/queue">View queue</Link></div>
    </form>
  </main>;
}
