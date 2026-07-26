begin;

alter table public.source_items
  add column if not exists release_metadata jsonb not null default '{}'::jsonb
  check (jsonb_typeof(release_metadata) = 'object');

create or replace function public.ingest_source_item(item jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  inserted_id uuid;
  item_status text := coalesce(item->>'status', 'Candidate');
  pending_count integer;
  pending_limit integer;
begin
  insert into public.source_items (
    source_id, source_identifier, url, canonical_url, title, published_at, excerpt,
    content_hash, title_hash, event_type_hint, language, status, rejection_reason, expires_at,
    release_metadata
  ) values (
    (item->>'source_id')::uuid, item->>'source_identifier', item->>'url',
    coalesce(item->>'canonical_url', item->>'url'), left(item->>'title', 500),
    nullif(item->>'published_at', '')::timestamptz, left(coalesce(item->>'excerpt', ''), 1200),
    item->>'content_hash', item->>'title_hash', left(item->>'event_type_hint', 80),
    left(coalesce(item->>'language', 'en'), 12), item_status, item->>'rejection_reason',
    case when item_status in ('Rejected', 'Irrelevant') then now() + interval '7 days' else null end,
    coalesce(nullif(item->'release_metadata', 'null'::jsonb), '{}'::jsonb)
  ) on conflict do nothing returning id into inserted_id;

  if inserted_id is null then
    return jsonb_build_object('inserted', false, 'reason', 'duplicate');
  end if;

  if item_status = 'Candidate' and exists (
    select 1 from public.source_items existing
    where existing.id <> inserted_id and existing.title_hash = item->>'title_hash'
      and existing.detected_at >= now() - interval '72 hours'
  ) then
    update public.source_items set status = 'Rejected', rejection_reason = 'exact_title_duplicate',
      expires_at = now() + interval '7 days' where id = inserted_id;
    return jsonb_build_object('inserted', true, 'queued', false, 'reason', 'exact_title_duplicate');
  end if;

  if item_status = 'Candidate' then
    select count(*) into pending_count from public.processing_jobs where status in ('Pending', 'Claimed');
    select max_pending_jobs into pending_limit from public.private_settings where id;
    if pending_count >= pending_limit then
      update public.source_items set status = 'Rejected', rejection_reason = 'queue_limit',
        expires_at = now() + interval '7 days' where id = inserted_id;
      return jsonb_build_object('inserted', true, 'queued', false, 'reason', 'queue_limit');
    end if;
    insert into public.processing_jobs (source_item_id, status, priority)
    values (inserted_id, 'Pending', case item->>'event_type_hint' when 'release' then 75 when 'research' then 60 else 50 end);
    update public.source_items set status = 'Queued' where id = inserted_id;
  end if;
  return jsonb_build_object('inserted', true, 'queued', item_status = 'Candidate', 'source_item_id', inserted_id);
end;
$$;

drop policy if exists "public reads active sources" on public.sources;
revoke all on public.sources from anon;

create or replace function public.get_public_platform_stats()
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  select jsonb_build_object(
    'active_source_count', (select count(*) from public.sources where active),
    'source_type_count', (select count(distinct source_type) from public.sources where active),
    'source_items_detected', (select count(*) from public.source_items),
    'developments_analysed', (select count(*) from public.developments),
    'published_development_count', (
      select count(*) from public.developments
      where publication_status = 'Published' and verification_status = 'Verified'
    ),
    'last_successful_collection_at', (
      select max(last_success_at) from public.sources where active
    ),
    'last_public_report_at', (
      select max(published_at) from public.reports where publication_status = 'Published'
    )
  );
$$;

create or replace function public.get_public_sources()
returns table (
  display_name text,
  public_category text,
  source_type text,
  active boolean,
  homepage_url text,
  last_updated_date date
)
language sql
stable
security definer
set search_path = public
as $$
  select
    s.name::text,
    case s.connector_key
      when 'arxiv' then 'Research'
      when 'github' then 'Open source'
      when 'huggingface' then 'Model ecosystem'
      when 'rss' then 'Official and technical feeds'
      else 'Public intelligence'
    end::text,
    s.source_type::text,
    s.active,
    s.base_url::text,
    s.last_success_at::date
  from public.sources s
  where s.active
  order by s.name;
$$;

revoke all on function public.ingest_source_item(jsonb) from public, anon, authenticated;
grant execute on function public.ingest_source_item(jsonb) to service_role;
revoke all on function public.get_public_platform_stats() from public, anon, authenticated;
revoke all on function public.get_public_sources() from public, anon, authenticated;
grant execute on function public.get_public_platform_stats() to anon, authenticated, service_role;
grant execute on function public.get_public_sources() to anon, authenticated, service_role;

commit;
