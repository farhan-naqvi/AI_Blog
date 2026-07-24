import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { getReports } from "@/lib/public-data";

export const metadata = { title: "Daily Briefing" };
export default async function BriefingPage() { const reports = await getReports("Daily"); return <PublicShell><PageHead kicker="DAILY SYNTHESIS" title="The daily briefing" description="Three to seven verified developments distilled into the day’s meaningful pattern." /><section className="shell page-body narrow">{reports.length ? reports.map((report) => <article className="report-card" key={report.id}><div className="eyebrow"><span>{new Date(report.period_end).toLocaleDateString()}</span><span>Daily</span></div><h2>{report.title}</h2><p>{report.summary}</p><div className="report-body">{report.body}</div></article>) : <EmptyState title="No daily briefing yet" detail="A briefing is withheld until at least three verified developments provide enough evidence." />}</section></PublicShell>; }
