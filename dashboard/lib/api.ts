import "server-only";

import { backendJson } from "@/lib/server-api";

export async function fetchHealth() {
  return backendJson<{ status: string; service: string; version: string }>("/health");
}

export async function fetchSessions() {
  return backendJson<unknown[]>("/sessions");
}

export async function fetchSession(id: string) {
  return backendJson<unknown>(`/sessions/${encodeURIComponent(id)}`);
}

export async function fetchReport(id: string) {
  return backendJson<unknown>(`/sessions/${encodeURIComponent(id)}/report`);
}

export async function fetchChecklists() {
  return backendJson<unknown[]>("/checklists");
}
