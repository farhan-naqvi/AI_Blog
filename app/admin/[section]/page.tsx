import { notFound } from "next/navigation";
import { AdminWorkspace } from "@/components/AdminWorkspace";
const sections = new Set(["processing-queue", "exceptions", "sources", "editorial-rules", "linkedin-studio", "system-health", "settings"]);
export default async function AdminSectionPage({ params }: { params: Promise<{ section: string }> }) { const { section } = await params; if (!sections.has(section)) notFound(); return <AdminWorkspace section={section} />; }
