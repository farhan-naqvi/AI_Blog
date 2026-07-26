begin;

create or replace function public.classify_development_public_category(
  p_category text,
  p_event_type text,
  p_source_category text
) returns text
language sql
immutable
set search_path = public
as $$
  select case
    when p_source_category = 'Infrastructure and hardware'
      and p_category in ('Models', 'Agents', 'Developer tools', 'Infrastructure', 'Other')
      then 'Infrastructure and hardware'
    when p_category = 'Models' then 'Models'
    when p_category in ('Agents', 'Developer tools') then 'Agents and developer tools'
    when p_category in ('Research', 'Robotics') then 'Research and AI science'
    when p_category = 'Infrastructure' then 'Infrastructure and hardware'
    when p_category in ('Regulation', 'Security') then 'Policy, safety and security'
    when p_event_type in ('Partnership', 'Funding') or p_category = 'Other'
      then 'Business and products'
    else coalesce(p_source_category, 'Business and products')
  end;
$$;

with preferred_source as (
  select distinct on (ds.development_id)
    ds.development_id,
    s.connector_config->>'public_category' as source_category
  from public.development_sources ds
  join public.source_items si on si.id = ds.source_item_id
  join public.sources s on s.id = si.source_id
  order by ds.development_id, ds.is_primary desc, ds.created_at
)
update public.developments d
set public_category = public.classify_development_public_category(
  d.category, d.event_type, preferred_source.source_category
)
from preferred_source
where preferred_source.development_id = d.id;

create or replace function public.set_development_public_category()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.developments d
  set public_category = public.classify_development_public_category(
    d.category,
    d.event_type,
    s.connector_config->>'public_category'
  )
  from public.source_items si
  join public.sources s on s.id = si.source_id
  where d.id = new.development_id
    and si.id = new.source_item_id
    and d.public_category is null;
  return new;
end;
$$;

revoke all on function public.classify_development_public_category(text, text, text)
  from public, anon, authenticated;
revoke all on function public.set_development_public_category() from public, anon, authenticated;

commit;
