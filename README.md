# Close the Loop — guitar coaching voice agent

A voice agent that coaches guitar over two surfaces and produces **verifiable
side effects**:

- **Phone (main):** call a real number, get coached through a song by voice,
  receive the chords by SMS. The text landing is the confirmable result.
- **VoiceOS (bonus):** a custom MCP connector VoiceOS drives by voice —
  "log my practice" writes a row that appears live on a dashboard. The row
  landing is the confirmable result.

Both surfaces share one coaching brain (`songs.py`) and one practice log
(a single Supabase table, `practice_entries`).

**The one rule that governs every design decision here:** the agent never
claims a side effect that didn't happen. It says "texted you" only after the
SMS API returns 200. It says "logged" only after the Supabase write succeeds.
On any failure it says so plainly instead of guessing or pretending. See
[The honesty rule](#the-honesty-rule) below for how this is enforced in code.

---

## Table of contents
- [Architecture](#architecture)
- [Components](#components)
- [Functional flow](#functional-flow)
- [The honesty rule](#the-honesty-rule)
- [Data model](#data-model)
- [Repo layout](#repo-layout)
- [Local setup](#local-setup)
- [Deployment (Render)](#deployment-render)
- [API reference](#api-reference)
- [Build status](#build-status)

---

## Architecture

Two Python voice services and one Next.js dashboard, joined by Supabase. The
two voice surfaces never talk to each other directly — Supabase is the only
seam, so either half can be down without breaking the other.

```
   Caller (phone)                         VoiceOS (desktop, voice)
        |                                        |
        v                                        v
  a1mobile telephony                     Custom MCP connector
   (TeXML webhook)                        (fastmcp, HTTP /mcp/)
        |                                        |
        v                                        v
  Phone service (Flask) ------.      .---- MCP service (fastmcp)
   services/phone_server.py    \    /      services/mcp_service.py
        |                       \  /              |
   real SMS out                  \/        tools: get_chord_chart,
   (a1mobile /api/sms)        Supabase      log_practice, schedule_practice,
        |                (practice_entries)       recent_practices
        |                       table              |
        '------------------> insert <-------------'
                               |
                               | realtime subscription (postgres_changes)
                               v
                     Next.js dashboard (web/)
                     row appears live on insert, no polling
```

Both `phone_server.py` and `mcp_service.py` import the same `get_chart()`
function from `reference-python/songs.py` — one coaching brain, no forked
logic between the two surfaces. Both write through the same
`services/store.py` — one persistence seam.

## Components

### 1. Coaching brain — `reference-python/songs.py`
Pure logic, no I/O beyond an optional LLM call. `get_chart(name)` returns
`(chart_dict, source)`:
- **Seed hit** (`source="seed"`) — one of 5 hand-verified songs (Wonderwall,
  Let It Be, Knockin' on Heaven's Door, A Horse with No Name, Three Little
  Birds). `confident: true`, no LLM call, the coach can vouch for these.
- **Generated** (`source="generated"`) — anything else goes to the LLM (OpenAI
  or the a1mobile gateway, `openai.gpt-5.6-sol`) with a strict JSON schema.
  The model sets its own `confident` flag; if it isn't sure, the agent says
  so out loud *before* coaching invented chords.
- **Error** — LLM call throws → `(None, "error")` → the agent says it
  couldn't find the song, offers the seed songs instead. Never fabricates.

### 2. Phone service — `services/phone_server.py` (Flask, port from `PORT`/`PHONE_PORT`)
Answers a1mobile calls via TeXML (must return `application/xml` or the call
drops). Walkie-talkie turn structure, per-call state kept in an in-memory
dict keyed by `CallSid` (fine for a hackathon; resets on restart):

```
/voice  ->  /handle-song  ->  /handle-turn (loops)  ->  /finish
```

- `/voice` — answer, greet, ask for a song.
- `/handle-song` — resolve the chart via `get_chart()`. Miss → offer seed
  songs, re-ask. Never guess a song exists.
- `/handle-turn` — coaches TIMING and DELIVERY only ("you're rushing, hold
  the Em7 a beat longer"). Never claims to hear the strings — phone audio
  can't reliably detect chords, and a wrong "you played G" is fabrication.
  Loops until the caller says "done"/"finish"/"text me", or flags a hard
  spot ("that was hard", "too fast", "again") which gets captured for the
  SMS.
- `/finish` — the deciding step. Sends the real SMS via a1mobile. **Only on
  HTTP 200** does it say "texted you, ending XXXX" and insert a
  `practice_entries` row (`source="phone"`). On any other status or a
  network exception, it says "nothing was sent" and inserts nothing.

### 3. MCP service — `services/mcp_service.py` (fastmcp, HTTP `/mcp/`, port from `PORT`/`MCP_PORT`)
A purpose-built VoiceOS connector (not a generic off-the-shelf integration),
serving four tools over streamable HTTP:

| Tool | Effect |
|---|---|
| `get_chord_chart(song)` | Reads the coaching brain. No side effect. |
| `log_practice(song, hard_spots, note)` | **The side-effecting tool.** Inserts a `practice_entries` row (`source="voiceos"`). Returns `logged: false` with an error message if the write fails — never claims `logged: true` on failure. |
| `schedule_practice(song, when)` | Records a follow-up in the same table. Same honesty guarantee. |
| `recent_practices(limit)` | Reads back recent entries. |

VoiceOS shows a confirm card before any write-capable tool fires, so a
spoken "log my Wonderwall practice" is a two-step: confirm, then the actual
Supabase insert.

### 4. Persistence — `services/store.py` + Supabase
Two functions, `add_entry()` and `recent_entries()`, backed by
`supabase-py` using the **service-role key** (server-side only, bypasses
RLS). Both voice services import from here — it's the only place either
service talks to Supabase, and the only place that can raise on failure so
callers know whether to claim success.

### 5. Dashboard — `web/` (Next.js App Router + `@supabase/supabase-js`)
The surface judges watch. On load: `select('*').order('created_at',
{ascending:false}).limit(50)` so the board isn't empty. Then subscribes:

```ts
supabase.channel('practice')
  .on('postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'practice_entries' },
      handler)
  .subscribe()
```

New rows are prepended, briefly highlighted, tagged with a source badge
(`Phone` / `VoiceOS`), and show hard spots + an "unverified chords" badge
when `confident: false`. Uses the **anon key** only — read-only by RLS
policy, never the service-role key in the browser.

## Functional flow

### Phone surface, end to end
1. Caller dials the a1mobile number → `/voice` greets, asks for a song.
2. Caller names a song → normalized (lowercased, punctuation stripped,
   filler words like "play" / "the song" dropped) → looked up.
   - **Seed hit** → coach from verified data, no LLM call.
   - **Miss** → LLM generates a chart with a `confident` flag.
     - `confident: true` → coach normally.
     - `confident: false` → agent says "this is a common version, I'm not
       certain it's exact" *before* coaching — never states invented chords
       as fact.
   - **Couldn't find or generate** → offers the seed songs by name.
   - **Mumbled / silent** → re-asks, doesn't guess.
3. Coached practice loop: names the section, counts in, calls the chord
   changes, corrects timing/delivery. After ~2 reps of the verse, moves to
   the chorus (if the song has one), then offers to wrap up. Any spot the
   caller flags as hard is captured for the SMS.
4. Destination confirmation: uses caller ID, reads back the last 4 digits.
   Only asks for a number if caller ID is withheld.
5. `/finish` sends the SMS.
   - **API 200** → insert `practice_entries` (`source="phone"`), say
     "texted you, ending XXXX."
   - **Any failure** (non-200, timeout, exception) → say "the message
     didn't go through, nothing was sent." Never claims success. Suggests
     verifying the number or retrying.

### VoiceOS surface, end to end
1. User speaks a request — "log my Wonderwall practice, I struggled with
   the Em7 to G change" or "get me the chords for Three Little Birds."
2. VoiceOS routes the utterance to one of the four MCP tools.
3. For a write (`log_practice` / `schedule_practice`), VoiceOS shows a
   confirm card. User approves.
4. The tool inserts into Supabase (or returns an honest failure if the
   insert raises).
5. The insert pushes to the dashboard via realtime — a visible row landing,
   tagged `voiceos`, within about a second. Not "an MCP was called" — an
   actual row a judge can see appear.

### The honesty branches, summarized

| Surface | Success says | Failure says |
|---|---|---|
| Phone | "texted you, ending XXXX" (only on SMS API 200) | "nothing was sent" |
| VoiceOS | tool returns `logged: true` + row appears live | tool returns `logged: false` + error message, agent relays it |

## The honesty rule

This is the disqualifying rule for the hackathon, and it's enforced at the
code level, not just in the prompt/copy:

- `send_sms()` in `phone_server.py` returns `(ok: bool, detail: str)`. The
  `/finish` handler branches on `ok` — the SMS-success message is only
  reachable through that branch, not something the LLM can be talked into
  saying.
- `add_entry()` in `services/store.py` either returns the inserted row or
  raises. `mcp_service.py`'s `log_practice` / `schedule_practice` wrap it in
  `try/except` and return `logged: false` / `scheduled: false` with the
  error on failure — there's no code path that returns `true` without a
  confirmed Supabase insert.
- Practice log rows are only ever written from the success branch of each
  side effect (SMS 200, or a completed Supabase insert) — never
  speculatively, never before the effect is confirmed.

## Data model

One table, `practice_entries` (see `supabase/schema.sql`):

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint identity` | primary key |
| `created_at` | `timestamptz` | defaults `now()`, indexed desc for newest-first reads |
| `source` | `text` | `'phone'` or `'voiceos'` (checked) |
| `song` | `text` | |
| `hard_spots` | `text[]` | default `{}` |
| `note` | `text` | default `''` |
| `confident` | `boolean` | default `true` — false means LLM-generated and unverified |

Realtime is enabled on this table (`alter publication supabase_realtime add
table practice_entries`). RLS is on; `anon` may `select` only. There is no
anon insert/update/delete policy on purpose — only the server-side
service-role key (used by the two Python services) writes.

## Repo layout

```
CLAUDE.md               instructions for Claude Code (build order, rules)
README.md               this file
render.yaml             Render blueprint — deploys both Python services
.env.example            all secrets/config (copy to .env)
docs/
  ARCHITECTURE.md        technical architecture (source doc for this README)
  FUNCTIONAL_FLOW.md      functional flow (source doc for this README)
  BUILD_PLAN.md           phased build plan with a test gate per step
  API_REFERENCE.md        a1mobile endpoints + VoiceOS Add-dialog values
supabase/
  schema.sql              the one shared table + RLS + realtime
reference-python/         tested reference logic (songs.py used as-is)
  songs.py                 coaching brain: 5 seed songs + generate-on-miss
  phone_server.py           original reference (superseded by services/phone_server.py)
  mcp_connector.py          original reference (superseded by services/mcp_service.py)
  practice_store.py         original local-file store (superseded by services/store.py)
  verify_number.py          a1mobile OTP verification CLI, used as-is
services/                 built: Python services wired to Supabase
  store.py                  the Supabase seam — add_entry() / recent_entries()
  phone_server.py            Flask TeXML webhook, ported from reference
  mcp_service.py             fastmcp VoiceOS connector, ported from reference
  requirements.txt           deps for both services (flask, fastmcp, supabase, gunicorn, ...)
  test_store.py               Step 1 smoke test: insert + read back
web/                      built: Next.js + Supabase dashboard
  app/page.tsx                the live feed (realtime subscription)
  lib/supabase.ts             browser Supabase client (anon key)
```

## Local setup

1. `cp .env.example .env` and fill in:
   - `TEAM_KEY` — a1mobile team key.
   - `OPENAI_API_KEY` (+ `OPENAI_BASE_URL`, `LLM_MODEL` if using the
     a1mobile gateway instead of a personal OpenAI key).
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — from a Supabase project
     with `supabase/schema.sql` applied (SQL Editor → paste → run).
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` — same
     project, anon key (safe for the browser).
2. Python services:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r services/requirements.txt
   set -a; source .env; set +a
   .venv/bin/python services/phone_server.py   # PHONE_PORT, default 5000
   .venv/bin/python services/mcp_service.py    # MCP_PORT, default 8000
   ```
3. Dashboard:
   ```bash
   cd web && npm install && npm run dev   # http://localhost:3000
   ```
4. Expose the phone webhook for a real call:
   ```bash
   ngrok http 5050   # or whatever PHONE_PORT you used
   ```
   Point the a1mobile number's webhook at `https://<ngrok-host>/voice`
   (`POST /api/numbers/point`).
5. Add the MCP connector to VoiceOS: Integrations → Custom MCP → URL tab →
   `http://localhost:8000/mcp/` (keep the trailing slash).

## Deployment (Render)

`render.yaml` at the repo root is a Render Blueprint defining both Python
services (the dashboard is a separate concern — deploy it on Vercel/etc. if
needed, or run it locally on the demo laptop since it's what's on screen
either way):

- **close-the-loop-phone** — `gunicorn phone_server:app --chdir services
  --bind 0.0.0.0:$PORT`
- **close-the-loop-mcp** — `python services/mcp_service.py` (respects
  `PORT` and binds `0.0.0.0` via `MCP_HOST`)

To deploy:
1. Render dashboard → **New** → **Blueprint** → connect the GitHub repo.
   Render reads `render.yaml` and proposes both services.
2. Fill in the env vars marked `sync: false` per service (same values as
   your local `.env`): `TEAM_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
   `LLM_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
3. Deploy. You get two stable URLs, e.g.
   `https://close-the-loop-phone.onrender.com` and
   `https://close-the-loop-mcp.onrender.com` — no ngrok tunnel to babysit.
4. Point the a1mobile webhook at `https://<phone-service>.onrender.com/voice`.
5. Add the VoiceOS connector at `https://<mcp-service>.onrender.com/mcp/`.

Free-tier Render services spin down when idle and take a few seconds to
wake on the first request — worth a warm-up call a minute before judging.

## API reference

Full detail in `docs/API_REFERENCE.md`. Summary:

- **a1mobile** — base `https://hack.a1mobile.com`, auth header
  `X-Team-Key: <TEAM_KEY>`.
  - `POST /api/numbers/claim` — claim an inbound number.
  - `POST /api/numbers/point` — point its webhook at your `/voice`.
  - `POST /api/sms` — send an SMS (`{"to", "body"}`); only delivers to
    OTP-verified numbers or organizer test lines, else 403.
  - `POST /api/verified-numbers` / `POST /api/verified-numbers/confirm` —
    OTP verification flow (`reference-python/verify_number.py` does both).
- **VoiceOS** — Integrations → Custom MCP → URL tab → server URL
  `http://localhost:8000/mcp/` (or the deployed Render URL), auth blank.

## Build status

Following `docs/BUILD_PLAN.md`, one feature at a time, test gate after each,
commit after each green step:

- [x] **Step 0** — repo, venv, deps.
- [x] **Step 1** — Supabase schema applied; insert + read-back verified
      (`services/test_store.py`).
- [x] **Step 2** — phone answer + honest SMS failure (unverified number →
      "nothing sent", verified) AND real send (verified number → SMS
      delivered, row inserted).
- [x] **Step 3** — full coaching flow: seed hit, generate-on-miss via the
      a1mobile LLM gateway, hard-spot capture, verse→chorus transition —
      all exercised end to end via simulated call requests.
- [x] **Step 4** — dashboard renders existing rows on load and picks up new
      inserts live via realtime subscription, verified in-browser.
- [x] **Step 5** — MCP connector: `fastmcp.Client` listed all four tools,
      `get_chord_chart` and `log_practice` both verified against the live
      Supabase project, insert confirmed live on the dashboard.
- [ ] **Step 6** — end-to-end + polish: real phone call through a public
      webhook (ngrok or the Render deploy above), VoiceOS actually driving
      the MCP connector, rehearsed dry run including a deliberate SMS
      failure on stage.
