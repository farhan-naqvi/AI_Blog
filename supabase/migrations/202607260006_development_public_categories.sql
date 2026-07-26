begin;

alter table public.developments
  add column if not exists public_category varchar(50)
  check (public_category in (
    'Models',
    'Agents and developer tools',
    'Research and AI science',
    'Infrastructure and hardware',
    'Business and products',
    'Policy, safety and security'
  ));

update public.developments d
set public_category = (
  select s.connector_config->>'public_category' as public_category
  from public.development_sources ds
  join public.source_items si on si.id = ds.source_item_id
  join public.sources s on s.id = si.source_id
  where ds.development_id = d.id
    and s.connector_config->>'public_category' is not null
  order by ds.is_primary desc, ds.created_at
  limit 1
)
where d.public_category is null;

create or replace function public.set_development_public_category()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.developments d
  set public_category = s.connector_config->>'public_category'
  from public.source_items si
  join public.sources s on s.id = si.source_id
  where d.id = new.development_id
    and si.id = new.source_item_id
    and d.public_category is null
    and s.connector_config->>'public_category' is not null;
  return new;
end;
$$;

drop trigger if exists development_sources_set_public_category on public.development_sources;
create trigger development_sources_set_public_category
after insert on public.development_sources
for each row execute function public.set_development_public_category();

revoke all on function public.set_development_public_category() from public, anon, authenticated;

commit;
