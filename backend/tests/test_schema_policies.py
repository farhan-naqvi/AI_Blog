from pathlib import Path

SCHEMA = (Path(__file__).parents[2] / "supabase" / "migrations" / "202607250001_initial_schema.sql").read_text(encoding="utf-8")


def test_atomic_job_claim_uses_skip_locked() -> None:
    assert "for update skip locked" in SCHEMA.lower()


def test_private_tables_have_rls_and_anon_revocation() -> None:
    for table in ("linkedin_drafts", "exceptions", "processing_jobs", "private_settings"):
        assert f"alter table public.{table} enable row level security" in SCHEMA
    assert "revoke all on public.private_settings, public.processing_jobs, public.exceptions, public.linkedin_drafts" in SCHEMA


def test_cleanup_honours_linkedin_pin_and_retention_windows() -> None:
    assert "delete from public.linkedin_drafts where not pinned and expires_at <= now()" in SCHEMA
    assert "now() + interval '48 hours'" in SCHEMA
    assert "now() + interval '14 days'" in SCHEMA
    assert "resolved_at + interval '30 days'" in SCHEMA


def test_no_full_source_body_column() -> None:
    source_items = SCHEMA.split("create table public.source_items", 1)[1].split(");", 1)[0]
    assert "raw_html" not in source_items
    assert "article_body" not in source_items
