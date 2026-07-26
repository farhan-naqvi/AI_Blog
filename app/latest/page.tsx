import { DevelopmentCard } from "@/components/DevelopmentCard";
import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { getDevelopments } from "@/lib/public-data";

export const metadata = { title: "Latest Developments" };
const filters = ["All verified", "Major", "Notable", "Incremental"] as const;

export default async function LatestPage({ searchParams }: { searchParams: Promise<{ importance?: string }> }) {
  const requested = (await searchParams).importance;
  const importance = requested === "Major" || requested === "Notable" || requested === "Incremental" ? requested : undefined;
  const items = await getDevelopments(50, importance);
  return <PublicShell><PageHead kicker="LIVE INTELLIGENCE" title="Latest developments" description="Verified AI activity, ordered by importance and recency without promoting source-reported claims to confirmed facts." /><section className="shell page-body"><div className="filters">{filters.map((filter) => { const value = filter === "All verified" ? undefined : filter; const active = value === importance; return <a className={`filter-pill ${active ? "active" : ""}`} href={value ? `/latest?importance=${value}` : "/latest"} key={filter}>{filter}</a>; })}</div>{items.length ? items.map((item, index) => <DevelopmentCard item={item} rank={index + 1} key={item.id} />) : <EmptyState title="No verified developments" detail="No development in this filter currently satisfies the public verification policy." />}</section></PublicShell>;
}
