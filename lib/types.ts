export type Development = {
  id: string;
  slug: string;
  headline: string;
  summary: string;
  why_it_matters: string;
  what_changed: string;
  limitations: string;
  who_affected: string;
  watch_next: string;
  organisation: string | null;
  product: string | null;
  event_type: string;
  category: string;
  importance_label: "Major" | "Notable" | "Incremental";
  confidence_label: "High" | "Medium" | "Low";
  verification_status: "Verified" | "Developing" | "Held";
  publication_status: "Published" | "Held" | "Rejected";
  published_at: string | null;
};

export type Report = {
  id: string;
  report_type: "Daily" | "Weekly" | "Topic";
  title: string;
  summary: string;
  body: string;
  period_start: string;
  period_end: string;
  published_at: string | null;
};

export type Source = {
  id: string;
  name: string;
  base_url: string;
  source_type: string;
  retrieval_method: string;
  is_primary_source: boolean;
  reliability_level: string;
  poll_interval_minutes: number;
  last_success_at: string | null;
};
