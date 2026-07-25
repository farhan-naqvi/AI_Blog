alter table public.developments alter column what_changed drop not null;

create or replace function public.claim_processing_job_by_id(p_worker text, p_job_id uuid)
returns setof public.processing_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  update public.processing_jobs j
  set status = 'Claimed',
      claimed_by = left(p_worker, 120),
      claimed_at = now(),
      attempt_count = j.attempt_count + 1
  where j.id = (
    select candidate.id
    from public.processing_jobs candidate
    where candidate.id = p_job_id
      and candidate.status = 'Pending'
      and candidate.available_at <= now()
      and candidate.expires_at > now()
    for update skip locked
  )
  returning j.*;
end;
$$;

revoke all on function public.claim_processing_job_by_id(text, uuid) from public, anon, authenticated;
grant execute on function public.claim_processing_job_by_id(text, uuid) to service_role;
