import { notFound } from "next/navigation";
import { DevelopmentCard } from "@/components/DevelopmentCard";
import { PublicShell } from "@/components/PublicShell";
import { getDevelopment, getDevelopmentSources, getRelatedDevelopments } from "@/lib/public-data";

export default async function DevelopmentPage({ params }: { params: Promise<{ slug: string }> }) {
  const item = await getDevelopment((await params).slug);
  if (!item) notFound();
  const [sources, related] = await Promise.all([
    getDevelopmentSources(item.id),
    getRelatedDevelopments(item),
  ]);

  return (
    <PublicShell>
      <article className="shell">
        <header className="detail-head">
          <div className="eyebrow">
            <span className={`importance ${item.importance_label.toLowerCase()}`}>{item.importance_label}</span>
            <span className={`evidence-status ${item.verification_status.toLowerCase()}`}>{item.verification_status}</span>
            <span>{item.category}</span>
            <span>{item.confidence_label} confidence</span>
          </div>
          <h1>{item.headline}</h1>
          <p>{item.summary}</p>
          {item.verification_status === "Reported" ? <p className="reported-note">This record confirms that a first-party announcement exists. Its source-reported claims are not presented as independently verified.</p> : null}
        </header>
        <div className="detail-layout">
          <div>
            <section className="detail-block"><h2>What happened</h2><p>{item.summary}</p></section>
            <section className="detail-block"><h2>Confirmed facts</h2>{item.confirmed_claims.length ? <ul>{item.confirmed_claims.map((claim) => <li key={claim}>{claim}</li>)}</ul> : <p>No directly observable factual claim was extracted beyond the identified first-party announcement.</p>}</section>
            {item.reported_claims.length ? <section className="detail-block"><h2>Source-reported claims</h2><p>These claims were reported by the source organisation and have not necessarily been independently verified.</p><ul>{item.reported_claims.map((claim) => <li key={claim}>{claim}</li>)}</ul></section> : null}
            <section className="detail-block"><h2>Why it matters</h2><p>{item.why_it_matters}</p></section>
            <section className="detail-block"><h2>What changed</h2><p>{item.what_changed || "No comparison evidence was supplied."}</p></section>
            <section className="detail-block"><h2>Limitations</h2><p>{item.limitations || "No material limitations were stated in the available source set."}</p></section>
            <section className="detail-block"><h2>Who may be affected</h2><p>{item.who_affected}</p></section>
            <section className="detail-block"><h2>What to watch next</h2><p>{item.watch_next}</p></section>
          </div>
          <aside className="source-list">
            <h2>EVIDENCE</h2>
            {sources.map((source) => <a className="source-link" key={source.source_items.canonical_url} href={source.source_items.canonical_url} target="_blank" rel="noreferrer"><b>{source.source_items.title}</b><span>{source.is_primary ? "Primary" : "Supporting"} · {source.evidence_role}</span></a>)}
          </aside>
        </div>
        {related.length ? <section className="related"><div className="section-heading"><div><span className="section-index">RELATED</span><h2>Related developments</h2></div></div>{related.map((entry) => <DevelopmentCard key={entry.id} item={entry} />)}</section> : null}
      </article>
    </PublicShell>
  );
}
