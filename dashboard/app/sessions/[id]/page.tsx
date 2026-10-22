import Link from "next/link";

import { backendJson } from "@/lib/server-api";

type ReportMedia = { id: string; url?: string | null };
type Finding = { id: string; checklist_item_id?: string | null; transcript?: string | null; condition?: string | null; media?: ReportMedia[] };
type InspectionReport = {
  session_id: string;
  status: "pending" | "in_progress" | "completed" | "abandoned";
  started_at?: string | null;
  completed_at?: string | null;
  customer_concern?: string | null;
  vehicle_year?: string | null;
  vehicle_make?: string | null;
  vehicle_model?: string | null;
  vehicle_vin?: string | null;
  vehicle_mileage?: number | null;
  findings: Finding[];
};

type ReportResponse = { report: InspectionReport };

async function getReport(id: string): Promise<InspectionReport | null> {
  try {
    return (await backendJson<ReportResponse>(`/sessions/${encodeURIComponent(id)}/report`)).report;
  } catch {
    return null;
  }
}

function statusStyle(status: InspectionReport["status"]): string {
  return { pending: "bg-amber-100 text-amber-800", in_progress: "bg-cyan-100 text-cyan-800", completed: "bg-emerald-100 text-emerald-800", abandoned: "bg-slate-100 text-slate-700" }[status];
}

function formatDate(value?: string | null): string { return value ? new Date(value).toLocaleString() : "—"; }

export default async function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const report = await getReport(id);
  if (!report) return <main className="grid min-h-screen place-items-center bg-[#f1ece3] px-6 text-[#1f3a47]"><section className="max-w-md rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] p-8 text-center shadow-sm"><h1 className="text-xl font-semibold">Inspection not available</h1><p className="mt-2 text-sm text-[#58717b]">This inspection may be outside your shop or no longer available.</p><Link className="mt-5 inline-block font-bold text-[#087e91]" href="/queue">Return to queue</Link></section></main>;

  const vehicle = [report.vehicle_year, report.vehicle_make, report.vehicle_model].filter(Boolean).join(" ");
  const photos = report.findings.flatMap((finding) => finding.media ?? []).filter((media): media is ReportMedia & { url: string } => Boolean(media.url));

  return (
    <main className="min-h-screen bg-[#f1ece3] px-4 py-8 text-[#1f3a47] sm:px-8"><div className="mx-auto max-w-4xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-[#cad7da] pb-6"><div><p className="mb-2 text-xs font-bold uppercase tracking-[.13em] text-[#087e91]">Inspection record</p><h1 className="text-3xl font-semibold tracking-tight">{vehicle || "Inspection report"}</h1><p className="mt-2 text-sm text-[#58717b]">Reference {report.session_id.slice(0, 8)} · started {formatDate(report.started_at)}</p></div><div className="flex items-center gap-3"><span className={`rounded-full px-3 py-1 text-xs font-bold capitalize ${statusStyle(report.status)}`}>{report.status.replace("_", " ")}</span><Link href="/queue" className="text-sm font-bold text-[#087e91]">Queue</Link></div></header>
      <section className="rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] p-6 shadow-sm"><h2 className="text-base font-bold">Vehicle and visit</h2><dl className="mt-5 grid grid-cols-2 gap-x-8 gap-y-5 text-sm sm:grid-cols-3"><div><dt className="text-xs font-bold uppercase tracking-wide text-[#718990]">Year</dt><dd className="mt-1 font-medium">{report.vehicle_year || "—"}</dd></div><div><dt className="text-xs font-bold uppercase tracking-wide text-[#718990]">Mileage</dt><dd className="mt-1 font-medium">{report.vehicle_mileage ? `${report.vehicle_mileage.toLocaleString()} mi` : "—"}</dd></div><div><dt className="text-xs font-bold uppercase tracking-wide text-[#718990]">VIN</dt><dd className="mt-1 break-all font-mono text-xs font-medium">{report.vehicle_vin || "—"}</dd></div></dl>{report.customer_concern && <div className="mt-6 border-l-2 border-[#1fbed4] pl-4"><p className="text-xs font-bold uppercase tracking-wide text-[#718990]">Customer-stated concern</p><p className="mt-2 italic leading-7 text-[#355462]">&ldquo;{report.customer_concern}&rdquo;</p></div>}</section>
      <section className="rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] p-6 shadow-sm"><h2 className="text-base font-bold">Inspection notes</h2>{report.findings.length === 0 ? <p className="mt-4 text-sm text-[#58717b]">No technician findings have been recorded yet.</p> : <div className="mt-4 divide-y divide-[#e0e7e6]">{report.findings.map((finding) => <article key={finding.id} className="py-4 first:pt-0 last:pb-0"><div className="flex items-center justify-between gap-3"><p className="text-sm font-semibold">{finding.checklist_item_id || "Inspection note"}</p>{finding.condition && <span className="rounded-full bg-[#edf4f3] px-2.5 py-1 text-xs font-bold capitalize text-[#42636d]">{finding.condition}</span>}</div>{finding.transcript && <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#58717b]">{finding.transcript}</p>}</article>)}</div>}</section>
      {photos.length > 0 && <section className="rounded-2xl border border-[#d4dedf] bg-[#fbf8f2] p-6 shadow-sm"><h2 className="text-base font-bold">Inspection media</h2><div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">{photos.map((photo) => <a key={photo.id} href={photo.url} target="_blank" rel="noreferrer" className="overflow-hidden rounded-xl border border-[#cad7da] transition hover:border-[#087e91]"><img src={photo.url} alt="Inspection attachment" className="h-40 w-full object-cover" /></a>)}</div></section>}
      <p className="pb-8 text-center text-xs text-[#718990]">Completed {formatDate(report.completed_at)}</p>
    </div></main>
  );
}
