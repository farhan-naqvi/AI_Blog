begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select plan(15);

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
from generate_series(1, 8) value;

insert into public.developments (
  id, slug, headline, summary, why_it_matters, what_changed, event_type, category,
  importance_label, confidence_label, verification_status, publication_status,
  confirmed_claims, reported_claims
) values
('41000000-0000-0000-0000-000000000001', 'visibility-incremental', 'Verified incremental update', 'A sufficiently detailed verified incremental summary for policy testing.', 'Verified incremental why', 'Verified incremental change', 'Release', 'Developer tools', 'Incremental', 'High', 'Verified', 'Held', '["confirmed fact"]', '[]'),
('41000000-0000-0000-0000-000000000002', 'visibility-notable', 'Verified notable development', 'A sufficiently detailed verified notable summary for policy testing.', 'Verified notable why', 'Verified notable change', 'Release', 'Developer tools', 'Notable', 'High', 'Verified', 'Held', '["confirmed fact"]', '[]'),
('41000000-0000-0000-0000-000000000003', 'visibility-major', 'Verified major development', 'A sufficiently detailed verified major summary for policy testing.', 'Verified major why', 'Verified major change', 'Release', 'Infrastructure', 'Major', 'High', 'Verified', 'Held', '["confirmed fact"]', '[]'),
('41000000-0000-0000-0000-000000000004', 'visibility-developing', 'Developing incremental update', 'A sufficiently detailed missing-primary summary for policy testing.', 'Developing incremental why', 'Developing incremental change', 'Release', 'Developer tools', 'Incremental', 'Low', 'Developing', 'Held', '["confirmed fact"]', '[]'),
('41000000-0000-0000-0000-000000000005', 'visibility-sensitive', 'Sensitive verified update', 'A sufficiently detailed sensitive summary for policy testing.', 'Sensitive verified why', 'Sensitive verified change', 'Security', 'Security', 'Incremental', 'Medium', 'Verified', 'Held', '["confirmed fact"]', '[]'),
('41000000-0000-0000-0000-000000000006', 'visibility-contradiction', 'Contradictory verified update', 'A sufficiently detailed contradictory summary for policy testing.', 'Contradictory verified why', 'Contradictory verified change', 'Release', 'Models', 'Incremental', 'Low', 'Verified', 'Held', '["confirmed fact"]', '[]'),
('41000000-0000-0000-0000-000000000007', 'visibility-no-claims', 'Unsupported verified update', 'A sufficiently detailed unsupported summary for policy testing.', 'Unsupported verified why', 'Unsupported verified change', 'Release', 'Models', 'Incremental', 'Low', 'Verified', 'Held', '[]', '[]'),
('41000000-0000-0000-0000-000000000008', 'visibility-reported', 'Reported official announcement', 'A sufficiently detailed first-party announcement summary for policy testing.', 'Reported announcement why', 'Reported announcement change', 'Release', 'Models', 'Incremental', 'Medium', 'Developing', 'Held', '[]', '["The source reports improved capability."]');

insert into public.development_sources (
  development_id, source_item_id, evidence_role, is_primary, claim_consistency
)
select
  ('41000000-0000-0000-0000-00000000000' || value)::uuid,
  ('21000000-0000-0000-0000-00000000000' || value)::uuid,
  'Repository', value <> 4, case when value = 6 then 'Contradictory' else 'Consistent' end
from generate_series(1, 8) value;

insert into public.exceptions (development_id, exception_type, reason)
values (
  '41000000-0000-0000-0000-000000000005',
  'Sensitive',
  'Sensitive fixture must remain held.'
);

select is((public.recalculate_public_visibility(true)->>'eligible_as_verified_public')::integer, 3, 'dry run finds three verified records');
select is((public.recalculate_public_visibility(true)->>'eligible_as_reported_public')::integer, 1, 'dry run finds one reported record');
select is((select count(*) from public.developments where slug like 'visibility-%' and publication_status = 'Published'), 0::bigint, 'dry run writes nothing');

create temporary table visibility_apply as select public.recalculate_public_visibility(false) result;
select is((select (result->>'verified_records_made_public')::integer from visibility_apply), 3, 'apply publishes three verified records');
select is((select (result->>'reported_records_made_public')::integer from visibility_apply), 1, 'apply publishes one reported record');
select is((select count(*) from public.exceptions where development_id = '41000000-0000-0000-0000-000000000005'), 1::bigint, 'sensitive exception remains unchanged');

create temporary table visibility_second_apply as select public.recalculate_public_visibility(false) result;
select is((select (result->>'verified_records_made_public')::integer from visibility_second_apply), 0, 'verified recalculation is idempotent');
select is((select (result->>'reported_records_made_public')::integer from visibility_second_apply), 0, 'reported recalculation is idempotent');
select ok(public.is_development_publicly_visible('41000000-0000-0000-0000-000000000001'), 'verified incremental is visible');
select ok(public.is_development_publicly_visible('41000000-0000-0000-0000-000000000008') and (select verification_status = 'Reported' from public.developments where id = '41000000-0000-0000-0000-000000000008'), 'reported incremental is visible and labelled Reported');
select ok(not public.is_development_publicly_visible('41000000-0000-0000-0000-000000000004'), 'missing-primary item is hidden');
select ok(not public.is_development_publicly_visible('41000000-0000-0000-0000-000000000005') and (select verification_status = 'Developing' from public.developments where id = '41000000-0000-0000-0000-000000000005'), 'sensitive item is Developing and hidden');
select ok(not public.is_development_publicly_visible('41000000-0000-0000-0000-000000000006'), 'contradictory item is hidden');
select ok(not public.is_development_publicly_visible('41000000-0000-0000-0000-000000000007'), 'item without grounded claims is hidden');
select ok(not has_function_privilege('anon', 'public.recalculate_public_visibility(boolean)', 'execute'), 'anonymous users cannot recalculate visibility');

select * from finish();
rollback;
