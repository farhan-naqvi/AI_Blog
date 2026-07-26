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
  verification_status: "Verified" | "Reported" | "Developing";
  publication_status: "Published" | "Held" | "Rejected";
  published_at: string | null;
  confirmed_claims: string[];
  reported_claims: string[];
  primary_source_title?: string | null;
  primary_source_url?: string | null;
  primary_evidence_role?: string | null;
};

export type Report = {
  id: string;
  report_type: "Daily" | "Weekly" | "Topic";
  report_level: "Briefing" | "Monitoring digest" | "Activity summary";
  title: string;
  summary: string;
  body: string;
  period_start: string;
  period_end: string;
  published_at: string | null;
};

export type Source = {
  display_name: string;
  public_category: string;
  source_type: string;
  active: boolean;
  homepage_url: string | null;
  last_updated_date: string | null;
};

export type PublicPlatformStats = {
  active_source_count: number;
  source_type_count: number;
  source_items_detected: number;
  developments_analysed: number;
  published_development_count: number;
  verified_public_development_count: number;
  reported_public_development_count: number;
  developing_private_development_count: number;
  major_verified_public_count: number;
  major_notable_public_count: number;
  incremental_public_count: number;
  incremental_verified_update_count: number;
  internally_held_count: number;
  last_successful_collection_at: string | null;
  last_public_report_at: string | null;
};
