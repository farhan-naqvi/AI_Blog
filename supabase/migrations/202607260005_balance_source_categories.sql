begin;

update public.sources
set connector_config = connector_config || '{"public_category":"Business and products"}'::jsonb
where name in ('OpenAI News', 'GitHub Blog');

update public.sources
set connector_config = connector_config || jsonb_build_object(
  'categories', jsonb_build_array('cs.CR'),
  'keywords', jsonb_build_array('AI safety', 'machine learning security', 'adversarial'),
  'public_category', 'Policy, safety and security'
)
where name = 'arXiv Language Vision Robotics and Security';

update public.sources
set connector_config = connector_config || '{"public_category":"Policy, safety and security"}'::jsonb
where name = 'arXiv AI Safety';

update public.sources
set connector_config = connector_config || jsonb_build_object(
  'keywords', jsonb_build_array('foundation model', 'machine learning method', 'neural network')
)
where name = 'arXiv AI and ML';

commit;
