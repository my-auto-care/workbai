import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Current visit | Workbai",
  description: "Limited current visit update.",
  robots: { index: false, follow: false, nocache: true },
};

export default function CurrentVisitLayout({ children }: { children: React.ReactNode }) {
  return children;
}
