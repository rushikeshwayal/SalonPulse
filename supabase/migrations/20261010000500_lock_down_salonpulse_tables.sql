-- Keep customer and feedback data off the public Supabase Data API.
alter table public.branches enable row level security;
alter table public.barbers enable row level security;
alter table public.customers enable row level security;
alter table public.visits enable row level security;
alter table public.feedback enable row level security;
alter table public.recovery_tasks enable row level security;
alter table public.message_logs enable row level security;

revoke all on table public.branches from anon, authenticated;
revoke all on table public.barbers from anon, authenticated;
revoke all on table public.customers from anon, authenticated;
revoke all on table public.visits from anon, authenticated;
revoke all on table public.feedback from anon, authenticated;
revoke all on table public.recovery_tasks from anon, authenticated;
revoke all on table public.message_logs from anon, authenticated;
