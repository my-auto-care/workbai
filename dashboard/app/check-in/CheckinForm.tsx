"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import styles from "./checkin.module.css";

export type CheckinOptions = {
  actor: { name: string; role: "advisor" | "admin"; shop_id: string };
  technicians: Array<{ id: string; name: string }>;
  checklists: Array<{ id: string; name: string; version: number; vehicle_filter: Record<string, unknown> }>;
};

type FormState = {
  vehicle_year: string;
  vehicle_make: string;
  vehicle_model: string;
  vehicle_vin: string;
  vehicle_mileage: string;
  customer_concern: string;
  presence_mode: string;
  checklist_template_id: string;
  assigned_technician_id: string;
};

type Result = { id: string; status: string; vehicle_year: string; vehicle_make: string; vehicle_model: string };

export function CheckinForm({ options, userName }: { options: CheckinOptions; userName: string }) {
  const [form, setForm] = useState<FormState>({
    vehicle_year: "",
    vehicle_make: "",
    vehicle_model: "",
    vehicle_vin: "",
    vehicle_mileage: "",
    customer_concern: "",
    presence_mode: "",
    checklist_template_id: options.checklists[0]?.id ?? "",
    assigned_technician_id: options.technicians[0]?.id ?? "",
  });
  const [state, setState] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  const ready = useMemo(
    () => options.technicians.length > 0 && options.checklists.length > 0,
    [options.checklists.length, options.technicians.length],
  );

  function update(key: keyof FormState, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready || state === "saving") return;
    setState("saving");
    setMessage("");

    const payload = {
      ...form,
      vehicle_year: Number(form.vehicle_year),
      vehicle_mileage: form.vehicle_mileage ? Number(form.vehicle_mileage) : null,
      vehicle_vin: form.vehicle_vin || null,
    };

    try {
      const response = await fetch("/api/check-in", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await response.json()) as Result | { detail?: string };
      if (!response.ok) throw new Error("detail" in body && body.detail ? body.detail : "Unable to start this inspection");
      setResult(body as Result);
      setState("success");
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Unable to start this inspection");
    }
  }

  if (state === "success" && result) {
    const vehicle = [result.vehicle_year, result.vehicle_make, result.vehicle_model].filter(Boolean).join(" ");
    return (
      <main className={styles.shell}>
        <section className={styles.receipt} aria-labelledby="started-title">
          <div className={styles.receiptMark} aria-hidden="true">✓</div>
          <p className={styles.eyebrow}>Inspection handoff recorded</p>
          <h1 id="started-title">{vehicle}</h1>
          <p className={styles.receiptCopy}>The inspection is pending in the assigned technician’s queue. No customer message, portal link, or DVI report was sent.</p>
          <div className={styles.receiptActions}>
            <Link className={styles.primaryAction} href="/queue">Open inspection queue</Link>
            <button className={styles.secondaryAction} onClick={() => { setResult(null); setState("idle"); setForm((current) => ({ ...current, vehicle_vin: "", vehicle_mileage: "", customer_concern: "" })); }}>Start another check-in</button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <div>
          <p className={styles.eyebrow}>Workbai · {options.actor.role}</p>
          <h1>Start an inspection</h1>
        </div>
        <div className={styles.operator}>{userName}</div>
      </header>

      <section className={styles.context} aria-label="Check-in context">
        <div><span className={styles.contextLabel}>Shop</span><strong>Assigned shop</strong></div>
        <div><span className={styles.contextLabel}>Outcome</span><strong>Pending technician handoff</strong></div>
      </section>

      {!ready && (
        <section className={styles.blocked} role="alert">
          <h2>Setup is incomplete</h2>
          <p>Check-in requires at least one active technician and one active inspection template for this shop. No visit can be created until both are available.</p>
        </section>
      )}

      <form className={styles.form} onSubmit={submit}>
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <span className={styles.step}>01</span>
            <div><h2>Vehicle</h2><p>Use confirmed information from the customer or repair order.</p></div>
          </div>
          <div className={styles.gridThree}>
            <label>Year<input required inputMode="numeric" min="1886" max="2100" value={form.vehicle_year} onChange={(event) => update("vehicle_year", event.target.value)} placeholder="2021" /></label>
            <label>Make<input required value={form.vehicle_make} onChange={(event) => update("vehicle_make", event.target.value)} placeholder="Toyota" /></label>
            <label>Model<input required value={form.vehicle_model} onChange={(event) => update("vehicle_model", event.target.value)} placeholder="Camry" /></label>
          </div>
          <div className={styles.gridTwo}>
            <label>VIN <span className={styles.optional}>optional</span><input className={styles.mono} maxLength={17} value={form.vehicle_vin} onChange={(event) => update("vehicle_vin", event.target.value.toUpperCase())} placeholder="17-character VIN" /></label>
            <label>Mileage <span className={styles.optional}>optional</span><input inputMode="numeric" min="0" max="2000000" value={form.vehicle_mileage} onChange={(event) => update("vehicle_mileage", event.target.value)} placeholder="48,000" /></label>
          </div>
          <p className={styles.note}>Plate and VIN image scanning will be added as a separate consent-led flow. This release uses confirmed manual entry and does not retain customer contact information.</p>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <span className={styles.step}>02</span>
            <div><h2>Arrival type</h2><p>Mark the operational handoff before the vehicle goes to the technician.</p></div>
          </div>
          <fieldset className={styles.arrivalChoices}>
            <legend>Is the customer waiting or dropping off?</legend>
            <label className={form.presence_mode === "waiter" ? styles.arrivalChoiceActive : styles.arrivalChoice}>
              <input required type="radio" name="presence_mode" value="waiter" checked={form.presence_mode === "waiter"} onChange={(event) => update("presence_mode", event.target.value)} />
              <span><strong>Waiter</strong><small>Needs a timely progress handoff.</small></span>
            </label>
            <label className={form.presence_mode === "dropoff" ? styles.arrivalChoiceActive : styles.arrivalChoice}>
              <input required type="radio" name="presence_mode" value="dropoff" checked={form.presence_mode === "dropoff"} onChange={(event) => update("presence_mode", event.target.value)} />
              <span><strong>Drop-off</strong><small>Customer will not wait on site.</small></span>
            </label>
          </fieldset>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <span className={styles.step}>03</span>
            <div><h2>Reason for visit</h2><p>Capture the customer’s words. Do not diagnose or promise work here.</p></div>
          </div>
          <label className={styles.fullLabel}>Customer-stated concern<textarea required minLength={3} maxLength={1000} value={form.customer_concern} onChange={(event) => update("customer_concern", event.target.value)} placeholder="Example: Steering wheel shakes while braking on the highway." rows={4} /></label>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <span className={styles.step}>04</span>
            <div><h2>Inspection handoff</h2><p>Choose an available shared template and the technician who will own the inspection.</p></div>
          </div>
          <div className={styles.gridTwo}>
            <label>Inspection template<select required value={form.checklist_template_id} onChange={(event) => update("checklist_template_id", event.target.value)}>{options.checklists.length === 0 ? <option value="">No available templates</option> : options.checklists.map((checklist) => <option key={checklist.id} value={checklist.id}>{checklist.name} · v{checklist.version}</option>)}</select></label>
            <label>Assigned technician<select required value={form.assigned_technician_id} onChange={(event) => update("assigned_technician_id", event.target.value)}>{options.technicians.length === 0 ? <option value="">No active technicians</option> : options.technicians.map((technician) => <option key={technician.id} value={technician.id}>{technician.name}</option>)}</select></label>
          </div>
          <div className={styles.handoff}><span aria-hidden="true">→</span><p>Creates a pending Workbai inspection. The technician starts it when the vehicle enters the bay.</p></div>
        </section>

        {state === "error" && <p className={styles.error} role="alert">{message}</p>}
        <div className={styles.actions}>
          <button className={styles.primaryAction} disabled={!ready || state === "saving"} type="submit">{state === "saving" ? "Starting inspection…" : "Create pending inspection"}</button>
          <Link className={styles.textLink} href="/queue">View queue</Link>
        </div>
      </form>
    </main>
  );
}
