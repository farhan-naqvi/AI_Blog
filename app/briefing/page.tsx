import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { getReports } from "@/lib/public-data";

export const metadata = { title: "Daily Briefing" };

export default async function BriefingPage() {
  const reports = await getReports("Daily");
  return <PublicShell><PageHead kicker="DAILY REPORTING" title="Daily intelligence" description="Selective briefings for major signals, with monitoring digests when verified activity is meaningful but incremental." /><section className="shell page-body narrow">{reports.length ? reports.map((report) => <article className="report-card" key={report.id}><div className="eyebrow"><span>{new Date(report.period_end).toLocaleDateString()}</span><span>{report.report_level === "Monitoring digest" ? "Daily Monitoring Digest" : "Daily Intelligence Briefing"}</span></div><h2>{report.title}</h2><p>{report.summary}</p><div className="report-body">{report.body}</div></article>) : <EmptyState title="Insufficient verified activity" detail="No daily report is generated until at least three verified public developments are available." />}</section></PublicShell>;
}
