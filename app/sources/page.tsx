import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { getSources } from "@/lib/public-data";

export const metadata = { title: "Sources" };
export default async function SourcesPage() {
  const sources = await getSources();
  return <PublicShell><PageHead kicker="SOURCE REGISTRY" title="Evidence starts here" description="Active public sources are shown without exposing polling configuration, errors, credentials, or internal identifiers." /><section className="shell page-body">{sources.length ? <table className="source-table"><thead><tr><th>Source</th><th>Category</th><th>Type</th><th>Status</th><th>Last updated</th></tr></thead><tbody>{sources.map((source) => <tr key={`${source.display_name}:${source.source_type}`}><td>{source.homepage_url ? <a href={source.homepage_url} target="_blank" rel="noreferrer">{source.display_name} ↗</a> : source.display_name}</td><td>{source.public_category}</td><td>{source.source_type}</td><td>{source.active ? "Active" : "Paused"}</td><td>{source.last_updated_date ? new Date(source.last_updated_date).toLocaleDateString() : "Awaiting first check"}</td></tr>)}</tbody></table> : <EmptyState title="No active public sources" detail="The source projection is connected, but no active sources are currently available." />}</section></PublicShell>;
}
