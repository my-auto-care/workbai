import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { BackendRequestError, backendJson } from "@/lib/server-api";

import { InspectionWorkspace, type InspectionWorkspaceData } from "./InspectionWorkspace";

export const dynamic = "force-dynamic";

type PageProps = { params: Promise<{ id: string }> };

export default async function InspectionWorkspacePage({ params }: PageProps) {
  const { id } = await params;
  let workspace: InspectionWorkspaceData | null = null;
  let message = "This inspection workspace is unavailable.";
  try {
    workspace = await backendJson<InspectionWorkspaceData>(`/sessions/${id}/inspection-workspace`);
  } catch (error) {
    if (error instanceof BackendRequestError && error.status === 401) {
      redirect(`/auth/login?returnTo=${encodeURIComponent(`/inspections/${id}`)}`);
    }
    if (error instanceof BackendRequestError && error.status === 404) notFound();
    message = error instanceof BackendRequestError ? error.detail : message;
  }

  if (workspace) {
    return <InspectionWorkspace initialWorkspace={workspace} />;
  }

  return (
    <main className="workbai-home">
      <section>
        <p className="home-kicker">Workbai · inspection workspace</p>
        <h1>Inspection workspace unavailable</h1>
        <p className="home-copy">{message}</p>
        <Link className="home-secondary" href="/queue">Return to inspection queue</Link>
      </section>
    </main>
  );
}
