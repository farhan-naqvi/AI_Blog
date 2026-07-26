import { DevelopmentCard } from "@/components/DevelopmentCard";
import { EmptyState } from "@/components/EmptyState";
import { PageHead } from "@/components/PageHead";
import { PublicShell } from "@/components/PublicShell";
import {
  getDevelopments,
  publicCategoryGroups,
  type DevelopmentFilters,
  type PublicCategoryGroup,
} from "@/lib/public-data";

export const metadata = { title: "Latest Developments" };

type Params = { status?: string; importance?: string; category?: string };

function filterHref(current: DevelopmentFilters, change: Partial<DevelopmentFilters>) {
  const next = { ...current, ...change };
  const query = new URLSearchParams();
  if (next.status) query.set("status", next.status);
  if (next.importance) query.set("importance", next.importance);
  if (next.category) query.set("category", next.category);
  return query.size ? `/latest?${query}` : "/latest";
}

export default async function LatestPage({ searchParams }: { searchParams: Promise<Params> }) {
  const requested = await searchParams;
  const filters: DevelopmentFilters = {
    status: requested.status === "Verified" || requested.status === "Reported" ? requested.status : undefined,
    importance: ["Major", "Notable", "Incremental"].includes(requested.importance ?? "")
      ? requested.importance as DevelopmentFilters["importance"]
      : undefined,
    category: publicCategoryGroups.includes(requested.category as PublicCategoryGroup)
      ? requested.category as PublicCategoryGroup
      : undefined,
  };
  const items = await getDevelopments(50, filters);
  const statusFilters = [undefined, "Verified", "Reported"] as const;
  const importanceFilters = [undefined, "Major", "Notable", "Incremental"] as const;

  return (
    <PublicShell>
      <PageHead
        kicker="LIVE INTELLIGENCE"
        title="Latest developments"
        description="Reliably sourced AI activity, ranked by evidence status and importance without presenting source-reported claims as independently verified."
      />
      <section className="shell page-body">
        <div className="filter-set">
          <span>Evidence</span>
          <div className="filters">
            {statusFilters.map((status) => (
              <a className={`filter-pill ${filters.status === status ? "active" : ""}`} href={filterHref(filters, { status })} key={status ?? "all"}>
                {status ? `${status} only` : "All public updates"}
              </a>
            ))}
          </div>
        </div>
        <div className="filter-set">
          <span>Importance</span>
          <div className="filters">
            {importanceFilters.map((importance) => (
              <a className={`filter-pill ${filters.importance === importance ? "active" : ""}`} href={filterHref(filters, { importance })} key={importance ?? "all"}>
                {importance ?? "All importance"}
              </a>
            ))}
          </div>
        </div>
        <div className="filter-set">
          <span>Category</span>
          <div className="filters">
            <a className={`filter-pill ${!filters.category ? "active" : ""}`} href={filterHref(filters, { category: undefined })}>All categories</a>
            {publicCategoryGroups.map((category) => (
              <a className={`filter-pill ${filters.category === category ? "active" : ""}`} href={filterHref(filters, { category })} key={category}>{category}</a>
            ))}
          </div>
        </div>
        {items.length
          ? items.map((item, index) => <DevelopmentCard item={item} rank={index + 1} key={item.id} />)
          : <EmptyState title="No public developments" detail="No development in this filter currently satisfies the public evidence policy." />}
      </section>
    </PublicShell>
  );
}
