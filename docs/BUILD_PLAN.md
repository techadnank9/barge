# Build plan — one feature at a time, test after each

Build in this order. Each step has a test. Do NOT move to the next step until
the current test passes. Commit after each green step. A working step 2 beats a
broken step 5.

For each step: build the honesty/failure path FIRST, then the success path.

---

## Step 0 — repo + env
Set up the monorepo layout, install deps, create `.env` from `.env.example`.

**Test:** `python services/mcp_service.py --help` (or equivalent) runs without
import errors; `npm run dev` in `web/` serves a blank page.

---

## Step 1 — Supabase + schema
Create the Supabase project. Apply `supabase/schema.sql`. Wire a Supabase client
into a small Python helper (`services/store.py`) that replaces the local-file
`practice_store.py`.

**Test:** a throwaway script inserts one practice entry and reads it back. Row
visible in the Supabase table editor.

---

## Step 2 — Phone: answer + HONEST SMS failure
Port `reference-python/phone_server.py`. Wire the SMS send. Point it at an
UNVERIFIED number on purpose.

**Test (failure path first):** call the number (or POST to `/finish` in a test),
confirm the agent says "nothing was sent" and does NOT claim success when the
SMS API returns non-200.

**Then success path:** verify your own number (`verify_number.py`), send for
real, confirm the text lands and a `practice_entries` row is inserted (source
`phone`).

---

## Step 3 — Phone: full coaching flow
Song selection with seed hit AND generate-on-miss (honor the `confident` flag),
the coached turn loop, hard-spot capture.

**Test:** call, say a SEED song (e.g. "Wonderwall") → coached with verified
chords. Call again, say a NON-seed song → generated chart, and if unsure the
agent says so. Say "that was fast" → hard spot captured and appears in the SMS.

---

## Step 4 — Dashboard (Next.js + Supabase realtime)
Build the dashboard in `web/`. Subscribe to `practice_entries` inserts. Render
each row live: song, source badge (phone/voiceos), hard spots, timestamp.

**Test:** with the dashboard open, insert a row by hand in Supabase → it appears
within ~1s without refresh. Complete a phone call from step 3 → that row appears
live too.

---

## Step 5 — VoiceOS MCP connector
Port `reference-python/mcp_connector.py`. Writes go through `services/store.py`
to Supabase. Serve streamable HTTP at `/mcp/`.

**Test (mechanism):** an MCP client (`fastmcp.Client` or the inspector CLI)
lists the four tools and calls `get_chord_chart` successfully.

**Test (end-to-end):** add the connector to VoiceOS by URL
(`http://localhost:8000/mcp/`), say "log my Wonderwall practice," approve the
confirm card, and watch the row appear on the dashboard tagged `voiceos`.

---

## Step 6 — End-to-end + polish
Both surfaces feed one dashboard. Tighten copy, timing, and the demo script.
Rehearse both moments end to end.

**Test:** a full dry run of both demos back to back, including deliberately
triggering a phone SMS failure to show the honest branch on stage.

---

## Guardrails for the whole build
- Never claim a side effect that didn't happen. This is the disqualifying rule.
- Keep the voice services in Python; reuse `reference-python/`.
- Keep secrets in env vars. Rotate anything exposed.
- If a step's test fails, fix it before continuing. No skipping ahead.
