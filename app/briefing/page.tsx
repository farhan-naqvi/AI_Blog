import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { getReports } from "@/lib/public-data";
import type { Report } from "@/lib/types";

export const metadata = { title: "Daily Briefing" };

function label(report: Report) {
  if (report.report_level === "Monitoring digest") return "Daily Monitoring Digest";
  if (report.report_level === "Activity summary") return "Daily Activity Summary";
  return "Daily Intelligence Briefing";
}

export default async function BriefingPage() {
  const reports = await getReports("Daily");
  return (
    <PublicShell>
      <PageHead kicker="DAILY REPORTING" title="Daily intelligence" description="Selective briefings for major verified signals, monitoring digests for broader reliably sourced activity, and concise summaries on quieter days." />
      <section className="shell page-body narrow">
        {reports.length
          ? reports.map((report) => <article className="report-card" key={report.id}><div className="eyebrow"><span>{new Date(report.period_end).toLocaleDateString()}</span><span>{label(report)}</span></div><h2>{report.title}</h2><p>{report.summary}</p><div className="report-body">{report.body}</div></article>)
          : <EmptyState title="No public activity" detail="No daily report is generated when there are zero public developments." />}
      </section>
    </PublicShell>
  );
}
