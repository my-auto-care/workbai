import { ChecklistGovernanceEditor } from "../ChecklistGovernanceEditor";

export const dynamic = "force-dynamic";

type PageProps = { params: Promise<{ id: string }> };

export default async function EditChecklistPage({ params }: PageProps) {
  const { id } = await params;
  return <ChecklistGovernanceEditor templateId={id} />;
}
