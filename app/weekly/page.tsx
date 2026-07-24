import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { getReports } from "@/lib/public-data";

export const metadata = { title: "Weekly Reports" };
export default async function WeeklyPage() { const reports = await getReports("Weekly"); return <PublicShell><PageHead kicker="WEEKLY SYNTHESIS" title="Weekly reports" description="The releases, research, regulation, and patterns that changed the AI landscape this week." /><section className="shell page-body narrow">{reports.length ? reports.map((report) => <article className="report-card" key={report.id}><div className="eyebrow"><span>Weekly</span><span>{new Date(report.period_start).toLocaleDateString()} — {new Date(report.period_end).toLocaleDateString()}</span></div><h2>{report.title}</h2><p>{report.summary}</p><div className="report-body">{report.body}</div></article>) : <EmptyState title="No weekly report yet" detail="Weekly synthesis requires at least five published, verified developments." />}</section></PublicShell>; }
