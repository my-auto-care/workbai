import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { BackendRequestError, backendJson } from "@/lib/server-api";

import { AdvisorReviewWorkbench, type AdvisorReviewData } from "./AdvisorReviewWorkbench";

export const dynamic = "force-dynamic";

type PageProps = { params: Promise<{ id: string }> };

export default async function AdvisorReviewPage({ params }: PageProps) {
  const { id } = await params;
  let review: AdvisorReviewData | null = null;
  let message = "This advisor review is unavailable.";

  try {
    review = await backendJson<AdvisorReviewData>(`/sessions/${id}/advisor-review`);
  } catch (error) {
    if (error instanceof BackendRequestError && error.status === 401) {
      redirect(`/auth/login?returnTo=${encodeURIComponent(`/advisor-review/${id}`)}`);
    }
    if (error instanceof BackendRequestError && error.status === 404) notFound();
    message = error instanceof BackendRequestError ? error.detail : message;
  }

  if (review) return <AdvisorReviewWorkbench initialReview={review} />;

  return (
    <main className="workbai-home">
      <section>
        <p className="home-kicker">Workbai · advisor review</p>
        <h1>Advisor review unavailable</h1>
        <p className="home-copy">{message}</p>
        <Link className="home-secondary" href="/queue">Return to inspection queue</Link>
      </section>
    </main>
  );
}
