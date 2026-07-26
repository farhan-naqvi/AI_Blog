begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select plan(10);

insert into public.sources (
  id, name, base_url, source_type, retrieval_method, connector_key,
  is_primary_source, reliability_level, poll_interval_minutes, rate_limit_per_hour
) values (
  '11000000-0000-0000-0000-000000000001', 'Visibility policy test source',
  'https://example.com/visibility', 'Test', 'API', 'test', true, 'High', 60, 10
);

insert into public.source_items (
  id, source_id, url, canonical_url, title, content_hash, title_hash, status
)
select
  ('21000000-0000-0000-0000-00000000000' || value)::uuid,
  '11000000-0000-0000-0000-000000000001',
  'https://example.com/visibility/' || value,
  'https://example.com/visibility/' || value,
  'Visibility source item ' || value,
  repeat(value::text, 64),
  repeat((value + 1)::text, 64),
  'Completed'
from generate_series(1, 7) value;

insert into public.developments (
  id, slug, headline, summary, why_it_matters, what_changed, event_type, category,
  importance_label, confidence_label, verification_status, publication_status, confirmed_claims
) values
('41000000-0000-0000-0000-000000000001', 'visibility-incremental', 'Verified incremental update', 'Verified incremental summary', 'Verified incremental why', 'Verified incremental change', 'Release', 'Developer tools', 'Incremental', 'High', 'Verified', 'Held', '["confirmed fact"]'),
('41000000-0000-0000-0000-000000000002', 'visibility-notable', 'Verified notable development', 'Verified notable summary', 'Verified notable why', 'Verified notable change', 'Release', 'Developer tools', 'Notable', 'High', 'Verified', 'Held', '["confirmed fact"]'),
('41000000-0000-0000-0000-000000000003', 'visibility-major', 'Verified major development', 'Verified major summary', 'Verified major why', 'Verified major change', 'Release', 'Infrastructure', 'Major', 'High', 'Verified', 'Held', '["confirmed fact"]'),
('41000000-0000-0000-0000-000000000004', 'visibility-developing', 'Developing incremental update', 'Developing incremental summary', 'Developing incremental why', 'Developing incremental change', 'Release', 'Developer tools', 'Incremental', 'Low', 'Developing', 'Held', '["confirmed fact"]'),
('41000000-0000-0000-0000-000000000005', 'visibility-sensitive', 'Sensitive verified update', 'Sensitive verified summary', 'Sensitive verified why', 'Sensitive verified change', 'Security', 'Security', 'Incremental', 'Medium', 'Verified', 'Held', '["confirmed fact"]'),
('41000000-0000-0000-0000-000000000006', 'visibility-contradiction', 'Contradictory verified update', 'Contradictory verified summary', 'Contradictory verified why', 'Contradictory verified change', 'Release', 'Models', 'Incremental', 'Low', 'Verified', 'Held', '["confirmed fact"]'),
('41000000-0000-0000-0000-000000000007', 'visibility-no-claims', 'Unsupported verified update', 'Unsupported verified summary', 'Unsupported verified why', 'Unsupported verified change', 'Release', 'Models', 'Incremental', 'Low', 'Verified', 'Held', '[]');

insert into public.development_sources (
  development_id, source_item_id, evidence_role, is_primary, claim_consistency
)
select
  ('41000000-0000-0000-0000-00000000000' || value)::uuid,
  ('21000000-0000-0000-0000-00000000000' || value)::uuid,
  'Repository', true, case when value = 6 then 'Contradictory' else 'Consistent' end
from generate_series(1, 7) value;

select is((public.recalculate_public_visibility(true)->>'eligible_for_public_visibility')::integer, 3, 'dry run finds three eligible records');
select is((select count(*) from public.developments where slug like 'visibility-%' and publication_status = 'Published'), 0::bigint, 'dry run writes nothing');
select is((public.recalculate_public_visibility(false)->>'records_made_public')::integer, 3, 'apply publishes three eligible records');
select is((public.recalculate_public_visibility(false)->>'records_made_public')::integer, 0, 'recalculation is idempotent');
select ok(public.is_development_publicly_visible('41000000-0000-0000-0000-000000000001'), 'verified incremental is visible');
select ok(not public.is_development_publicly_visible('41000000-0000-0000-0000-000000000004'), 'developing item is hidden');
select ok(not public.is_development_publicly_visible('41000000-0000-0000-0000-000000000005'), 'sensitive item is hidden');
select ok(not public.is_development_publicly_visible('41000000-0000-0000-0000-000000000006'), 'contradictory item is hidden');
select ok(not public.is_development_publicly_visible('41000000-0000-0000-0000-000000000007'), 'item without confirmed claims is hidden');
select ok(not has_function_privilege('anon', 'public.recalculate_public_visibility(boolean)', 'execute'), 'anonymous users cannot recalculate visibility');

select * from finish();
rollback;
