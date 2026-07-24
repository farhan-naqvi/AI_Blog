begin;

create extension if not exists pgcrypto with schema extensions;

create table public.private_settings (
  id boolean primary key default true check (id),
  owner_user_id uuid references auth.users(id) on delete set null,
  owner_email text,
  max_pending_jobs integer not null default 500 check (max_pending_jobs between 10 and 5000),
  max_pending_age_days integer not null default 7 check (max_pending_age_days between 1 and 30),
  linkedin_draft_ttl_hours integer not null default 48 check (linkedin_draft_ttl_hours between 1 and 168),
  updated_at timestamptz not null default now()
);
insert into public.private_settings (id) values (true) on conflict do nothing;

create or replace function public.is_owner()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.private_settings
    where id
      and (
        owner_user_id = auth.uid()
        or (owner_user_id is null and lower(owner_email) = lower(auth.jwt() ->> 'email'))
      )
  );
$$;

create table public.sources (
  id uuid primary key default gen_random_uuid(),
  name varchar(200) not null unique,
  base_url varchar(2000) not null,
  source_type varchar(50) not null,
  retrieval_method varchar(50) not null,
  connector_key varchar(50) not null,
  connector_config jsonb not null default '{}'::jsonb,
  is_primary_source boolean not null default false,
  reliability_level varchar(10) not null check (reliability_level in ('High', 'Medium', 'Low')),
  poll_interval_minutes integer not null check (poll_interval_minutes between 15 and 10080),
  rate_limit_per_hour integer not null default 60 check (rate_limit_per_hour between 1 and 5000),
  active boolean not null default true,
  etag varchar(500),
  last_modified varchar(500),
  last_checked_at timestamptz,
  last_success_at timestamptz,
  last_error varchar(1000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.source_items (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.sources(id) on delete cascade,
  source_identifier varchar(500),
  url varchar(2000) not null,
  canonical_url varchar(2000) not null,
  title varchar(500) not null check (length(title) >= 3),
  published_at timestamptz,
  detected_at timestamptz not null default now(),
  excerpt varchar(1200) not null default '',
  content_hash char(64) not null,
  title_hash char(64) not null,
  event_type_hint varchar(80),
  language varchar(12) not null default 'en',
  status varchar(20) not null check (status in ('Candidate', 'Queued', 'Processing', 'Completed', 'Rejected', 'Irrelevant')),
  rejection_reason varchar(100),
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  unique (canonical_url),
  unique (source_id, source_identifier),
  unique (source_id, content_hash)
);
create index source_items_status_detected_idx on public.source_items (status, detected_at);
create index source_items_title_hash_idx on public.source_items (title_hash);

create table public.developments (
  id uuid primary key default gen_random_uuid(),
  slug varchar(280) not null unique,
  headline varchar(240) not null,
  summary varchar(1600) not null,
  why_it_matters varchar(1400) not null,
  what_changed varchar(1400) not null,
  limitations varchar(2400) not null default '',
  who_affected varchar(800) not null default '',
  watch_next varchar(800) not null default '',
  organisation varchar(200),
  product varchar(200),
  release_date timestamptz,
  event_type varchar(100) not null,
  category varchar(100) not null,
  importance_label varchar(20) not null check (importance_label in ('Major', 'Notable', 'Incremental')),
  confidence_label varchar(20) not null check (confidence_label in ('High', 'Medium', 'Low')),
  verification_status varchar(20) not null check (verification_status in ('Verified', 'Developing', 'Held')),
  publication_status varchar(20) not null check (publication_status in ('Published', 'Held', 'Rejected')),
  confirmed_claims jsonb not null default '[]'::jsonb,
  reported_claims jsonb not null default '[]'::jsonb,
  model_identifier varchar(120),
  prompt_template_version varchar(80),
  search_document tsvector generated always as (
    to_tsvector('english', coalesce(headline, '') || ' ' || coalesce(summary, '') || ' ' ||
      coalesce(organisation, '') || ' ' || coalesce(product, '') || ' ' || coalesce(category, ''))
  ) stored,
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index developments_public_idx on public.developments (publication_status, published_at desc);
create index developments_search_idx on public.developments using gin (search_document);

create table public.development_sources (
  development_id uuid not null references public.developments(id) on delete cascade,
  source_item_id uuid not null references public.source_items(id) on delete restrict,
  evidence_role varchar(50) not null check (evidence_role in ('Primary announcement', 'Documentation', 'Repository', 'Research paper', 'Independent confirmation', 'Discovery signal')),
  is_primary boolean not null default false,
  claim_consistency varchar(20) not null default 'Consistent' check (claim_consistency in ('Consistent', 'Partial', 'Contradictory')),
  created_at timestamptz not null default now(),
  primary key (development_id, source_item_id)
);

create table public.processing_jobs (
  id uuid primary key default gen_random_uuid(),
  source_item_id uuid references public.source_items(id) on delete cascade,
  job_type varchar(40) not null default 'ExtractDevelopment',
  status varchar(20) not null check (status in ('Pending', 'Claimed', 'Completed', 'Failed', 'Dead')),
  priority smallint not null default 50 check (priority between 0 and 100),
  attempt_count smallint not null default 0 check (attempt_count between 0 and 20),
  claimed_by varchar(120),
  claimed_at timestamptz,
  available_at timestamptz not null default now(),
  completed_at timestamptz,
  last_error varchar(1000),
  expires_at timestamptz not null default (now() + interval '7 days'),
  created_at timestamptz not null default now(),
  unique (source_item_id, job_type)
);
create index processing_jobs_claim_idx on public.processing_jobs (status, available_at, priority desc, created_at);

create table public.exceptions (
  id uuid primary key default gen_random_uuid(),
  development_id uuid not null references public.developments(id) on delete cascade,
  exception_type varchar(100) not null,
  reason varchar(1200) not null,
  status varchar(20) not null default 'Open' check (status in ('Open', 'Resolved', 'Dismissed')),
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  expires_at timestamptz
);

create table public.linkedin_drafts (
  id uuid primary key default gen_random_uuid(),
  development_id uuid not null references public.developments(id) on delete cascade,
  content varchar(3000) not null,
  angle varchar(40) not null check (angle in ('Technical', 'Strategic', 'Career or learning')),
  status varchar(20) not null default 'Draft' check (status in ('Draft', 'Published')),
  pinned boolean not null default false,
  external_url varchar(2000) check (external_url is null or external_url ~ '^https://'),
  content_fingerprint char(64),
  published_at timestamptz,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '48 hours')
);
create index linkedin_drafts_expiry_idx on public.linkedin_drafts (expires_at) where not pinned;

create or replace function public.scrub_published_linkedin_content()
returns trigger language plpgsql set search_path = public as $$
begin
  if new.status = 'Published' and old.status <> 'Published' and not new.pinned then
    new.content_fingerprint = coalesce(new.content_fingerprint, encode(extensions.digest(new.content, 'sha256'), 'hex'));
    new.content = '';
  end if;
  return new;
end;
$$;
create trigger linkedin_drafts_scrub before update on public.linkedin_drafts
for each row execute function public.scrub_published_linkedin_content();

create table public.reports (
  id uuid primary key default gen_random_uuid(),
  report_type varchar(20) not null check (report_type in ('Daily', 'Weekly', 'Topic')),
  title varchar(200) not null,
  summary varchar(1200) not null,
  body varchar(12000) not null,
  development_ids jsonb not null default '[]'::jsonb,
  period_start timestamptz not null,
  period_end timestamptz not null,
  publication_status varchar(20) not null check (publication_status in ('Published', 'Held')),
  model_identifier varchar(120),
  prompt_template_version varchar(80),
  published_at timestamptz,
  created_at timestamptz not null default now(),
  unique (report_type, period_start, period_end)
);

create table public.daily_metrics (
  date date primary key,
  sources_checked integer not null default 0,
  items_detected integer not null default 0,
  items_rejected integer not null default 0,
  jobs_processed integer not null default 0,
  developments_published integer not null default 0,
  jobs_failed integer not null default 0,
  updated_at timestamptz not null default now()
);

create table public.operational_logs (
  id bigint generated always as identity primary key,
  event_type varchar(100) not null,
  severity varchar(10) not null check (severity in ('INFO', 'WARN', 'ERROR')),
  source_id uuid references public.sources(id) on delete set null,
  job_id uuid references public.processing_jobs(id) on delete set null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '7 days')
);

create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = public as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
create trigger sources_updated before update on public.sources for each row execute function public.set_updated_at();
create trigger developments_updated before update on public.developments for each row execute function public.set_updated_at();

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
    content_hash, title_hash, event_type_hint, language, status, rejection_reason, expires_at
  ) values (
    (item->>'source_id')::uuid, item->>'source_identifier', item->>'url',
    coalesce(item->>'canonical_url', item->>'url'), left(item->>'title', 500),
    nullif(item->>'published_at', '')::timestamptz, left(coalesce(item->>'excerpt', ''), 1200),
    item->>'content_hash', item->>'title_hash', left(item->>'event_type_hint', 80),
    left(coalesce(item->>'language', 'en'), 12), item_status, item->>'rejection_reason',
    case when item_status in ('Rejected', 'Irrelevant') then now() + interval '7 days' else null end
  ) on conflict do nothing returning id into inserted_id;

  if inserted_id is null then
    return jsonb_build_object('inserted', false, 'reason', 'duplicate');
  end if;

  if item_status = 'Candidate' and exists (
    select 1 from public.source_items existing
    where existing.id <> inserted_id and existing.title_hash = item->>'title_hash'
      and existing.detected_at >= now() - interval '72 hours'
  ) then
    update public.source_items set status = 'Rejected', rejection_reason = 'exact_title_duplicate', expires_at = now() + interval '7 days' where id = inserted_id;
    return jsonb_build_object('inserted', true, 'queued', false, 'reason', 'exact_title_duplicate');
  end if;

  if item_status = 'Candidate' then
    select count(*) into pending_count from public.processing_jobs where status in ('Pending', 'Claimed');
    select max_pending_jobs into pending_limit from public.private_settings where id;
    if pending_count >= pending_limit then
      update public.source_items set status = 'Rejected', rejection_reason = 'queue_limit', expires_at = now() + interval '7 days' where id = inserted_id;
      return jsonb_build_object('inserted', true, 'queued', false, 'reason', 'queue_limit');
    end if;
    insert into public.processing_jobs (source_item_id, status, priority)
    values (inserted_id, 'Pending', case item->>'event_type_hint' when 'release' then 75 when 'research' then 60 else 50 end);
    update public.source_items set status = 'Queued' where id = inserted_id;
  end if;
  return jsonb_build_object('inserted', true, 'queued', item_status = 'Candidate', 'source_item_id', inserted_id);
end;
$$;

create or replace function public.claim_processing_jobs(p_worker text, p_batch_size integer default 5)
returns setof public.processing_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  with candidates as (
    select j.id from public.processing_jobs j
    where j.status = 'Pending' and j.available_at <= now() and j.expires_at > now()
    order by j.priority desc, j.created_at
    for update skip locked
    limit least(greatest(p_batch_size, 1), 20)
  )
  update public.processing_jobs j
  set status = 'Claimed', claimed_by = left(p_worker, 120), claimed_at = now(), attempt_count = attempt_count + 1
  from candidates c where j.id = c.id
  returning j.*;
end;
$$;

create or replace function public.finalize_processing_job(
  p_job_id uuid, p_result jsonb, p_decision jsonb, p_model_identifier text, p_prompt_version text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  new_development_id uuid := gen_random_uuid();
  item_id uuid;
  source_primary boolean;
  slug_value text;
  linkedin_allowed boolean := false;
  ref jsonb;
begin
  select source_item_id into item_id from public.processing_jobs
    where id = p_job_id and status = 'Claimed' for update;
  if item_id is null then raise exception 'job is not currently claimed'; end if;
  select s.is_primary_source into source_primary from public.source_items si join public.sources s on s.id = si.source_id where si.id = item_id;
  slug_value := trim(both '-' from regexp_replace(lower(p_result->>'headline'), '[^a-z0-9]+', '-', 'g')) || '-' || left(new_development_id::text, 8);
  insert into public.developments (
    id, slug, headline, summary, why_it_matters, what_changed, limitations, who_affected,
    watch_next, organisation, product, release_date, event_type, category, importance_label,
    confidence_label, verification_status, publication_status, confirmed_claims, reported_claims,
    model_identifier, prompt_template_version, published_at
  ) values (
    new_development_id, left(slug_value, 280), p_result->>'headline', p_result->>'summary',
    p_result->>'why_it_matters', p_result->>'what_changed',
    left(coalesce((select string_agg(value, E'\n') from jsonb_array_elements_text(p_result->'limitations')), ''), 2400),
    p_result->>'who_affected', p_result->>'watch_next', p_result->>'organisation', p_result->>'product',
    nullif(p_result->>'release_date', '')::timestamptz, p_result->>'event_type', p_result->>'category',
    p_result->>'importance_label', p_decision->>'confidence_label', p_decision->>'verification_status',
    p_decision->>'publication_status', p_result->'confirmed_claims', p_result->'reported_claims',
    left(p_model_identifier, 120), left(p_prompt_version, 80),
    case when p_decision->>'publication_status' = 'Published' then now() else null end
  );
  for ref in select value from jsonb_array_elements(p_result->'evidence') loop
    if (ref->>'source_item_id')::uuid <> item_id then raise exception 'unknown evidence source'; end if;
    insert into public.development_sources (development_id, source_item_id, evidence_role, is_primary)
    values (new_development_id, item_id, ref->>'role', source_primary) on conflict do nothing;
  end loop;
  if p_decision->>'exception_type' is not null then
    insert into public.exceptions (development_id, exception_type, reason)
    values (new_development_id, p_decision->>'exception_type', left(array_to_string(array(select jsonb_array_elements_text(p_decision->'reasons')), '; '), 1200));
  end if;
  update public.processing_jobs set status = 'Completed', completed_at = now(), expires_at = now() + interval '7 days' where id = p_job_id;
  update public.source_items set status = 'Completed', expires_at = null where id = item_id;
  if p_decision->>'publication_status' = 'Published'
     and lower(p_result->>'category') ~ '(agent|infrastructure|security|knowledge graph|machine learning|developer|robot|autonomous)'
     and not exists (select 1 from public.linkedin_drafts where created_at >= date_trunc('day', now())) then
    linkedin_allowed := true;
  end if;
  return jsonb_build_object('development_id', new_development_id, 'linkedin_allowed', linkedin_allowed);
end;
$$;

create or replace function public.fail_processing_job(p_job_id uuid, p_error_message text, p_retryable boolean default true)
returns void language plpgsql security definer set search_path = public as $$
declare attempts integer;
begin
  select attempt_count into attempts from public.processing_jobs where id = p_job_id for update;
  update public.processing_jobs set
    status = case when p_retryable and attempts < 3 then 'Pending' when attempts >= 3 then 'Dead' else 'Failed' end,
    available_at = case when p_retryable and attempts < 3 then now() + make_interval(mins => (2 ^ attempts)::integer) else available_at end,
    claimed_by = null, claimed_at = null, last_error = left(p_error_message, 1000),
    expires_at = case when attempts >= 3 or not p_retryable then now() + interval '14 days' else expires_at end
  where id = p_job_id;
end;
$$;

create or replace function public.create_linkedin_draft(p_development_id uuid, p_draft jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare new_id uuid; ttl integer;
begin
  if exists (select 1 from public.linkedin_drafts where created_at >= date_trunc('day', now())) then
    return jsonb_build_object('created', false, 'reason', 'daily_limit');
  end if;
  select linkedin_draft_ttl_hours into ttl from public.private_settings where id;
  insert into public.linkedin_drafts (development_id, content, angle, content_fingerprint, expires_at)
  values (p_development_id, p_draft->>'content', p_draft->>'angle', encode(extensions.digest(p_draft->>'content', 'sha256'), 'hex'), now() + make_interval(hours => ttl))
  returning id into new_id;
  return jsonb_build_object('created', true, 'id', new_id);
end;
$$;

create or replace function public.create_verified_report(
  p_report_type text, p_report jsonb, p_period_start timestamptz, p_period_end timestamptz,
  p_model_identifier text, p_prompt_version text
) returns jsonb language plpgsql security definer set search_path = public as $$
declare new_id uuid;
begin
  if exists (select 1 from public.reports r where r.report_type = p_report_type and r.created_at >= case when p_report_type = 'Daily' then date_trunc('day', now()) else date_trunc('week', now()) end) then
    return jsonb_build_object('created', false, 'reason', 'period_already_exists');
  end if;
  if jsonb_array_length(p_report->'development_ids') < case when p_report_type = 'Daily' then 3 else 5 end then
    raise exception 'insufficient evidence for report';
  end if;
  insert into public.reports (report_type, title, summary, body, development_ids, period_start, period_end,
    publication_status, published_at, model_identifier, prompt_template_version)
  values (p_report_type, p_report->>'title', p_report->>'summary', p_report->>'body', p_report->'development_ids',
    p_period_start, p_period_end, 'Published', now(), left(p_model_identifier, 120), left(p_prompt_version, 80))
  returning id into new_id;
  return jsonb_build_object('id', new_id);
end;
$$;

create or replace function public.cleanup_expired_data()
returns jsonb language plpgsql security definer set search_path = public as $$
declare drafts_count integer; items_count integer; jobs_count integer; exceptions_count integer; logs_count integer;
begin
  delete from public.linkedin_drafts where not pinned and expires_at <= now(); get diagnostics drafts_count = row_count;
  update public.source_items si set status = 'Rejected', rejection_reason = 'pending_age_limit', expires_at = now()
    where exists (select 1 from public.processing_jobs j where j.source_item_id = si.id and j.status in ('Pending', 'Claimed') and j.expires_at <= now());
  delete from public.processing_jobs where status in ('Pending', 'Claimed') and expires_at <= now();
  delete from public.source_items si where si.status in ('Rejected', 'Irrelevant') and si.expires_at <= now()
    and not exists (select 1 from public.development_sources ds where ds.source_item_id = si.id); get diagnostics items_count = row_count;
  delete from public.processing_jobs where status in ('Completed', 'Failed', 'Dead') and expires_at <= now(); get diagnostics jobs_count = row_count;
  delete from public.exceptions where status in ('Resolved', 'Dismissed') and coalesce(expires_at, resolved_at + interval '30 days') <= now(); get diagnostics exceptions_count = row_count;
  delete from public.operational_logs where expires_at <= now(); get diagnostics logs_count = row_count;
  return jsonb_build_object('linkedin_drafts', drafts_count, 'source_items', items_count, 'processing_jobs', jobs_count, 'exceptions', exceptions_count, 'logs', logs_count);
end;
$$;

create or replace function public.aggregate_daily_metrics(metric_date date default current_date)
returns void language plpgsql security definer set search_path = public as $$
begin
  insert into public.daily_metrics (
    date, sources_checked, items_detected, items_rejected, jobs_processed,
    developments_published, jobs_failed, updated_at
  ) values (
    metric_date,
    (select count(*) from public.operational_logs where event_type in ('source_success', 'source_error') and created_at >= metric_date and created_at < metric_date + 1),
    (select count(*) from public.source_items where detected_at >= metric_date and detected_at < metric_date + 1),
    (select count(*) from public.source_items where status in ('Rejected', 'Irrelevant') and detected_at >= metric_date and detected_at < metric_date + 1),
    (select count(*) from public.processing_jobs where completed_at >= metric_date and completed_at < metric_date + 1),
    (select count(*) from public.developments where published_at >= metric_date and published_at < metric_date + 1),
    (select count(*) from public.processing_jobs where status in ('Failed', 'Dead') and created_at >= metric_date and created_at < metric_date + 1),
    now()
  ) on conflict (date) do update set
    sources_checked = excluded.sources_checked,
    items_detected = excluded.items_detected,
    items_rejected = excluded.items_rejected,
    jobs_processed = excluded.jobs_processed,
    developments_published = excluded.developments_published,
    jobs_failed = excluded.jobs_failed,
    updated_at = now();
end;
$$;

create or replace function public.system_health_snapshot()
returns jsonb language plpgsql security definer set search_path = public as $$
begin
  if not public.is_owner() and auth.role() <> 'service_role' then raise exception 'owner access required'; end if;
  return (select jsonb_build_object(
    'healthy_sources', (select count(*) from public.sources where active and last_error is null),
    'failing_sources', (select count(*) from public.sources where active and last_error is not null),
    'pending_jobs', (select count(*) from public.processing_jobs where status = 'Pending'),
    'failed_jobs', (select count(*) from public.processing_jobs where status in ('Failed', 'Dead')),
    'open_exceptions', (select count(*) from public.exceptions where status = 'Open'),
    'last_collection', (select max(last_success_at) from public.sources),
    'last_processing', (select max(completed_at) from public.processing_jobs where status = 'Completed')
  ));
end;
$$;

create or replace function public.search_public_developments(p_query text)
returns setof public.developments
language sql
stable
security invoker
set search_path = public
as $$
  select d.* from public.developments d
  where d.publication_status = 'Published' and d.verification_status = 'Verified'
    and length(trim(p_query)) between 1 and 100
    and (
      d.search_document @@ websearch_to_tsquery('english', p_query)
      or lower(d.published_at::date::text) = lower(trim(p_query))
      or exists (
        select 1 from public.development_sources ds
        join public.source_items si on si.id = ds.source_item_id
        join public.sources s on s.id = si.source_id
        where ds.development_id = d.id and s.name ilike '%' || replace(trim(p_query), '%', '\%') || '%'
      )
    )
  order by d.published_at desc
  limit 40;
$$;

alter table public.private_settings enable row level security;
alter table public.sources enable row level security;
alter table public.source_items enable row level security;
alter table public.developments enable row level security;
alter table public.development_sources enable row level security;
alter table public.processing_jobs enable row level security;
alter table public.exceptions enable row level security;
alter table public.linkedin_drafts enable row level security;
alter table public.reports enable row level security;
alter table public.daily_metrics enable row level security;
alter table public.operational_logs enable row level security;

create policy "public reads active sources" on public.sources for select using (active);
create policy "owner manages sources" on public.sources for all using (public.is_owner()) with check (public.is_owner());
create policy "public reads published developments" on public.developments for select using (publication_status = 'Published' and verification_status = 'Verified');
create policy "owner manages developments" on public.developments for all using (public.is_owner()) with check (public.is_owner());
create policy "public reads published evidence links" on public.development_sources for select using (
  exists (select 1 from public.developments d where d.id = development_id and d.publication_status = 'Published' and d.verification_status = 'Verified')
);
create policy "owner manages evidence links" on public.development_sources for all using (public.is_owner()) with check (public.is_owner());
create policy "public reads supporting metadata" on public.source_items for select using (
  exists (select 1 from public.development_sources ds join public.developments d on d.id = ds.development_id
    where ds.source_item_id = source_items.id and d.publication_status = 'Published' and d.verification_status = 'Verified')
);
create policy "owner manages source items" on public.source_items for all using (public.is_owner()) with check (public.is_owner());
create policy "public reads published reports" on public.reports for select using (publication_status = 'Published');
create policy "owner manages reports" on public.reports for all using (public.is_owner()) with check (public.is_owner());

create policy "owner only private settings" on public.private_settings for all using (public.is_owner()) with check (public.is_owner());
create policy "owner only processing jobs" on public.processing_jobs for all using (public.is_owner()) with check (public.is_owner());
create policy "owner only exceptions" on public.exceptions for all using (public.is_owner()) with check (public.is_owner());
create policy "owner only linkedin drafts" on public.linkedin_drafts for all using (public.is_owner()) with check (public.is_owner());
create policy "owner only metrics" on public.daily_metrics for all using (public.is_owner()) with check (public.is_owner());
create policy "owner only logs" on public.operational_logs for all using (public.is_owner()) with check (public.is_owner());

revoke all on public.private_settings, public.processing_jobs, public.exceptions, public.linkedin_drafts, public.daily_metrics, public.operational_logs from anon;
grant select on public.sources, public.source_items, public.developments, public.development_sources, public.reports to anon, authenticated;
grant all on public.private_settings, public.sources, public.source_items, public.developments, public.development_sources, public.processing_jobs, public.exceptions, public.linkedin_drafts, public.reports, public.daily_metrics, public.operational_logs to authenticated;
grant all on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to service_role;
revoke all on function public.ingest_source_item(jsonb) from public, anon, authenticated;
revoke all on function public.claim_processing_jobs(text, integer) from public, anon, authenticated;
revoke all on function public.finalize_processing_job(uuid, jsonb, jsonb, text, text) from public, anon, authenticated;
revoke all on function public.fail_processing_job(uuid, text, boolean) from public, anon, authenticated;
revoke all on function public.create_linkedin_draft(uuid, jsonb) from public, anon, authenticated;
revoke all on function public.create_verified_report(text, jsonb, timestamptz, timestamptz, text, text) from public, anon, authenticated;
revoke all on function public.cleanup_expired_data() from public, anon, authenticated;
revoke all on function public.aggregate_daily_metrics(date) from public, anon, authenticated;
revoke all on function public.system_health_snapshot() from public, anon;
grant execute on function public.ingest_source_item(jsonb) to service_role;
grant execute on function public.claim_processing_jobs(text, integer) to service_role;
grant execute on function public.finalize_processing_job(uuid, jsonb, jsonb, text, text) to service_role;
grant execute on function public.fail_processing_job(uuid, text, boolean) to service_role;
grant execute on function public.create_linkedin_draft(uuid, jsonb) to service_role;
grant execute on function public.create_verified_report(text, jsonb, timestamptz, timestamptz, text, text) to service_role;
grant execute on function public.cleanup_expired_data() to service_role;
grant execute on function public.aggregate_daily_metrics(date) to service_role;
grant execute on function public.system_health_snapshot() to authenticated, service_role;
grant execute on function public.search_public_developments(text) to anon, authenticated;

commit;
