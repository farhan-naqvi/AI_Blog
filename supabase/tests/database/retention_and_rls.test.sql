begin;
create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;
select plan(20);

insert into public.sources (id, name, base_url, source_type, retrieval_method, connector_key, is_primary_source, reliability_level, poll_interval_minutes, rate_limit_per_hour)
values ('10000000-0000-0000-0000-000000000001', 'Retention test source', 'https://example.com', 'Test', 'API', 'test', true, 'High', 60, 10);

insert into public.source_items (id, source_id, url, canonical_url, title, content_hash, title_hash, status, expires_at)
values
('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'https://example.com/rejected', 'https://example.com/rejected', 'Rejected test item', repeat('a', 64), repeat('b', 64), 'Rejected', now() - interval '1 minute'),
('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'https://example.com/completed', 'https://example.com/completed', 'Completed test item', repeat('c', 64), repeat('d', 64), 'Completed', null),
('20000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001', 'https://example.com/failed', 'https://example.com/failed', 'Failed test item', repeat('e', 64), repeat('f', 64), 'Completed', null);

insert into public.processing_jobs (id, source_item_id, status, expires_at)
values
('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'Completed', now() - interval '1 minute'),
('30000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000003', 'Failed', now() + interval '13 days');

insert into public.developments (id, slug, headline, summary, why_it_matters, what_changed, event_type, category, importance_label, confidence_label, verification_status, publication_status, published_at)
values
('40000000-0000-0000-0000-000000000001', 'published-retention-test', 'Published retention test', 'Published summary', 'Published why', 'Published change', 'release', 'Test', 'Notable', 'High', 'Verified', 'Published', now()),
('40000000-0000-0000-0000-000000000002', 'held-retention-test', 'Held retention test', 'Held summary', 'Held why', 'Held change', 'release', 'Test', 'Notable', 'Medium', 'Held', 'Held', null);

insert into public.linkedin_drafts (id, development_id, content, angle, pinned, expires_at)
values
('50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', 'expired', 'Technical', false, now() - interval '1 minute'),
('50000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000001', 'pinned', 'Technical', true, now() - interval '1 minute'),
('50000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000001', 'published draft text', 'Technical', false, now() + interval '48 hours');

update public.linkedin_drafts set status = 'Published', published_at = now()
where id = '50000000-0000-0000-0000-000000000003';
select is((select content from public.linkedin_drafts where id = '50000000-0000-0000-0000-000000000003'), '', 'published unpinned draft content is scrubbed');
select ok((select content_fingerprint is not null from public.linkedin_drafts where id = '50000000-0000-0000-0000-000000000003'), 'published draft retains only its fingerprint');

insert into public.exceptions (id, development_id, exception_type, reason, status, resolved_at)
values ('60000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000002', 'Test', 'Resolved test', 'Resolved', now() - interval '31 days');

insert into public.reports (id, report_type, title, summary, body, period_start, period_end, publication_status, published_at)
values ('70000000-0000-0000-0000-000000000001', 'Topic', 'Retention report', 'Report summary', 'Report body', now() - interval '1 day', now(), 'Published', now());

do $$ begin perform public.cleanup_expired_data(); end $$;
select is((select count(*) from public.linkedin_drafts where id = '50000000-0000-0000-0000-000000000001'), 0::bigint, 'expired unpinned draft is deleted');
select is((select count(*) from public.linkedin_drafts where id = '50000000-0000-0000-0000-000000000002'), 1::bigint, 'expired pinned draft is retained');
select is((select count(*) from public.source_items where id = '20000000-0000-0000-0000-000000000001'), 0::bigint, 'expired rejected source item is deleted');
select is((select count(*) from public.processing_jobs where id = '30000000-0000-0000-0000-000000000001'), 0::bigint, 'expired completed job is deleted');
select is((select count(*) from public.processing_jobs where id = '30000000-0000-0000-0000-000000000002'), 1::bigint, 'failed job inside fourteen-day window is retained');
select is((select count(*) from public.exceptions where id = '60000000-0000-0000-0000-000000000001'), 0::bigint, 'resolved exception older than thirty days is deleted');
select is((select count(*) from public.developments where id = '40000000-0000-0000-0000-000000000001'), 1::bigint, 'published development remains');
select is((select count(*) from public.reports where id = '70000000-0000-0000-0000-000000000001'), 1::bigint, 'published report remains');
select ok(not has_table_privilege('anon', 'public.linkedin_drafts', 'select'), 'anon lacks LinkedIn draft access');
select ok(not has_table_privilege('anon', 'public.processing_jobs', 'select'), 'anon lacks processing job access');
select ok(not has_table_privilege('anon', 'public.exceptions', 'select'), 'anon lacks exception access');
select ok(not has_table_privilege('anon', 'public.operational_logs', 'select'), 'anon lacks log access');
select ok(not has_table_privilege('anon', 'public.private_settings', 'select'), 'anon lacks private settings access');

set local role anon;
select is((select count(*) from public.developments where id = '40000000-0000-0000-0000-000000000001'), 1::bigint, 'anon sees published verified development');
select is((select count(*) from public.developments where id = '40000000-0000-0000-0000-000000000002'), 0::bigint, 'anon cannot see held development');
reset role;

set local role authenticated;
select is((select count(*) from public.private_settings), 0::bigint, 'non-owner authenticated user cannot see private settings');
select is((select count(*) from public.linkedin_drafts), 0::bigint, 'non-owner authenticated user cannot see LinkedIn drafts');
select is((select count(*) from public.sources where id = '10000000-0000-0000-0000-000000000001'), 0::bigint, 'non-owner authenticated user cannot read operational source rows');
reset role;

select * from finish();
rollback;
