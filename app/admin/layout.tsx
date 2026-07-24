import { AdminGate } from "@/components/AdminGate";
import { AdminNav } from "@/components/AdminNav";

export const metadata = { title: "Owner Workspace", robots: { index: false, follow: false } };
export default function AdminLayout({ children }: { children: React.ReactNode }) { return <AdminGate><div className="admin-layout"><AdminNav /><main className="admin-main">{children}</main></div></AdminGate>; }
