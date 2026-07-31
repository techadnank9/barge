-- Close the Loop — Supabase schema
-- One table both voice services write to and the dashboard reads live.

create table if not exists practice_entries (
  id           bigint generated always as identity primary key,
  created_at   timestamptz not null default now(),
  source       text not null check (source in ('phone', 'voiceos')),
  song         text not null,
  hard_spots   text[] not null default '{}',
  note         text not null default '',
  confident    boolean not null default true
);

-- newest-first reads
create index if not exists practice_entries_created_at_idx
  on practice_entries (created_at desc);

-- Realtime: let the dashboard subscribe to inserts.
alter publication supabase_realtime add table practice_entries;

-- Row Level Security.
-- The Python services use the service-role key (bypasses RLS) to insert.
-- The dashboard uses the anon key and only needs to READ.
alter table practice_entries enable row level security;

create policy "anon can read practice entries"
  on practice_entries for select
  to anon
  using (true);

-- No anon insert/update/delete policy on purpose: only the server-side
-- service-role key writes. Do not add a browser-side write policy.
