import Link from "next/link";
import type { Development } from "@/lib/types";

function date(value: string | null) {
  return value ? new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(value)) : "—";
}

export function DevelopmentCard({ item, rank }: { item: Development; rank?: number }) {
  return (
    <article className="development-card">
      {rank ? <span className="rank">{String(rank).padStart(2, "0")}</span> : null}
      <div className="card-main">
        <div className="eyebrow"><span className={`importance ${item.importance_label.toLowerCase()}`}>{item.importance_label}</span><span>{item.category}</span><time>{date(item.published_at)}</time></div>
        <h3><Link href={`/developments/${item.slug}`}>{item.headline}</Link></h3>
        <p>{item.summary}</p>
        <div className="evidence-line"><span className="verified-dot" /> Verified · {item.confidence_label} confidence</div>
      </div>
      <Link className="arrow-link" href={`/developments/${item.slug}`} aria-label={`Read ${item.headline}`}>↗</Link>
    </article>
  );
}
