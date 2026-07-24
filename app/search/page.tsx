import { DevelopmentCard } from "@/components/DevelopmentCard";
import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { searchDevelopments } from "@/lib/public-data";

export const metadata = { title: "Search" };
export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const query = (await searchParams).q ?? "";
  const items = query ? await searchDevelopments(query) : [];
  return <PublicShell><PageHead kicker="POSTGRESQL FULL-TEXT SEARCH" title="Search intelligence" description="Search published developments by headline, summary, company, product, category, source, or date." /><section className="shell page-body"><form className="search-form"><input name="q" defaultValue={query} placeholder="Agents, inference, regulation…" aria-label="Search query" /><button type="submit">Search →</button></form><div className="search-results">{query ? items.length ? items.map((item) => <DevelopmentCard item={item} key={item.id} />) : <EmptyState title="No verified matches" detail="Try a broader term. Held and unverified items never appear in public search." /> : null}</div></section></PublicShell>;
}
