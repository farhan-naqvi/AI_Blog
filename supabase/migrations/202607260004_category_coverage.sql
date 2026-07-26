begin;

alter table public.source_items
  add column if not exists cluster_key varchar(64)
  check (cluster_key is null or cluster_key ~ '^[0-9a-f]{64}$');
create index if not exists source_items_cluster_key_idx
  on public.source_items (cluster_key, detected_at desc) where cluster_key is not null;

update public.sources
set connector_config = connector_config || jsonb_build_object(
  'public_category',
  case
    when name in ('OpenAI News', 'Hugging Face Blog', 'Google AI Blog',
      'Hugging Face OpenAI models', 'Hugging Face Meta Llama models',
      'Hugging Face Mistral models', 'Anthropic News', 'Google DeepMind',
      'Meta AI', 'Mistral AI News', 'Cohere Blog', 'GitHub QwenLM/Qwen')
      then 'Models'
    when name in ('GitHub Blog', 'GitHub langchain-ai/langchain',
      'GitHub langfuse/langfuse', 'GitHub modelcontextprotocol/specification')
      then 'Agents and developer tools'
    when connector_key = 'arxiv' or name = 'Microsoft Research'
      then 'Research and AI science'
    when name in ('GitHub ollama/ollama', 'GitHub vllm-project/vllm',
      'GitHub huggingface/transformers', 'GitHub pytorch/pytorch',
      'GitHub tensorflow/tensorflow', 'GitHub jax-ml/jax',
      'GitHub ggml-org/llama.cpp', 'GitHub NVIDIA/TensorRT-LLM',
      'NVIDIA AI', 'AWS Machine Learning', 'Cloudflare AI', 'Databricks AI')
      then 'Infrastructure and hardware'
    when source_type = 'Government' or connector_key = 'eurlex'
      then 'Policy, safety and security'
    else 'Business and products'
  end
);

insert into public.sources
  (name, base_url, source_type, retrieval_method, connector_key, connector_config,
   is_primary_source, reliability_level, poll_interval_minutes, rate_limit_per_hour, active)
values
  ('GitHub google-deepmind/gemma', 'https://github.com/google-deepmind/gemma', 'Open source', 'API', 'github', '{"repository":"google-deepmind/gemma","public_category":"Models"}', true, 'High', 120, 30, true),
  ('GitHub meta-llama/llama-models', 'https://github.com/meta-llama/llama-models', 'Open source', 'API', 'github', '{"repository":"meta-llama/llama-models","public_category":"Models"}', true, 'High', 120, 30, true),
  ('GitHub mistralai/mistral-inference', 'https://github.com/mistralai/mistral-inference', 'Open source', 'API', 'github', '{"repository":"mistralai/mistral-inference","public_category":"Models"}', true, 'High', 120, 30, true),
  ('GitHub deepseek-ai/DeepSeek-V3', 'https://github.com/deepseek-ai/DeepSeek-V3', 'Open source', 'API', 'github', '{"repository":"deepseek-ai/DeepSeek-V3","public_category":"Models"}', true, 'High', 120, 30, true),
  ('GitHub allenai/OLMo', 'https://github.com/allenai/OLMo', 'Open source', 'API', 'github', '{"repository":"allenai/OLMo","public_category":"Models"}', true, 'High', 120, 30, true),
  ('GitHub langchain-ai/langgraph', 'https://github.com/langchain-ai/langgraph', 'Open source', 'API', 'github', '{"repository":"langchain-ai/langgraph","public_category":"Agents and developer tools"}', true, 'High', 120, 30, true),
  ('GitHub run-llama/llama_index', 'https://github.com/run-llama/llama_index', 'Open source', 'API', 'github', '{"repository":"run-llama/llama_index","public_category":"Agents and developer tools"}', true, 'High', 120, 30, true),
  ('GitHub crewAIInc/crewAI', 'https://github.com/crewAIInc/crewAI', 'Open source', 'API', 'github', '{"repository":"crewAIInc/crewAI","public_category":"Agents and developer tools"}', true, 'High', 120, 30, true),
  ('GitHub microsoft/autogen', 'https://github.com/microsoft/autogen', 'Open source', 'API', 'github', '{"repository":"microsoft/autogen","public_category":"Agents and developer tools"}', true, 'High', 120, 30, true),
  ('GitHub microsoft/semantic-kernel', 'https://github.com/microsoft/semantic-kernel', 'Open source', 'API', 'github', '{"repository":"microsoft/semantic-kernel","public_category":"Agents and developer tools"}', true, 'High', 120, 30, true),
  ('GitHub pydantic/pydantic-ai', 'https://github.com/pydantic/pydantic-ai', 'Open source', 'API', 'github', '{"repository":"pydantic/pydantic-ai","public_category":"Agents and developer tools"}', true, 'High', 120, 30, true),
  ('arXiv Foundation Models', 'https://export.arxiv.org/api/query', 'Research', 'API', 'arxiv', '{"categories":["cs.AI","cs.CL","cs.LG"],"keywords":["foundation model","large language model","multimodal model"],"public_category":"Research and AI science"}', true, 'High', 720, 10, true),
  ('arXiv AI Agents', 'https://export.arxiv.org/api/query', 'Research', 'API', 'arxiv', '{"categories":["cs.AI","cs.CL"],"keywords":["agent","tool use","planning"],"public_category":"Research and AI science"}', true, 'High', 720, 10, true),
  ('arXiv Computer Vision', 'https://export.arxiv.org/api/query', 'Research', 'API', 'arxiv', '{"categories":["cs.CV"],"keywords":["vision","image","video"],"public_category":"Research and AI science"}', true, 'High', 720, 10, true),
  ('arXiv Robotics', 'https://export.arxiv.org/api/query', 'Research', 'API', 'arxiv', '{"categories":["cs.RO"],"keywords":["robot","embodied","autonomous"],"public_category":"Research and AI science"}', true, 'High', 720, 10, true),
  ('arXiv AI Safety', 'https://export.arxiv.org/api/query', 'Research', 'API', 'arxiv', '{"categories":["cs.AI","cs.LG","cs.CR"],"keywords":["AI safety","alignment","robustness"],"public_category":"Research and AI science"}', true, 'High', 720, 10, true),
  ('arXiv ML Systems', 'https://export.arxiv.org/api/query', 'Research', 'API', 'arxiv', '{"categories":["cs.LG","cs.SE","cs.DC"],"keywords":["machine learning systems","distributed training","serving"],"public_category":"Research and AI science"}', true, 'High', 720, 10, true),
  ('arXiv Efficient Inference', 'https://export.arxiv.org/api/query', 'Research', 'API', 'arxiv', '{"categories":["cs.LG","cs.CL"],"keywords":["efficient inference","quantization","model compression"],"public_category":"Research and AI science"}', true, 'High', 720, 10, true),
  ('arXiv AI for Health and Science', 'https://export.arxiv.org/api/query', 'Research', 'API', 'arxiv', '{"categories":["cs.LG","q-bio.QM","q-bio.BM"],"keywords":["healthcare","biology","chemistry"],"public_category":"Research and AI science"}', true, 'High', 720, 10, true),
  ('GitHub ray-project/ray', 'https://github.com/ray-project/ray', 'Open source', 'API', 'github', '{"repository":"ray-project/ray","public_category":"Infrastructure and hardware"}', true, 'High', 120, 30, true),
  ('GitHub triton-lang/triton', 'https://github.com/triton-lang/triton', 'Open source', 'API', 'github', '{"repository":"triton-lang/triton","public_category":"Infrastructure and hardware"}', true, 'High', 120, 30, true),
  ('GitHub onnx/onnx', 'https://github.com/onnx/onnx', 'Open source', 'API', 'github', '{"repository":"onnx/onnx","public_category":"Infrastructure and hardware"}', true, 'High', 120, 30, true),
  ('GitHub mlcommons/inference', 'https://github.com/mlcommons/inference', 'Open source', 'API', 'github', '{"repository":"mlcommons/inference","public_category":"Infrastructure and hardware"}', true, 'High', 120, 30, true),
  ('GitHub apache/tvm', 'https://github.com/apache/tvm', 'Open source', 'API', 'github', '{"repository":"apache/tvm","public_category":"Infrastructure and hardware"}', true, 'High', 120, 30, true),
  ('Microsoft Official Blog', 'https://blogs.microsoft.com/feed/', 'Official company', 'RSS', 'rss', '{"public_category":"Business and products"}', true, 'High', 60, 24, true),
  ('AWS Machine Learning Feed', 'https://aws.amazon.com/blogs/machine-learning/feed/', 'Official company', 'RSS', 'rss', '{"public_category":"Business and products"}', true, 'High', 60, 24, true),
  ('Google Cloud Blog', 'https://cloudblog.withgoogle.com/rss/', 'Official company', 'RSS', 'rss', '{"public_category":"Business and products"}', true, 'High', 60, 24, true),
  ('European Commission Digital Strategy', 'https://digital-strategy.ec.europa.eu/en/rss.xml', 'Government', 'RSS', 'rss', '{"public_category":"Policy, safety and security"}', true, 'High', 360, 8, true),
  ('NIST News', 'https://www.nist.gov/news-events/news/rss.xml', 'Government', 'RSS', 'rss', '{"public_category":"Policy, safety and security"}', true, 'High', 360, 8, true),
  ('UK AI Security Institute Updates', 'https://www.gov.uk/government/organisations/ai-security-institute.atom', 'Government', 'Atom', 'rss', '{"public_category":"Policy, safety and security"}', true, 'High', 360, 8, true),
  ('GitHub Stability-AI/generative-models', 'https://github.com/Stability-AI/generative-models', 'Open source', 'API', 'github', '{"repository":"Stability-AI/generative-models","public_category":"Models"}', true, 'High', 120, 30, false),
  ('GitHub NVIDIA/NeMo', 'https://github.com/NVIDIA/NeMo', 'Open source', 'API', 'github', '{"repository":"NVIDIA/NeMo","public_category":"Models"}', true, 'High', 120, 30, false),
  ('GitHub stanfordnlp/dspy', 'https://github.com/stanfordnlp/dspy', 'Open source', 'API', 'github', '{"repository":"stanfordnlp/dspy","public_category":"Agents and developer tools"}', true, 'High', 120, 30, false),
  ('GitHub Arize-ai/phoenix', 'https://github.com/Arize-ai/phoenix', 'Open source', 'API', 'github', '{"repository":"Arize-ai/phoenix","public_category":"Agents and developer tools"}', true, 'High', 120, 30, false),
  ('GitHub PrefectHQ/marvin', 'https://github.com/PrefectHQ/marvin', 'Open source', 'API', 'github', '{"repository":"PrefectHQ/marvin","public_category":"Agents and developer tools"}', true, 'High', 120, 30, false),
  ('GitHub ROCm/ROCm', 'https://github.com/ROCm/ROCm', 'Open source', 'API', 'github', '{"repository":"ROCm/ROCm","public_category":"Infrastructure and hardware"}', true, 'High', 120, 30, false),
  ('GitHub snowflakedb/snowpark-python', 'https://github.com/snowflakedb/snowpark-python', 'Open source', 'API', 'github', '{"repository":"snowflakedb/snowpark-python","public_category":"Infrastructure and hardware"}', true, 'High', 120, 30, false),
  ('GitHub huggingface/text-generation-inference', 'https://github.com/huggingface/text-generation-inference', 'Open source', 'API', 'github', '{"repository":"huggingface/text-generation-inference","public_category":"Infrastructure and hardware"}', true, 'High', 120, 30, false),
  ('GitHub google-ai-edge/mediapipe', 'https://github.com/google-ai-edge/mediapipe', 'Open source', 'API', 'github', '{"repository":"google-ai-edge/mediapipe","public_category":"Research and AI science"}', true, 'High', 120, 30, false)
on conflict (name) do update set
  base_url = excluded.base_url,
  source_type = excluded.source_type,
  retrieval_method = excluded.retrieval_method,
  connector_key = excluded.connector_key,
  connector_config = excluded.connector_config,
  is_primary_source = excluded.is_primary_source,
  reliability_level = excluded.reliability_level,
  poll_interval_minutes = excluded.poll_interval_minutes,
  rate_limit_per_hour = excluded.rate_limit_per_hour,
  active = excluded.active;

create or replace function public.ingest_source_item(item jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  inserted_id uuid;
  clustered_with uuid;
  item_status text := coalesce(item->>'status', 'Candidate');
  pending_count integer;
  pending_limit integer;
begin
  insert into public.source_items (
    source_id, source_identifier, url, canonical_url, title, published_at, excerpt,
    content_hash, title_hash, event_type_hint, language, status, rejection_reason, expires_at,
    release_metadata, cluster_key
  ) values (
    (item->>'source_id')::uuid, item->>'source_identifier', item->>'url',
    coalesce(item->>'canonical_url', item->>'url'), left(item->>'title', 500),
    nullif(item->>'published_at', '')::timestamptz, left(coalesce(item->>'excerpt', ''), 1200),
    item->>'content_hash', item->>'title_hash', left(item->>'event_type_hint', 80),
    left(coalesce(item->>'language', 'en'), 12), item_status, item->>'rejection_reason',
    case when item_status in ('Rejected', 'Irrelevant') then now() + interval '7 days' else null end,
    coalesce(nullif(item->'release_metadata', 'null'::jsonb), '{}'::jsonb),
    nullif(item->>'cluster_key', '')
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

  if item_status = 'Candidate' and nullif(item->>'cluster_key', '') is not null then
    select existing.id into clustered_with
    from public.source_items existing
    where existing.id <> inserted_id
      and existing.cluster_key = item->>'cluster_key'
      and existing.status in ('Queued', 'Processing', 'Completed')
      and existing.detected_at >= now() - interval '7 days'
    order by existing.detected_at
    limit 1;
    if clustered_with is not null then
      update public.source_items set status = 'Queued' where id = inserted_id;
      return jsonb_build_object('inserted', true, 'queued', false, 'clustered', true);
    end if;
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
    coalesce(s.connector_config->>'public_category', 'Business and products')::text,
    s.source_type::text,
    s.active,
    s.base_url::text,
    s.last_success_at::date
  from public.sources s
  where s.active
  order by 2, s.name;
$$;

create or replace function public.finalize_processing_job(
  p_job_id uuid, p_worker text, p_result jsonb, p_decision jsonb,
  p_model_identifier text, p_prompt_version text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  new_development_id uuid := gen_random_uuid();
  item_id uuid;
  item_cluster_key text;
  slug_value text;
  linkedin_allowed boolean := false;
  ref jsonb;
  ref_item_id uuid;
  ref_primary boolean;
begin
  select j.source_item_id, si.cluster_key into item_id, item_cluster_key
  from public.processing_jobs j
  join public.source_items si on si.id = j.source_item_id
  where j.id = p_job_id and j.status = 'Claimed' and j.claimed_by = left(p_worker, 120)
  for update of j;
  if item_id is null then raise exception 'job is not currently claimed'; end if;

  slug_value := trim(both '-' from regexp_replace(lower(p_result->>'headline'), '[^a-z0-9]+', '-', 'g'))
    || '-' || left(new_development_id::text, 8);
  insert into public.developments (
    id, slug, headline, summary, why_it_matters, what_changed, limitations, who_affected,
    watch_next, organisation, product, release_date, event_type, category, importance_label,
    confidence_label, verification_status, publication_status, confirmed_claims, reported_claims,
    model_identifier, prompt_template_version, published_at
  ) values (
    new_development_id, left(slug_value, 280), p_result->>'headline', p_result->>'summary',
    p_result->>'why_it_matters', coalesce(p_result->>'what_changed', ''),
    left(coalesce((select string_agg(value, E'\n') from jsonb_array_elements_text(p_result->'limitations')), ''), 2400),
    p_result->>'who_affected', p_result->>'watch_next', p_result->>'organisation', p_result->>'product',
    nullif(p_result->>'release_date', '')::timestamptz, p_result->>'event_type', p_result->>'category',
    p_result->>'importance_label', p_decision->>'confidence_label', p_decision->>'verification_status',
    p_decision->>'publication_status', p_result->'confirmed_claims', p_result->'reported_claims',
    left(p_model_identifier, 120), left(p_prompt_version, 80),
    case when p_decision->>'publication_status' = 'Published' then now() else null end
  );

  for ref in select value from jsonb_array_elements(p_result->'evidence') loop
    ref_item_id := (ref->>'source_item_id')::uuid;
    if not exists (
      select 1 from public.source_items candidate
      where candidate.id = ref_item_id
        and (candidate.id = item_id or (item_cluster_key is not null and candidate.cluster_key = item_cluster_key))
    ) then
      raise exception 'unknown evidence source';
    end if;
    select s.is_primary_source into ref_primary
    from public.source_items si join public.sources s on s.id = si.source_id
    where si.id = ref_item_id;
    insert into public.development_sources (development_id, source_item_id, evidence_role, is_primary)
    values (new_development_id, ref_item_id, ref->>'role', ref_primary)
    on conflict do nothing;
  end loop;

  if p_decision->>'exception_type' is not null then
    insert into public.exceptions (development_id, exception_type, reason)
    values (
      new_development_id,
      p_decision->>'exception_type',
      left(array_to_string(array(select jsonb_array_elements_text(p_decision->'reasons')), '; '), 1200)
    );
  end if;
  update public.processing_jobs
  set status = 'Completed', completed_at = now(), expires_at = now() + interval '7 days'
  where id = p_job_id;
  update public.source_items
  set status = 'Completed', expires_at = null
  where id = item_id or (item_cluster_key is not null and cluster_key = item_cluster_key);

  if p_decision->>'publication_status' = 'Published'
     and lower(p_result->>'category') ~ '(agent|infrastructure|security|knowledge graph|machine learning|developer|robot|autonomous)'
     and not exists (select 1 from public.linkedin_drafts where created_at >= date_trunc('day', now())) then
    linkedin_allowed := true;
  end if;
  return jsonb_build_object('development_id', new_development_id, 'linkedin_allowed', linkedin_allowed);
end;
$$;

revoke all on function public.ingest_source_item(jsonb) from public, anon, authenticated;
grant execute on function public.ingest_source_item(jsonb) to service_role;
revoke all on function public.finalize_processing_job(uuid, text, jsonb, jsonb, text, text)
  from public, anon, authenticated;
grant execute on function public.finalize_processing_job(uuid, text, jsonb, jsonb, text, text)
  to service_role;
revoke all on function public.get_public_sources() from public, anon, authenticated;
grant execute on function public.get_public_sources() to anon, authenticated, service_role;

commit;
