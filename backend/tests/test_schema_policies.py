from pathlib import Path

SCHEMA = (Path(__file__).parents[2] / "supabase" / "migrations" / "202607250001_initial_schema.sql").read_text(encoding="utf-8")
EXTRACTION_MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607250003_structured_extraction.sql"
).read_text(encoding="utf-8")
PUBLIC_DASHBOARD_MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607260001_public_dashboard.sql"
).read_text(encoding="utf-8")
VISIBILITY_MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607260002_visibility_and_digests.sql"
).read_text(encoding="utf-8")
REPORTED_VISIBILITY_MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607260003_reported_visibility.sql"
).read_text(encoding="utf-8")
COVERAGE_MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607260004_category_coverage.sql"
).read_text(encoding="utf-8")
CATEGORY_REFINEMENT_MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607260007_refine_development_categories.sql"
).read_text(encoding="utf-8")


def test_atomic_job_claim_uses_skip_locked() -> None:
    assert "for update skip locked" in SCHEMA.lower()
    assert "claimed_by = left(p_worker, 120)" in SCHEMA


def test_private_tables_have_rls_and_anon_revocation() -> None:
    for table in ("linkedin_drafts", "exceptions", "processing_jobs", "private_settings"):
        assert f"alter table public.{table} enable row level security" in SCHEMA
    revoke_block = SCHEMA.split("revoke all on public.private_settings", 1)[1].split("from anon", 1)[0]
    for table in ("processing_jobs", "exceptions", "linkedin_drafts", "operational_logs"):
        assert f"public.{table}" in revoke_block


def test_anon_source_access_is_column_limited() -> None:
    assert 'policy "public reads active sources" on public.sources for select to anon' in SCHEMA
    assert "revoke all on public.private_settings, public.sources" in SCHEMA
    assert "grant select (id, name, base_url" in SCHEMA
    public_grant = SCHEMA.split("grant select (id, name, base_url", 1)[1].split("to anon", 1)[0]
    assert "last_error" not in public_grant
    assert "connector_config" not in public_grant
    assert 'drop policy if exists "public reads active sources"' in PUBLIC_DASHBOARD_MIGRATION
    assert "revoke all on public.sources from anon" in PUBLIC_DASHBOARD_MIGRATION


def test_cleanup_honours_linkedin_pin_and_retention_windows() -> None:
    assert "delete from public.linkedin_drafts where not pinned and expires_at <= now()" in SCHEMA
    assert "now() + interval '48 hours'" in SCHEMA
    assert "now() + interval '14 days'" in SCHEMA
    assert "resolved_at + interval '30 days'" in SCHEMA


def test_no_full_source_body_column() -> None:
    source_items = SCHEMA.split("create table public.source_items", 1)[1].split(");", 1)[0]
    assert "raw_html" not in source_items
    assert "article_body" not in source_items


def test_specific_replay_claim_is_atomic_and_service_only() -> None:
    lowered = EXTRACTION_MIGRATION.lower()
    assert "for update skip locked" in lowered
    assert "candidate.id = p_job_id" in lowered
    assert "revoke all on function public.claim_processing_job_by_id" in lowered
    assert "grant execute on function public.claim_processing_job_by_id" in lowered
    assert "to service_role" in lowered


def test_public_stats_rpc_is_aggregate_only_and_explicitly_granted() -> None:
    lowered = PUBLIC_DASHBOARD_MIGRATION.lower()
    body = lowered.split("function public.get_public_platform_stats()", 1)[1].split("$$;", 1)[0]
    for expected in (
        "active_source_count",
        "source_type_count",
        "source_items_detected",
        "developments_analysed",
        "published_development_count",
        "last_successful_collection_at",
        "last_public_report_at",
    ):
        assert expected in body
    for forbidden in (
        "processing_jobs",
        "exceptions",
        "private_settings",
        "last_error",
        "connector_config",
        "owner_user_id",
        "headline",
    ):
        assert forbidden not in body
    assert "revoke all on function public.get_public_platform_stats()" in lowered
    assert "grant execute on function public.get_public_platform_stats() to anon" in lowered


def test_public_source_rpc_exposes_only_reviewed_projection() -> None:
    lowered = PUBLIC_DASHBOARD_MIGRATION.lower()
    body = lowered.split("function public.get_public_sources()", 1)[1].split("$$;", 1)[0]
    for expected in (
        "display_name text",
        "public_category text",
        "source_type text",
        "active boolean",
        "homepage_url text",
        "last_updated_date date",
    ):
        assert expected in body
    for forbidden in (
        "connector_config",
        "poll_interval",
        "last_error",
        "reliability_level",
        "rate_limit",
        "credentials",
    ):
        assert forbidden not in body
    assert "grant execute on function public.get_public_sources() to anon" in lowered


def test_category_coverage_migration_preserves_private_table_denials() -> None:
    lowered = COVERAGE_MIGRATION.lower()
    assert "grant execute on function public.get_public_sources() to anon" in lowered
    assert "grant execute on function public.ingest_source_item(jsonb) to service_role" in lowered
    assert "grant execute on function public.ingest_source_item(jsonb) to anon" not in lowered
    for table in ("processing_jobs", "exceptions", "private_settings", "linkedin_drafts"):
        assert f"grant select on public.{table} to anon" not in lowered


def test_public_category_refinement_does_not_change_visibility_rules() -> None:
    lowered = CATEGORY_REFINEMENT_MIGRATION.lower()
    assert "verification_status" not in lowered
    assert "publication_status" not in lowered
    assert "reported_claims" not in lowered
    assert "confirmed_claims" not in lowered
    assert "revoke all on function public.classify_development_public_category" in lowered


def test_release_metadata_is_bounded_and_ingested_without_article_text() -> None:
    lowered = PUBLIC_DASHBOARD_MIGRATION.lower()
    assert "add column if not exists release_metadata jsonb" in lowered
    assert "jsonb_typeof(release_metadata) = 'object'" in lowered
    assert "item->'release_metadata'" in lowered
    assert "article_body" not in lowered and "raw_html" not in lowered


def test_visibility_policy_keeps_verification_and_importance_separate() -> None:
    lowered = VISIBILITY_MIGRATION.lower()
    eligibility = lowered.split("function public.development_visibility_blocker", 1)[1].split("$$;", 1)[0]
    assert "verification_status <> 'verified'" in eligibility
    assert "jsonb_array_length(development_record.confirmed_claims) = 0" in eligibility
    assert "claim_consistency = 'contradictory'" in eligibility
    assert "evidence_role in ('primary announcement', 'documentation', 'repository', 'research paper')" in eligibility
    assert "importance_label" not in eligibility
    assert "public.is_development_publicly_visible(id)" in lowered


def test_visibility_recalculation_is_service_only_and_idempotent() -> None:
    lowered = VISIBILITY_MIGRATION.lower()
    assert "recalculate_public_visibility(p_dry_run boolean default true)" in lowered
    assert "where d.publication_status <> 'published'" in lowered
    assert "grant execute on function public.recalculate_public_visibility(boolean) to service_role" in lowered
    assert "eligible_by_importance" in lowered
    assert "records_made_public" in lowered


def test_daily_report_levels_have_distinct_thresholds() -> None:
    lowered = VISIBILITY_MIGRATION.lower()
    assert "daily briefing requires three major or notable developments" in lowered
    assert "daily monitoring digest requires three verified public developments" in lowered
    assert "report_level in ('briefing', 'monitoring digest')" in lowered


def test_reported_visibility_uses_three_deterministic_evidence_statuses() -> None:
    lowered = REPORTED_VISIBILITY_MIGRATION.lower()
    assert "verification_status in ('verified', 'reported', 'developing')" in lowered
    assert "eligible_verified" in lowered
    assert "eligible_reported" in lowered
    assert "missing_primary_source" in lowered
    assert "extraction_failure" in lowered
    assert "importance_label" not in lowered.split(
        "function public.development_evidence_classification", 1
    )[1].split("$$;", 1)[0]


def test_reported_recalculation_is_service_only_and_idempotent() -> None:
    lowered = REPORTED_VISIBILITY_MIGRATION.lower()
    assert "recalculate_public_visibility(p_dry_run boolean default true)" in lowered
    assert "eligible_as_verified_public" in lowered
    assert "eligible_as_reported_public" in lowered
    assert "verification_status_updates" in lowered
    assert "grant execute on function public.recalculate_public_visibility(boolean) to service_role" in lowered


def test_reported_stats_and_report_thresholds_are_separated() -> None:
    lowered = REPORTED_VISIBILITY_MIGRATION.lower()
    assert "reported_public_development_count" in lowered
    assert "developing_private_development_count" in lowered
    assert "daily briefing requires three verified major or notable developments" in lowered
    assert "daily monitoring digest requires three public developments" in lowered
    assert "daily activity summary requires one or two public developments" in lowered
