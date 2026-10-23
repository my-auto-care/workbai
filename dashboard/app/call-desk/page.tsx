import { redirect } from "next/navigation";

import { auth0 } from "@/lib/auth0";
import { CallDesk } from "./CallDesk";

export const dynamic = "force-dynamic";

export default async function CallDeskPage() {
  const session = await auth0.getSession();
  if (!session) redirect("/auth/login?returnTo=%2Fcall-desk");
  return <CallDesk />;
}
