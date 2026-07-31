# web/ — Next.js + Supabase dashboard

Claude Code builds this in step 4 of `docs/BUILD_PLAN.md`.

## What it is
A single live dashboard the judges watch. It subscribes to inserts on the
Supabase `practice_entries` table and renders each new row the instant it lands:
song, a source badge (phone vs voiceos), hard spots, and timestamp. Newest first,
with a brief highlight animation on arrival.

## Build notes
- Next.js App Router, `npm create next-app`.
- Use `@supabase/supabase-js` with the ANON key (read-only; RLS allows select).
  Never put the service-role key in the browser.
- Subscribe with Supabase realtime:
  `supabase.channel('practice').on('postgres_changes',
   { event: 'INSERT', schema: 'public', table: 'practice_entries' }, handler)
   .subscribe()`.
- Also do an initial `select(...).order('created_at', desc).limit(50)` so the
  board isn't empty on load.
- Keep it clean and flat: a header, then a list of cards. This is the "feels
  built" surface, so make it look like a product, but don't over-engineer.

## Env (web/.env.local)
```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

## Test (from BUILD_PLAN step 4)
With the page open, insert a row by hand in Supabase → it appears within ~1s
without refresh. Then a real phone call → its row appears live too.
