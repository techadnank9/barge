-- Close the Loop — Supabase schema
-- One table both voice services write to and the dashboard reads live.

create table if not exists practice_entries (
  id           bigint generated always as identity primary key,
  created_at   timestamptz not null default now(),
  source       text not null check (source in ('phone', 'voiceos')),
  song         text not null,
  hard_spots   text[] not null default '{}',
  note         text not null default '',
  confident    boolean not null default true,
  call_sid     text
);

-- Links a phone practice entry to its call_turns transcript. Null for
-- voiceos entries (no phone call) and for entries created before this
-- column existed.
alter table practice_entries add column if not exists call_sid text;

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

-- ---------------------------------------------------------------------------
-- Live call transcript: one row per turn (caller speech or agent line),
-- keyed by CallSid. Lets the dashboard show an in-progress phone call
-- turn-by-turn, not just the finished practice_entries summary.
-- ---------------------------------------------------------------------------
create table if not exists call_turns (
  id           bigint generated always as identity primary key,
  created_at   timestamptz not null default now(),
  call_sid     text not null,
  speaker      text not null check (speaker in ('caller', 'agent')),
  text         text not null
);

create index if not exists call_turns_created_at_idx
  on call_turns (created_at desc);
create index if not exists call_turns_call_sid_idx
  on call_turns (call_sid);

alter publication supabase_realtime add table call_turns;

alter table call_turns enable row level security;

create policy "anon can read call turns"
  on call_turns for select
  to anon
  using (true);

-- No anon insert/update/delete on purpose: only the phone service's
-- service-role key writes turns.
