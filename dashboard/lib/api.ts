const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://167.99.153.77';

export async function fetchHealth() {
  const res = await fetch(`${BACKEND_URL}/health`);
  return res.json();
}

export async function fetchSessions() {
  const res = await fetch(`${BACKEND_URL}/sessions`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchSession(id: string) {
  const res = await fetch(`${BACKEND_URL}/sessions/${id}`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchReport(id: string) {
  const res = await fetch(`${BACKEND_URL}/sessions/${id}/report`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchChecklists() {
  const res = await fetch(`${BACKEND_URL}/checklists`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}
