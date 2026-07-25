import { AdminNav } from "@/components/AdminNav";
import { requireOwner } from "@/lib/supabase-server";

export const metadata = { title: "Owner Workspace", robots: { index: false, follow: false } };
export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  await requireOwner();
  return <div className="admin-layout"><AdminNav /><main className="admin-main">{children}</main></div>;
}
