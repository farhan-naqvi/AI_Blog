import Link from "next/link";
import { DevelopmentCard } from "@/components/DevelopmentCard";
import { EmptyState } from "@/components/EmptyState";
import { PublicShell } from "@/components/PublicShell";
import { getDevelopments, getPublicPlatformStats, getReports } from "@/lib/public-data";

export default async function OverviewPage() {
  const [developments, reports, stats] = await Promise.all([getDevelopments(6), getReports("Daily", 1), getPublicPlatformStats()]);
  const categories = [...new Set(developments.map((item) => item.category))].slice(0, 5);
  return (
    <PublicShell>
      <section className="hero shell">
        <div className="live-kicker"><span /> PRIMARY-SOURCE AI INTELLIGENCE</div>
        <h1>What changed in AI.<br /><em>Verified, not amplified.</em></h1>
        <p>Automated monitoring across official releases, research, open source, and regulation—processed locally and published only when the evidence holds.</p>
        <div className="hero-actions"><Link href="/latest" className="button primary">Explore developments <span>→</span></Link><Link href="/briefing" className="button subtle">Read today’s briefing</Link></div>
      </section>
      <section className="signal-strip">
        <div className="shell metrics">
          <div><strong>{stats?.active_source_count ?? 0}</strong><span>Sources monitored</span></div>
          <div><strong>{stats?.source_items_detected ?? 0}</strong><span>Items detected</span></div>
          <div><strong>{stats?.developments_analysed ?? 0}</strong><span>Developments analysed</span></div>
          <div><strong>{stats?.published_development_count ?? 0}</strong><span>Developments published</span></div>
        </div>
      </section>
      <section className="shell section-grid">
        <div>
          <div className="section-heading"><div><span className="section-index">01</span><h2>Latest important developments</h2></div><Link href="/latest">View all →</Link></div>
          <div className="development-list">{developments.length ? developments.slice(0, 4).map((item, index) => <DevelopmentCard key={item.id} item={item} rank={index + 1} />) : <EmptyState title="Monitoring is active" detail="No development currently meets the public publication threshold." />}</div>
        </div>
        <aside className="brief-panel">
          <div className="panel-label">DAILY BRIEFING</div>
          {reports[0] ? <><h2>{reports[0].title}</h2><p>{reports[0].summary}</p><Link href="/briefing">Open briefing →</Link></> : <><h2>The daily signal</h2><p>A briefing is published only when at least three verified developments support a meaningful synthesis.</p><span className="muted-link">Awaiting sufficient evidence</span></>}
          <div className="category-stack"><span>MONITORED NOW</span>{(categories.length ? categories : ["AI infrastructure", "Open source", "Research"]).map((category) => <div key={category}>{category}<i /></div>)}</div>
        </aside>
      </section>
      <section className="shell principles"><div><span>Evidence hierarchy</span><h2>Primary sources lead.</h2></div><p>Official announcements, documentation, repositories, and papers appear before discovery signals. Sensitive or conflicting claims are held for owner review.</p><Link href="/sources">How verification works →</Link></section>
    </PublicShell>
  );
}
