"use client";
// The Request Desk "FIX" button every LPG surface carries (Chad, 2026-10-22: "Add a fix button so that I can start
// practicing using it today"). The widget comes from the shared Request Desk (mypwa.pufu.ai); RQD_SURFACE "workbai" files
// each report against this repo (orchestrator/config/app_targets.yaml). Not on the public customer page /v, whose CSP
// allows no outside script.
import Script from "next/script";
import { usePathname } from "next/navigation";

declare global {
  interface Window { RQD_SURFACE?: string }
}

export default function FixButton() {
  const path = usePathname();
  if (path === "/v" || path.startsWith("/v/")) return null;
  if (typeof window !== "undefined") window.RQD_SURFACE = "workbai";
  return <Script id="request-desk-embed" src="https://mypwa.pufu.ai/api/request-desk/embed.js" strategy="afterInteractive"
    onLoad={() => { window.RQD_SURFACE = "workbai"; }} />;
}
