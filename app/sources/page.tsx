import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { getSources } from "@/lib/public-data";

export const metadata = { title: "Sources" };
export default async function SourcesPage() {
  const sources = await getSources();
  return <PublicShell><PageHead kicker="SOURCE REGISTRY" title="Evidence starts here" description="Official APIs, feeds, repositories, papers, and carefully reviewed public sources. Primary evidence is always displayed first." /><section className="shell page-body">{sources.length ? <table className="source-table"><thead><tr><th>Source</th><th>Type</th><th>Method</th><th>Reliability</th><th>Interval</th></tr></thead><tbody>{sources.map((source) => <tr key={source.id}><td><a href={source.base_url} target="_blank" rel="noreferrer">{source.name} ↗</a>{source.is_primary_source ? <small> Primary</small> : null}</td><td>{source.source_type}</td><td>{source.retrieval_method}</td><td>{source.reliability_level}</td><td>{source.poll_interval_minutes < 60 ? `${source.poll_interval_minutes}m` : `${source.poll_interval_minutes / 60}h`}</td></tr>)}</tbody></table> : <EmptyState title="Source registry not connected" detail="Add the public Supabase environment values to display the active registry." />}</section></PublicShell>;
}
