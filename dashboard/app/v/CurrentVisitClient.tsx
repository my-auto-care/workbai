"use client";

import { useEffect, useState } from "react";

import styles from "./current-visit.module.css";

type PublicVisit = {
  vehicle_label: string;
  shop: { display_name: string; support_phone: string };
  visit: { status_code: string; status_label: string; updated_at: string };
  contact: { primary_action_label: string };
  access_expires_at: string | null;
  disclosure: string;
};

type ScreenState = { kind: "loading" } | { kind: "unavailable" } | { kind: "ready"; visit: PublicVisit };

function displayTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}

export function CurrentVisitClient() {
  const [screen, setScreen] = useState<ScreenState>(() => {
    if (typeof window !== "undefined" && !window.location.hash.slice(1)) return { kind: "unavailable" };
    return { kind: "loading" };
  });

  useEffect(() => {
    const secret = window.location.hash.slice(1);
    if (!secret) return;
    // The fragment never reached the server. Remove it before the network request
    // so it cannot remain in address/history state on an unavailable response.
    window.history.replaceState(null, "", "/v");
    let cancelled = false;
    void fetch("/api/public-current-visit/resolve", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ secret }),
    }).then(async (response) => ({ response, payload: await response.json() as PublicVisit }))
      .then(({ response, payload }) => {
        if (cancelled) return;
        if (!response.ok) { setScreen({ kind: "unavailable" }); return; }
        setScreen({ kind: "ready", visit: payload });
      })
      .catch(() => { if (!cancelled) setScreen({ kind: "unavailable" }); });
    return () => { cancelled = true; };
  }, []);

  if (screen.kind === "loading") return <main className={styles.shell}><section className={styles.card}><p className={styles.eyebrow}>Current visit</p><h1>Loading your visit</h1><p className={styles.copy}>Please wait while we securely open this limited visit update.</p></section></main>;
  if (screen.kind === "unavailable") return <main className={styles.shell}><section className={styles.card}><p className={styles.eyebrow}>Current visit</p><h1>This visit link is unavailable</h1><p className={styles.copy}>This private visit view may have expired or no longer be active. Please contact the service team for help.</p></section></main>;

  const { visit } = screen;
  const phone = visit.shop.support_phone.replace(/[^+\d]/g, "");
  const updated = displayTime(visit.visit.updated_at);
  const expires = displayTime(visit.access_expires_at);
  return <main className={styles.shell}><section className={styles.card} aria-labelledby="visit-title"><p className={styles.eyebrow}>{visit.shop.display_name} · Current visit</p><h1 id="visit-title">{visit.vehicle_label}</h1><div className={styles.status}><span className={styles.statusDot} aria-hidden="true" /><div><p className={styles.statusLabel}>Current update</p><p>{visit.visit.status_label}</p></div></div>{updated && <p className={styles.timestamp}>Updated {updated}</p>}<section className={styles.notice} aria-label="Visit scope"><strong>Limited visit update</strong><span>{visit.disclosure}</span></section><a className={styles.callAction} href={`tel:${phone}`}>{visit.contact.primary_action_label}</a>{expires && <p className={styles.expiry}>This private view expires {expires}.</p>}</section></main>;
}
