begin;

alter table public.developments
  drop constraint if exists developments_verification_status_check;

update public.developments
set verification_status = 'Developing', updated_at = now()
where verification_status = 'Held';

alter table public.developments
  add constraint developments_verification_status_check
  check (verification_status in ('Verified', 'Reported', 'Developing'));

alter table public.reports
  drop constraint if exists reports_report_level_check;

alter table public.reports
  add constraint reports_report_level_check
  check (report_level in ('Briefing', 'Monitoring digest', 'Activity summary'));

create or replace function public.development_evidence_classification(p_development_id uuid)
returns text
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  development_record public.developments%rowtype;
begin
  select * into development_record
  from public.developments
  where id = p_development_id;

  if not found then return 'extraction_failure'; end if;

  if development_record.publication_status = 'Rejected'
     or length(trim(development_record.headline)) < 8
     or length(trim(development_record.summary)) < 40 then
    return 'extraction_failure';
  end if;

  if lower(development_record.event_type) = 'security'
     or lower(development_record.category) ~ '(security|vulnerab|medical|clinical|politic|legal accusation|misconduct|job.loss|financial)'
     or exists (
       select 1 from public.exceptions e
       where e.development_id = p_development_id
         and e.status = 'Open'
         and lower(e.exception_type) = 'sensitive'
     ) then
    return 'sensitivity';
  end if;

  if exists (
       select 1 from public.development_sources ds
       where ds.development_id = p_development_id
         and ds.claim_consistency = 'Contradictory'
     ) or exists (
       select 1 from public.exceptions e
       where e.development_id = p_development_id
         and e.status = 'Open'
         and (lower(e.exception_type) = 'evidence conflict' or lower(e.reason) like '%contradict%')
     ) then
    return 'contradiction';
  end if;

  if not exists (
    select 1 from public.development_sources ds
    where ds.development_id = p_development_id
      and ds.is_primary
      and ds.evidence_role in ('Primary announcement', 'Documentation', 'Repository', 'Research paper')
  ) then
    return 'missing_primary_source';
  end if;

  if not exists (
       select 1
       from public.development_sources ds
       join public.source_items si on si.id = ds.source_item_id
       where ds.development_id = p_development_id
         and si.status = 'Completed'
     ) or exists (
       select 1 from public.exceptions e
       where e.development_id = p_development_id and e.status = 'Open'
     ) then
    return 'extraction_failure';
  end if;

  if jsonb_array_length(development_record.confirmed_claims) > 0 then
    return 'eligible_verified';
  end if;

  if jsonb_array_length(development_record.reported_claims) > 0 then
    return 'eligible_reported';
  end if;

  return 'extraction_failure';
end;
$$;

create or replace function public.development_visibility_blocker(p_development_id uuid)
returns text
language sql
stable
security definer
set search_path = public
as $$
  select public.development_evidence_classification(p_development_id);
$$;

create or replace function public.is_development_publicly_eligible(p_development_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.development_evidence_classification(p_development_id)
    in ('eligible_verified', 'eligible_reported');
$$;

create or replace function public.is_development_publicly_visible(p_development_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.developments d
    cross join lateral (
      select public.development_evidence_classification(d.id) as classification
    ) classified
    where d.id = p_development_id
      and d.publication_status = 'Published'
      and (
        (classified.classification = 'eligible_verified' and d.verification_status = 'Verified')
        or (classified.classification = 'eligible_reported' and d.verification_status = 'Reported')
      )
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
  verified_made_public integer := 0;
  reported_made_public integer := 0;
  made_private integer := 0;
  status_updates integer := 0;
begin
  with classified as (
    select
      d.id,
      d.verification_status,
      d.publication_status,
      public.development_evidence_classification(d.id) as classification
    from public.developments d
  ), counts as (
    select
      count(*) filter (where classification = 'eligible_verified') as eligible_verified,
      count(*) filter (where classification = 'eligible_reported') as eligible_reported,
      count(*) filter (where classification not in ('eligible_verified', 'eligible_reported')) as developing_private,
      count(*) filter (where classification = 'sensitivity') as sensitivity,
      count(*) filter (where classification = 'contradiction') as contradiction,
      count(*) filter (where classification = 'missing_primary_source') as missing_primary,
      count(*) filter (where classification = 'extraction_failure') as extraction_failure,
      count(*) filter (
        where classification = 'eligible_verified' and publication_status <> 'Published'
      ) as verified_to_publish,
      count(*) filter (
        where classification = 'eligible_reported' and publication_status <> 'Published'
      ) as reported_to_publish
    from classified
  )
  select jsonb_build_object(
    'dry_run', p_dry_run,
    'eligible_as_verified_public', counts.eligible_verified,
    'eligible_as_reported_public', counts.eligible_reported,
    'remaining_developing_private', counts.developing_private,
    'blocked_by_sensitivity', counts.sensitivity,
    'blocked_by_contradiction', counts.contradiction,
    'blocked_by_missing_primary_source', counts.missing_primary,
    'blocked_by_extraction_failure', counts.extraction_failure,
    'verified_records_to_make_public', counts.verified_to_publish,
    'reported_records_to_make_public', counts.reported_to_publish,
    'verified_records_made_public', 0,
    'reported_records_made_public', 0,
    'records_made_private', 0,
    'verification_status_updates', 0
  ) into result
  from counts;

  if not p_dry_run then
    with classified as (
      select
        d.id,
        d.verification_status,
        d.publication_status,
        public.development_evidence_classification(d.id) as classification
      from public.developments d
    )
    select
      count(*) filter (
        where classification = 'eligible_verified' and publication_status <> 'Published'
      ),
      count(*) filter (
        where classification = 'eligible_reported' and publication_status <> 'Published'
      ),
      count(*) filter (
        where classification not in ('eligible_verified', 'eligible_reported')
          and publication_status = 'Published'
      ),
      count(*) filter (
        where verification_status <> case
          when classification = 'eligible_verified' then 'Verified'
          when classification = 'eligible_reported' then 'Reported'
          else 'Developing'
        end
      )
    into verified_made_public, reported_made_public, made_private, status_updates
    from classified;

    update public.developments d
    set verification_status = case
          when classified.classification = 'eligible_verified' then 'Verified'
          when classified.classification = 'eligible_reported' then 'Reported'
          else 'Developing'
        end,
        publication_status = case
          when classified.classification in ('eligible_verified', 'eligible_reported') then 'Published'
          else 'Held'
        end,
        published_at = case
          when classified.classification in ('eligible_verified', 'eligible_reported')
            then coalesce(d.published_at, now())
          else null
        end,
        updated_at = now()
    from (
      select id, public.development_evidence_classification(id) as classification
      from public.developments
    ) classified
    where d.id = classified.id
      and (
        d.verification_status <> case
          when classified.classification = 'eligible_verified' then 'Verified'
          when classified.classification = 'eligible_reported' then 'Reported'
          else 'Developing'
        end
        or d.publication_status <> case
          when classified.classification in ('eligible_verified', 'eligible_reported') then 'Published'
          else 'Held'
        end
      );

    result := jsonb_set(result, '{verified_records_made_public}', to_jsonb(verified_made_public));
    result := jsonb_set(result, '{reported_records_made_public}', to_jsonb(reported_made_public));
    result := jsonb_set(result, '{records_made_private}', to_jsonb(made_private));
    result := jsonb_set(result, '{verification_status_updates}', to_jsonb(status_updates));

    insert into public.operational_logs (event_type, severity, details)
    values ('evidence_status_recalculation', 'INFO', result);
  end if;

  return result;
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
  where public.is_development_publicly_visible(d.id)
    and length(trim(p_query)) between 1 and 100
    and (
      d.search_document @@ websearch_to_tsquery('english', p_query)
      or lower(d.published_at::date::text) = lower(trim(p_query))
      or exists (
        select 1 from public.development_sources ds
        join public.source_items si on si.id = ds.source_item_id
        join public.sources s on s.id = si.source_id
        where ds.development_id = d.id
          and s.name ilike '%' || replace(trim(p_query), '%', '\%') || '%'
      )
    )
  order by
    case
      when d.verification_status = 'Verified' and d.importance_label = 'Major' then 1
      when d.verification_status = 'Reported' and d.importance_label = 'Major' then 2
      when d.verification_status = 'Verified' and d.importance_label = 'Notable' then 3
      when d.verification_status = 'Reported' and d.importance_label = 'Notable' then 4
      when d.verification_status = 'Verified' and d.importance_label = 'Incremental' then 5
      else 6
    end,
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
      select count(*) from public.developments d
      where public.is_development_publicly_visible(d.id) and d.verification_status = 'Verified'
    ),
    'reported_public_development_count', (
      select count(*) from public.developments d
      where public.is_development_publicly_visible(d.id) and d.verification_status = 'Reported'
    ),
    'developing_private_development_count', (
      select count(*) from public.developments d where not public.is_development_publicly_visible(d.id)
    ),
    'major_verified_public_count', (
      select count(*) from public.developments d
      where public.is_development_publicly_visible(d.id)
        and d.verification_status = 'Verified'
        and d.importance_label = 'Major'
    ),
    'major_notable_public_count', (
      select count(*) from public.developments d
      where public.is_development_publicly_visible(d.id)
        and d.importance_label in ('Major', 'Notable')
    ),
    'incremental_public_count', (
      select count(*) from public.developments d
      where public.is_development_publicly_visible(d.id) and d.importance_label = 'Incremental'
    ),
    'incremental_verified_update_count', (
      select count(*) from public.developments d
      where public.is_development_publicly_visible(d.id)
        and d.verification_status = 'Verified'
        and d.importance_label = 'Incremental'
    ),
    'internally_held_count', (
      select count(*) from public.developments d where not public.is_development_publicly_visible(d.id)
    ),
    'last_successful_collection_at', (select max(last_success_at) from public.sources where active),
    'last_public_report_at', (
      select max(published_at) from public.reports where publication_status = 'Published'
    )
  );
$$;

create or replace function public.create_verified_report(
  p_report_type text,
  p_report jsonb,
  p_period_start timestamptz,
  p_period_end timestamptz,
  p_model_identifier text,
  p_prompt_version text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  new_id uuid;
  report_level_value text := coalesce(p_report->>'report_level', 'Briefing');
  requested_count integer;
  eligible_count integer;
  verified_briefing_count integer;
begin
  if report_level_value not in ('Briefing', 'Monitoring digest', 'Activity summary') then
    raise exception 'invalid report level';
  end if;
  if p_report_type <> 'Daily' and report_level_value <> 'Briefing' then
    raise exception 'daily-only report level';
  end if;
  if exists (
    select 1 from public.reports r
    where r.report_type = p_report_type
      and r.created_at >= case
        when p_report_type = 'Daily' then date_trunc('day', now())
        else date_trunc('week', now())
      end
  ) then
    return jsonb_build_object('created', false, 'reason', 'period_already_exists');
  end if;

  requested_count := jsonb_array_length(p_report->'development_ids');
  select
    count(*),
    count(*) filter (
      where d.verification_status = 'Verified' and d.importance_label in ('Major', 'Notable')
    )
  into eligible_count, verified_briefing_count
  from public.developments d
  where d.id::text in (select jsonb_array_elements_text(p_report->'development_ids'))
    and public.is_development_publicly_visible(d.id);

  if eligible_count <> requested_count then
    raise exception 'report references ineligible development';
  end if;
  if p_report_type = 'Daily' and report_level_value = 'Briefing'
     and verified_briefing_count < 3 then
    raise exception 'daily briefing requires three Verified Major or Notable developments';
  end if;
  if p_report_type = 'Daily' and report_level_value = 'Monitoring digest'
     and eligible_count < 3 then
    raise exception 'daily monitoring digest requires three public developments';
  end if;
  if p_report_type = 'Daily' and report_level_value = 'Activity summary'
     and (eligible_count < 1 or eligible_count > 2) then
    raise exception 'daily activity summary requires one or two public developments';
  end if;
  if p_report_type <> 'Daily' and eligible_count < 5 then
    raise exception 'insufficient evidence for report';
  end if;

  insert into public.reports (
    report_type, report_level, title, summary, body, development_ids,
    period_start, period_end, publication_status, published_at,
    model_identifier, prompt_template_version
  ) values (
    p_report_type, report_level_value, p_report->>'title', p_report->>'summary',
    p_report->>'body', p_report->'development_ids', p_period_start, p_period_end,
    'Published', now(), left(p_model_identifier, 120), left(p_prompt_version, 80)
  ) returning id into new_id;

  return jsonb_build_object('id', new_id, 'report_level', report_level_value);
end;
$$;

revoke all on function public.development_evidence_classification(uuid) from public, anon, authenticated;
revoke all on function public.development_visibility_blocker(uuid) from public, anon, authenticated;
revoke all on function public.is_development_publicly_eligible(uuid) from public, anon, authenticated;
revoke all on function public.is_development_publicly_visible(uuid) from public, anon, authenticated;
revoke all on function public.recalculate_public_visibility(boolean) from public, anon, authenticated;
grant execute on function public.is_development_publicly_visible(uuid) to anon, authenticated, service_role;
grant execute on function public.recalculate_public_visibility(boolean) to service_role;

commit;
