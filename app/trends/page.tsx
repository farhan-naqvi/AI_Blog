import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import { getDevelopments } from "@/lib/public-data";

export const metadata = { title: "Trends" };
export default async function TrendsPage() {
  const items = await getDevelopments(100);
  const counts = [...items.reduce((map, item) => map.set(item.category, (map.get(item.category) ?? 0) + 1), new Map<string, number>())].sort((a, b) => b[1] - a[1]);
  const max = counts[0]?.[1] ?? 1;
  return <PublicShell><PageHead kicker="EVIDENCE-BASED PATTERNS" title="Emerging trends" description="A compact view of categories represented in published, verified intelligence—not social attention or page views." /><section className="shell page-body narrow">{counts.length ? <div className="trend-list">{counts.map(([name, count]) => <div className="trend-row" key={name}><div><strong>{name}</strong><span>{count} verified development{count === 1 ? "" : "s"}</span></div><div className="trend-track"><i style={{ width: `${Math.max(8, count / max * 100)}%` }} /></div></div>)}</div> : <EmptyState title="Trends need evidence" detail="Category patterns appear after verified developments have been published." />}</section></PublicShell>;
}
