import { DevelopmentCard } from "@/components/DevelopmentCard";
import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { getDevelopments } from "@/lib/public-data";

export const metadata = { title: "Latest Developments" };
export default async function LatestPage() {
  const items = await getDevelopments(50);
  return <PublicShell><PageHead kicker="LIVE INTELLIGENCE" title="Latest developments" description="Meaningful changes in AI, ordered by publication time and released only after deterministic verification." /><section className="shell page-body"><div className="filters"><span className="filter-pill active">All verified</span><span className="filter-pill">Major</span><span className="filter-pill">Research</span><span className="filter-pill">Open source</span><span className="filter-pill">Regulation</span></div>{items.length ? items.map((item, index) => <DevelopmentCard item={item} rank={index + 1} key={item.id} />) : <EmptyState />}</section></PublicShell>;
}
