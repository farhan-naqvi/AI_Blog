begin;

alter table public.reports
  add column if not exists report_level varchar(30) not null default 'Briefing'
  check (report_level in ('Briefing', 'Monitoring digest'));

create or replace function public.development_visibility_blocker(p_development_id uuid)
returns text
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  development_record public.developments%rowtype;
begin
  select * into development_record from public.developments where id = p_development_id;
  if not found then return 'missing'; end if;

  if lower(development_record.event_type) = 'security'
     or lower(development_record.category) ~ '(security|medical|politic|legal accusation|misconduct|job loss|financial)'
     or exists (
       select 1 from public.exceptions e
       where e.development_id = p_development_id and e.status = 'Open'
         and lower(e.exception_type) = 'sensitive'
     ) then
    return 'sensitivity';
  end if;

  if exists (
       select 1 from public.development_sources ds
       where ds.development_id = p_development_id and ds.claim_consistency = 'Contradictory'
     ) or exists (
       select 1 from public.exceptions e
       where e.development_id = p_development_id and e.status = 'Open'
         and (lower(e.exception_type) = 'evidence conflict' or lower(e.reason) like '%contradict%')
     ) then
    return 'contradiction';
  end if;

  if development_record.verification_status <> 'Verified'
     or jsonb_array_length(development_record.confirmed_claims) = 0
     or not exists (
       select 1 from public.development_sources ds
       where ds.development_id = p_development_id
         and ds.is_primary
         and ds.evidence_role in ('Primary announcement', 'Documentation', 'Repository', 'Research paper')
     )
     or not exists (
       select 1 from public.development_sources ds
       join public.source_items si on si.id = ds.source_item_id
       where ds.development_id = p_development_id and si.status = 'Completed'
     ) then
    return 'evidence';
  end if;

  if exists (
    select 1 from public.exceptions e
    where e.development_id = p_development_id and e.status = 'Open'
  ) then
    return 'other_hold';
  end if;

  return 'eligible';
end;
$$;

create or replace function public.is_development_publicly_eligible(p_development_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.development_visibility_blocker(p_development_id) = 'eligible';
$$;

create or replace function public.is_development_publicly_visible(p_development_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.developments d
    where d.id = p_development_id
      and d.publication_status = 'Published'
      and public.is_development_publicly_eligible(d.id)
  );
$$;

create or replace function public.recalculate_public_visibility(p_dry_run boolean default true)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  result jsonb;
  made_public integer := 0;
begin
  with classified as (
    select
      d.id,
      d.importance_label,
      d.publication_status,
      public.development_visibility_blocker(d.id) as blocker
    from public.developments d
  ), counts as (
    select
      count(*) filter (where blocker = 'eligible' and publication_status <> 'Published') as eligible,
      count(*) filter (where blocker <> 'eligible') as remaining_private,
      count(*) filter (where blocker = 'eligible' and publication_status = 'Published') as already_public,
      count(*) filter (where blocker = 'sensitivity') as sensitivity,
      count(*) filter (where blocker = 'evidence') as evidence,
      count(*) filter (where blocker = 'contradiction') as contradiction,
      count(*) filter (where blocker = 'other_hold') as other_hold
    from classified
  ), importance_counts as (
    select coalesce(jsonb_object_agg(importance_label, amount), '{}'::jsonb) as values
    from (
      select importance_label, count(*) as amount
      from classified
      where blocker = 'eligible' and publication_status <> 'Published'
      group by importance_label
    ) grouped
  )
  select jsonb_build_object(
    'dry_run', p_dry_run,
    'eligible_for_public_visibility', counts.eligible,
    'remaining_privately_held', counts.remaining_private,
    'unchanged_already_public', counts.already_public,
    'blocked_by_sensitivity', counts.sensitivity,
    'blocked_by_evidence', counts.evidence,
    'blocked_by_contradiction', counts.contradiction,
    'blocked_by_other_hold', counts.other_hold,
    'eligible_by_importance', importance_counts.values,
    'records_made_public', 0
  ) into result
  from counts cross join importance_counts;

  if not p_dry_run then
    update public.developments d
    set publication_status = 'Published',
        published_at = coalesce(d.published_at, now()),
        updated_at = now()
    where d.publication_status <> 'Published'
      and public.is_development_publicly_eligible(d.id);
    get diagnostics made_public = row_count;
    result := jsonb_set(result, '{records_made_public}', to_jsonb(made_public));
    insert into public.operational_logs (event_type, severity, details)
    values ('visibility_policy_recalculation', 'INFO', result);
  end if;

  return result;
end;
$$;

drop policy if exists "public reads published developments" on public.developments;
create policy "public reads eligible developments" on public.developments for select
using (public.is_development_publicly_visible(id));

drop policy if exists "public reads published evidence links" on public.development_sources;
create policy "public reads eligible evidence links" on public.development_sources for select using (
  public.is_development_publicly_visible(development_id)
);

drop policy if exists "public reads supporting metadata" on public.source_items;
create policy "public reads eligible supporting metadata" on public.source_items for select using (
  exists (
    select 1 from public.development_sources ds
    where ds.source_item_id = source_items.id
      and public.is_development_publicly_visible(ds.development_id)
  )
);

drop policy if exists "public reads published reports" on public.reports;
create policy "public reads safe published reports" on public.reports for select using (
  publication_status = 'Published'
  and not exists (
    select 1 from jsonb_array_elements_text(development_ids) development_id
    where not public.is_development_publicly_visible(development_id::uuid)
  )
);

create or replace function public.search_public_developments(p_query text)
returns setof public.developments
language sql
stable
security invoker
set search_path = public
as $$
  select d.* from public.developments d
  where public.is_development_publicly_visible(d.id)
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
  order by
    case d.importance_label when 'Major' then 1 when 'Notable' then 2 else 3 end,
    d.published_at desc
  limit 40;
$$;

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
      select count(*) from public.developments d where public.is_development_publicly_visible(d.id)
    ),
    'verified_public_development_count', (
      select count(*) from public.developments d where public.is_development_publicly_visible(d.id)
    ),
    'major_notable_public_count', (
      select count(*) from public.developments d
      where public.is_development_publicly_visible(d.id) and d.importance_label in ('Major', 'Notable')
    ),
    'incremental_verified_update_count', (
      select count(*) from public.developments d
      where public.is_development_publicly_visible(d.id) and d.importance_label = 'Incremental'
    ),
    'internally_held_count', (
      select count(*) from public.developments d where not public.is_development_publicly_visible(d.id)
    ),
    'last_successful_collection_at', (select max(last_success_at) from public.sources where active),
    'last_public_report_at', (select max(published_at) from public.reports where publication_status = 'Published')
  );
$$;

create or replace function public.create_verified_report(
  p_report_type text, p_report jsonb, p_period_start timestamptz, p_period_end timestamptz,
  p_model_identifier text, p_prompt_version text
) returns jsonb language plpgsql security definer set search_path = public as $$
declare
  new_id uuid;
  report_level_value text := coalesce(p_report->>'report_level', 'Briefing');
  requested_count integer;
  eligible_count integer;
  briefing_count integer;
begin
  if report_level_value not in ('Briefing', 'Monitoring digest') then
    raise exception 'invalid report level';
  end if;
  if p_report_type <> 'Daily' and report_level_value = 'Monitoring digest' then
    raise exception 'monitoring digests are daily only';
  end if;
  if exists (
    select 1 from public.reports r
    where r.report_type = p_report_type
      and r.created_at >= case when p_report_type = 'Daily' then date_trunc('day', now()) else date_trunc('week', now()) end
  ) then
    return jsonb_build_object('created', false, 'reason', 'period_already_exists');
  end if;

  requested_count := jsonb_array_length(p_report->'development_ids');
  select count(*), count(*) filter (where d.importance_label in ('Major', 'Notable'))
    into eligible_count, briefing_count
  from public.developments d
  where d.id::text in (select jsonb_array_elements_text(p_report->'development_ids'))
    and public.is_development_publicly_visible(d.id);

  if eligible_count <> requested_count then
    raise exception 'report references ineligible development';
  end if;
  if p_report_type = 'Daily' and report_level_value = 'Briefing' and briefing_count < 3 then
    raise exception 'daily briefing requires three Major or Notable developments';
  end if;
  if p_report_type = 'Daily' and report_level_value = 'Monitoring digest' and eligible_count < 3 then
    raise exception 'daily monitoring digest requires three verified public developments';
  end if;
  if p_report_type <> 'Daily' and eligible_count < 5 then
    raise exception 'insufficient evidence for report';
  end if;

  insert into public.reports (
    report_type, report_level, title, summary, body, development_ids, period_start, period_end,
    publication_status, published_at, model_identifier, prompt_template_version
  ) values (
    p_report_type, report_level_value, p_report->>'title', p_report->>'summary', p_report->>'body',
    p_report->'development_ids', p_period_start, p_period_end, 'Published', now(),
    left(p_model_identifier, 120), left(p_prompt_version, 80)
  ) returning id into new_id;
  return jsonb_build_object('id', new_id, 'report_level', report_level_value);
end;
$$;

revoke all on function public.development_visibility_blocker(uuid) from public, anon, authenticated;
revoke all on function public.is_development_publicly_eligible(uuid) from public, anon, authenticated;
revoke all on function public.is_development_publicly_visible(uuid) from public, anon, authenticated;
revoke all on function public.recalculate_public_visibility(boolean) from public, anon, authenticated;
grant execute on function public.is_development_publicly_visible(uuid) to anon, authenticated, service_role;
grant execute on function public.recalculate_public_visibility(boolean) to service_role;

commit;
