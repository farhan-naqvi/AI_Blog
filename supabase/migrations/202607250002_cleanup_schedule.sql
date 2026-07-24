-- Supabase enables pg_cron from Database > Extensions. Apply this migration
-- after enabling it. The function itself is service-only and RLS-safe.
create extension if not exists pg_cron with schema extensions;

select cron.unschedule(jobid)
from cron.job
where jobname = 'signalwatch-retention-cleanup';

select cron.schedule(
  'signalwatch-retention-cleanup',
  '17 * * * *',
  $$select public.cleanup_expired_data();$$
);

select cron.unschedule(jobid)
from cron.job
where jobname = 'signalwatch-daily-metrics';

select cron.schedule(
  'signalwatch-daily-metrics',
  '10 1 * * *',
  $$select public.aggregate_daily_metrics(current_date - 1);$$
);
