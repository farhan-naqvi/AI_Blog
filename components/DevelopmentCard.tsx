import Link from "next/link";
import type { Development } from "@/lib/types";

function date(value: string | null) {
  return value ? new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(value)) : "—";
}

export function DevelopmentCard({ item, rank, headline }: { item: Development; rank?: number; headline?: string }) {
  const displayedHeadline = headline ?? item.headline;
  const publicLabel = item.importance_label === "Incremental"
    ? `${item.verification_status} update`
    : `${item.importance_label} ${item.verification_status.toLowerCase()} ${item.verification_status === "Verified" ? "development" : "announcement"}`;
  return (
    <article className="development-card">
      {rank ? <span className="rank">{String(rank).padStart(2, "0")}</span> : null}
      <div className="card-main">
        <div className="eyebrow"><span className={`importance ${item.importance_label.toLowerCase()}`}>{publicLabel}</span><span>{item.importance_label}</span><span>{item.category}</span><time>{date(item.published_at)}</time></div>
        <h3><Link href={`/developments/${item.slug}`}>{displayedHeadline}</Link></h3>
        <p>{item.summary}</p>
        <div className={`evidence-line evidence-${item.verification_status.toLowerCase()}`}><span className="evidence-dot" /> {item.verification_status} · {item.confidence_label} confidence</div>
        <div className="card-facts">
          {item.primary_source_url ? <a href={item.primary_source_url} target="_blank" rel="noreferrer">Primary: {item.primary_source_title}</a> : null}
          <span>{item.confirmed_claims.length} confirmed facts · {item.reported_claims.length} source-reported claims</span>
        </div>
      </div>
      <Link className="arrow-link" href={`/developments/${item.slug}`} aria-label={`Read ${displayedHeadline}`}>↗</Link>
    </article>
  );
}
