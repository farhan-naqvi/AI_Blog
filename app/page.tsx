import Link from "next/link";
import { DevelopmentCard } from "@/components/DevelopmentCard";
import { EmptyState } from "@/components/EmptyState";
import { PublicShell } from "@/components/PublicShell";
import {
  developmentPublicCategory,
  getDevelopments,
  getPublicPlatformStats,
  getReports,
  publicCategoryGroups,
  readerFacingHeadline,
  selectReaderValueDevelopments,
} from "@/lib/public-data";

function reportLabel(level: "Briefing" | "Monitoring digest" | "Activity summary" | undefined) {
  if (level === "Monitoring digest") return "DAILY MONITORING DIGEST";
  if (level === "Activity summary") return "DAILY ACTIVITY SUMMARY";
  return "DAILY INTELLIGENCE BRIEFING";
}

export default async function OverviewPage() {
  const [developments, reports, stats] = await Promise.all([
    getDevelopments(30),
    getReports("Daily", 1),
    getPublicPlatformStats(),
  ]);
  const grouped = publicCategoryGroups.map((category) => ({
    category,
    items: selectReaderValueDevelopments(
      developments.filter((item) => developmentPublicCategory(item) === category),
      5,
    ),
  }));
  const featuredDevelopments = selectReaderValueDevelopments(developments, 4);
  const publicCount = stats?.published_development_count ?? 0;
  const noMajorVerified = publicCount > 0 && (stats?.major_verified_public_count ?? 0) === 0;

  return (
    <PublicShell>
      <section className="hero shell">
        <div className="live-kicker"><span /> PRIMARY-SOURCE AI INTELLIGENCE</div>
        <h1>What changed in AI.<br /><em>Grounded, not amplified.</em></h1>
        <p>Automated monitoring across official releases, research, open source, and regulation—processed locally and published with explicit evidence labels.</p>
        <div className="hero-actions"><Link href="/latest" className="button primary">Explore developments <span>→</span></Link><Link href="/briefing" className="button subtle">Read today’s report</Link></div>
      </section>
      <section className="signal-strip">
        <div className="shell metrics">
          <div><strong>{stats?.active_source_count ?? 0}</strong><span>Sources monitored</span></div>
          <div><strong>{stats?.source_items_detected ?? 0}</strong><span>Items detected</span></div>
          <div><strong>{stats?.developments_analysed ?? 0}</strong><span>Developments analysed</span></div>
          <div><strong>{stats?.verified_public_development_count ?? 0}</strong><span>Verified public</span></div>
          <div><strong>{stats?.reported_public_development_count ?? 0}</strong><span>Reported public</span></div>
          <div><strong>{stats?.developing_private_development_count ?? 0}</strong><span>Developing/private</span></div>
          <div><strong>{stats?.major_notable_public_count ?? 0}</strong><span>Major or notable</span></div>
          <div><strong>{stats?.incremental_public_count ?? 0}</strong><span>Incremental</span></div>
        </div>
      </section>
      <section className="shell category-monitor">
        <div className="section-heading"><div><span className="section-index">01</span><h2>Monitoring by category</h2></div></div>
        <div className="category-grid">
          {grouped.map(({ category, items }) => (
            <section className="category-panel" key={category}>
              <div className="category-panel-head"><h3>{category}</h3><Link href={`/latest?category=${encodeURIComponent(category)}`}>View all</Link></div>
              {items.length
                ? items.map((item, index) => <DevelopmentCard key={item.id} item={item} rank={index + 1} headline={readerFacingHeadline(item)} />)
                : <EmptyState title="No public developments yet" detail="Monitoring is active; no item in this category currently meets the public evidence policy." />}
            </section>
          ))}
        </div>
      </section>
      <section className="shell section-grid">
        <div>
          <div className="section-heading"><div><span className="section-index">01</span><h2>Latest public developments</h2></div><Link href="/latest">View all →</Link></div>
          {noMajorVerified ? <p className="monitoring-note">Monitoring is active. Reliably sourced updates are available, while no major verified development has been identified today.</p> : null}
          <div className="development-list">{featuredDevelopments.length ? featuredDevelopments.map((item, index) => <DevelopmentCard key={item.id} item={item} rank={index + 1} headline={readerFacingHeadline(item)} />) : <EmptyState title="Monitoring is active" detail="No development currently combines sufficient evidence with a distinct reader-relevant change." />}</div>
        </div>
        <aside className="brief-panel">
          <div className="panel-label">{reportLabel(reports[0]?.report_level)}</div>
          {reports[0] ? <><h2>{reports[0].title}</h2><p>{reports[0].summary}</p><Link href="/briefing">Open daily report →</Link></> : <><h2>The daily signal</h2><p>No public activity summary or report is available yet.</p><span className="muted-link">Awaiting reliably sourced activity</span></>}
          <div className="category-stack"><span>MONITORED NOW</span>{publicCategoryGroups.map((category) => <div key={category}>{category}<i /></div>)}</div>
        </aside>
      </section>
      <section className="shell principles"><div><span>Evidence hierarchy</span><h2>Primary sources lead.</h2></div><p>Verified facts and source-reported claims are labelled separately. Sensitive, conflicting, or insufficiently grounded developments remain private.</p><Link href="/sources">How verification works →</Link></section>
    </PublicShell>
  );
}
