# Close the Loop — guitar coaching voice agent

A voice agent that coaches guitar over two surfaces and produces **verifiable
side effects**:

- **Phone (main):** call a real number, get coached through a song by a
  natural voice AI, receive the chords by SMS. The text landing is the
  confirmable result.
- **VoiceOS (bonus):** a custom MCP connector VoiceOS drives by voice —
  "log my practice" writes a row that appears live on a dashboard. The row
  landing is the confirmable result.

Both surfaces share one coaching brain (`songs.py`) and one Supabase-backed
practice log, all visible on a live dashboard.

**The one rule that governs every design decision here:** the agent never
claims a side effect that didn't happen. It says "texted you" only after the
SMS API returns 200. It logs a session only after a write actually succeeds
(and even an incomplete call is logged as *incomplete*, never as a fake
success). See [The honesty rule](#the-honesty-rule) for how this is enforced
in code, not just in prompts.

**Status:** fully deployed and working end to end — phone number live,
Vapi-driven conversation, real-time dashboard with live transcript + chord
chart, VoiceOS MCP connector. See [Current live deployment](#current-live-deployment)
for exact URLs, and [Known platform issue](#known-platform-issue-a1mobile-speech-gather)
for the one thing that changed the architecture mid-build.

---

## Table of contents
- [Current live deployment](#current-live-deployment)
- [Architecture](#architecture)
- [Known platform issue: a1mobile speech Gather](#known-platform-issue-a1mobile-speech-gather)
- [Components](#components)
- [Data model](#data-model)
- [The honesty rule](#the-honesty-rule)
- [Repo layout](#repo-layout)
- [Local setup](#local-setup)
- [Deployment](#deployment)
- [Vapi assistant config](#vapi-assistant-config)
- [Operational notes / gotchas](#operational-notes--gotchas)
- [Build status](#build-status)

---

## Current live deployment

| Piece | URL / value |
|---|---|
| Phone number (call this) | **+1 (313) 479-6171** |
| Landing page | https://close-the-loop-dashboard.vercel.app |
| Dashboard | https://close-the-loop-dashboard.vercel.app/dashboard |
| Live call view | `/dashboard/call?sid=<call_sid>` (linked from the dashboard automatically) |
| Logs viewer | https://close-the-loop-dashboard.vercel.app/dashboard/logs |
| Phone service (Render) | https://close-the-loop-phone.onrender.com |
| MCP service (Render) | https://close-the-loop-mcp.onrender.com/mcp/ |
| Vapi assistant | "Guitar Coach", id `72a2acf3-c1d1-496e-b04b-afeb819bec68` |
| Vapi SIP address (internal, not a real number) | `sip:close-the-loop-guitar-coach@sip.vapi.ai` |
| Repo | https://github.com/techadnank9/barge |
| Supabase project | `dnkpintlpoaydbqrppel` |

Render free-tier services sleep after inactivity. The dashboard has
wake/status buttons (green = awake, click to wake) for both services — use
them before a demo.

## Architecture

```
   Caller (phone)                         VoiceOS (desktop, voice)
        |                                        |
        v                                        v
  a1mobile telephony                     Custom MCP connector
   (TeXML webhook)                        (fastmcp, HTTP /mcp/)
        |                                        |
        v                                        v
  Phone service (Flask)                    MCP service (fastmcp)
  services/phone_server.py                 services/mcp_service.py
        |                                        |
   <Dial><Sip> bridge                     tools: get_chord_chart,
        |                                  log_practice, schedule_practice,
        v                                  recent_practices
  Vapi assistant                                 |
  (STT + LLM + TTS,                               |
   natural conversation)                          |
        |                                        |
        | tool-call webhooks                     |
        | (get-chord-chart, finish,               |
        |  transcript)                            |
        v                                        |
  Phone service (same Flask app) <-------- writes practice_entries,
        |                                  call_turns, call_charts
   real SMS out                                   |
   (a1mobile /api/sms)                             |
        |                                          |
        '---------------> Supabase <---------------'
                       (realtime subscriptions)
                               |
                               v
                     Next.js dashboard (web/)
              live practice log + live call transcript
              + live chord chart, all realtime, no polling
```

Both `phone_server.py` and `mcp_service.py` import the same `get_chart()`
function from `reference-python/songs.py` — one coaching brain, no forked
logic between the two surfaces. Both write through the same
`services/store.py` — one persistence seam.

## Known platform issue: a1mobile speech Gather

The original build (see git history before commit `9adf8d4`) used TeXML
`<Gather input="speech">` to capture what the caller said, with our own Flask
app driving the whole conversation turn by turn. **This does not work on
a1mobile's platform.** Real calls consistently returned
`SpeechResult: '' / Confidence: '0.0'` — a1mobile's TeXML cheatsheet only
documents `<Gather input="dtmf">` (keypad); free speech recognition isn't a
supported, documented primitive there.

The fix: `/voice` now returns `<Dial><Sip>{VAPI_SIP_URI}</Sip></Dial>`,
bridging the live call audio into a **Vapi** assistant, which brings its own
STT/LLM/TTS and handles the actual conversation. a1mobile still owns the
phone number, answers the call, carries the audio, and sends the SMS — Vapi
only replaces the broken "listen and understand" part. See
[Vapi assistant config](#vapi-assistant-config) for how that's wired.

If you ever need pure open speech recognition on a1mobile without Vapi, the
two documented alternatives are `<Connect><Stream>` (stream call audio to
your own websocket and run your own STT, their Pipecat starter-kit pattern)
or `<Dial><Sip>` into any other BYO voice AI platform (Retell, LiveKit, etc).

## Components

### 1. Coaching brain — `reference-python/songs.py`
Pure logic, no I/O beyond an optional LLM call. `get_chart(name)` returns
`(chart_dict, source)`:
- **Seed hit** (`source="seed"`) — hand-verified songs: Wonderwall, Let It
  Be, Knockin' on Heaven's Door, A Horse with No Name, Three Little Birds,
  Perfect (Ed Sheeran). `confident: true`. Matching is loose (substring, so
  STT mishears like "Perfect Sound" still resolve correctly).
- **Generated** (`source="generated"`) — anything else goes to the LLM
  (OpenAI or the a1mobile gateway) with a strict JSON schema. The model sets
  its own `confident` flag; if unsure, the agent says so *before* coaching
  invented chords. Output is defensively normalized (`_split_chords`) since
  the LLM sometimes joins a whole progression into one dash-separated string
  instead of separate array elements — that gets split back apart so the
  dashboard's one-card-per-chord UI doesn't break.
- **Error** — LLM call throws → `(None, "error")` → the agent says it
  couldn't find the song, offers the seed songs instead. Never fabricates.

### 2. Phone service — `services/phone_server.py` (Flask)
Two jobs:
- **`/voice`** — a1mobile webhook. Answers and bridges into Vapi via
  `<Dial><Sip>`. That's it — no more TeXML conversation logic.
- **Vapi tool-call webhooks** — Vapi calls back into this same service
  mid-conversation:
  - `POST /vapi/get-chord-chart` — reads the coaching brain, also upserts
    `call_charts` so the dashboard can show the chart live.
  - `POST /vapi/finish` — the honesty-critical one. Sends the real SMS via
    a1mobile; only on confirmed success does it insert a `practice_entries`
    row and tell Vapi `texted: true`.
  - `POST /vapi/transcript` — assistant-level webhook for two Vapi message
    types: `transcript` (final lines, logged live turn-by-turn as the call
    happens) and `end-of-call-report` (fires once when the call ends; used
    as (a) a backfill safety net for any transcript lines that didn't arrive
    live, and (b) to log a `practice_entries` row for **every** call, even
    ones that never reached `finish_session` — marked
    `"call ended before finishing - no text was sent"`, never claiming a
    text went out).

Also serves `GET /` (health/wake ping, CORS-open) and `GET /logs` (in-memory
ring buffer of recent events, CORS-open, for the dashboard's logs page).

### 3. Vapi assistant — "Guitar Coach"
Handles the actual conversation: greets, asks for a song, calls
`get_chord_chart`, coaches through the chords slowly with real pauses,
waits for the caller to say "ready" before counting them in, reacts to what
the caller actually says (never claims to hear their playing — phone audio
can't verify that, and pretending to would be dishonest), captures hard
spots, and calls `finish_session` when the caller's done. Full prompt and
tool config: [Vapi assistant config](#vapi-assistant-config).

### 4. MCP service — `services/mcp_service.py` (fastmcp, HTTP `/mcp/`)
A purpose-built VoiceOS connector serving four tools:

| Tool | Effect |
|---|---|
| `get_chord_chart(song)` | Reads the coaching brain. No side effect. |
| `log_practice(song, hard_spots, note)` | **The side-effecting tool.** Inserts a `practice_entries` row (`source="voiceos"`). Returns `logged: false` on failure — never claims success without a confirmed insert. |
| `schedule_practice(song, when)` | Records a follow-up. Same honesty guarantee. |
| `recent_practices(limit)` | Reads back recent entries. |

VoiceOS shows a confirm card before any write-capable tool fires.

### 5. Persistence — `services/store.py` + Supabase
The only place either Python service talks to Supabase, using the
**service-role key** (server-side only, bypasses RLS):
`add_entry`, `recent_entries`, `add_turn`, `has_turns`, `set_call_chart`,
`get_call_chart`, `has_entry_for_call`.

### 6. Dashboard — `web/` (Next.js App Router, static export, `@supabase/supabase-js`)
- **`/`** — landing page (guitar-themed, call button, link to dashboard).
- **`/dashboard`** — practice log. Wake/status buttons for both Render
  services. A red pulsing **"Call in progress"** banner appears the instant
  a call starts (before any practice entry exists), linking to the live
  view. Each phone entry with a `call_sid` is clickable → its transcript.
- **`/dashboard/call?sid=&song=`** — full-page view: live chord chart (step
  cards, "press in order") above a live/final transcript, both realtime.
- **`/dashboard/logs`** — polls both services' `/logs` endpoints every 4s,
  merges and displays recent backend events (useful for debugging what a
  real call actually sent, e.g. `SpeechResult` payloads back when that was
  still the mechanism).

Everything subscribes via Supabase realtime (`postgres_changes`) — no
polling except the logs page, which hits plain HTTP endpoints, not Supabase.

## Data model

Three tables (`supabase/schema.sql`), all realtime-enabled, RLS on with
`anon` read-only (service-role key writes):

**`practice_entries`** — one row per completed or incomplete coaching
session.
| Column | Type | Notes |
|---|---|---|
| `id` | `bigint identity` | primary key |
| `created_at` | `timestamptz` | default `now()` |
| `source` | `text` | `'phone'` or `'voiceos'` |
| `song` | `text` | |
| `hard_spots` | `text[]` | default `{}` |
| `note` | `text` | e.g. `"coached by phone (vapi)"` or `"call ended before finishing - no text was sent"` |
| `confident` | `boolean` | false = LLM-generated, unverified |
| `call_sid` | `text` | links to `call_turns` / `call_charts`; null for voiceos entries |

**`call_turns`** — one row per turn of a phone call transcript.
| Column | Type | Notes |
|---|---|---|
| `id` | `bigint identity` | primary key |
| `created_at` | `timestamptz` | |
| `call_sid` | `text` | Vapi's call id |
| `speaker` | `text` | `'caller'` or `'agent'` |
| `text` | `text` | |

**`call_charts`** — the chart currently (or last) being coached on a call,
one row per `call_sid` (upserted).
| Column | Type | Notes |
|---|---|---|
| `call_sid` | `text` | primary key |
| `updated_at` | `timestamptz` | |
| `song` | `text` | |
| `verse` / `chorus` | `text[]` | one chord per element |
| `hard_spots` | `text[]` | |
| `confident` | `boolean` | |
| `current_section` | `text` | `'verse'` or `'chorus'` — which section the dashboard highlights as "you are here". Set by `advance_section`; verse and chorus chords both stay visible regardless. |

## The honesty rule

Enforced at the code level, not just in prompts:

- `send_sms()` returns `(ok: bool, detail: str)`. `/vapi/finish` branches on
  `ok` — the "texted" result is only reachable through that branch.
- `add_entry()` either returns the inserted row or raises; every write site
  wraps it so a failure never gets reported as success.
- The Vapi system prompt explicitly forbids claiming to hear whether the
  caller played a chord correctly (phone audio can't verify that) and
  forbids stating unconfident/generated chords as fact without saying so
  first.
- Every call gets logged to the dashboard now (per user request), but
  incomplete ones are unambiguously marked `"call ended before finishing -
  no text was sent"` — visibility was extended, the no-fabrication rule
  wasn't relaxed.

## Repo layout

```
CLAUDE.md               instructions for Claude Code (build order, rules)
README.md               this file
render.yaml              Render blueprint — deploys both Python services
.env.example             all secrets/config (copy to .env)
docs/                    original planning docs (some now superseded by this README - see Known platform issue)
supabase/
  schema.sql               practice_entries + call_turns + call_charts, RLS, realtime
reference-python/
  songs.py                  coaching brain: seed songs + generate-on-miss + normalization
  verify_number.py          a1mobile OTP verification CLI, used as-is
  phone_server.py, mcp_connector.py, practice_store.py   original reference, superseded by services/
services/
  store.py                  the Supabase seam
  phone_server.py            Flask: /voice SIP bridge + Vapi tool webhooks + health/logs
  mcp_service.py             fastmcp VoiceOS connector
  requirements.txt           flask, fastmcp, supabase, gunicorn, ...
  test_store.py               Step 1 smoke test
web/
  app/page.tsx                 landing page
  app/dashboard/page.tsx       practice log + live-call banner
  app/dashboard/call/page.tsx  live chord chart + transcript for one call
  app/dashboard/logs/page.tsx  backend event log viewer
  components/                  ServiceStatus, LiveCallBanner, ChordChart, CallTranscript
  lib/supabase.ts               browser Supabase client (anon key) + shared types
```

## Local setup

1. `cp .env.example .env` and fill in `TEAM_KEY`, `OPENAI_API_KEY` (+
   `OPENAI_BASE_URL`/`LLM_MODEL` for the a1mobile gateway),
   `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and add
   `VAPI_SIP_URI=sip:close-the-loop-guitar-coach@sip.vapi.ai` (or your own,
   see below). `web/.env.local` needs `NEXT_PUBLIC_SUPABASE_URL` /
   `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
2. Apply `supabase/schema.sql` in the Supabase SQL Editor if not already.
3. Python services:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r services/requirements.txt
   set -a; source .env; set +a
   .venv/bin/python services/phone_server.py   # PHONE_PORT, default 5000
   .venv/bin/python services/mcp_service.py    # MCP_PORT, default 8000
   ```
4. Dashboard: `cd web && npm install && npm run dev` →
   http://localhost:3000. Note: production builds as a **static export**
   (`output: "export"` in `next.config.ts`) because Vercel's bundled Next.js
   adapter wasn't emitting a working serverless function output at build
   time — dev mode is unaffected, this only matters for `vercel --prod`.
5. For a real local call: `ngrok http 5050`, then `POST
   /api/numbers/point` with your ngrok URL + `/voice`. You still need a
   working Vapi assistant + `VAPI_SIP_URI` regardless of local vs deployed,
   since that's where the conversation actually happens.

## Deployment

### Backend (Render)
`render.yaml` defines both services. **Render's GitHub auto-deploy does not
reliably trigger here** — confirmed by checking deploy history via the
Render API: both services sat on their very first commit despite many
subsequent pushes and manual "Sync" clicks in the dashboard. The reliable
way to deploy a new commit is the Render API directly:

```bash
curl -X POST "https://api.render.com/v1/services/<service-id>/deploys" \
  -H "Authorization: Bearer $RENDER_API_KEY" -H "Content-Type: application/json" -d '{}'
```

Get `RENDER_API_KEY` from Render → Account Settings → API Keys. Service ids
are visible in each service's dashboard URL (`srv-...`). Poll
`GET /v1/services/<id>/deploys/<deploy-id>` for `status` until `"live"`.
Env vars can also be set via `PUT /v1/services/<id>/env-vars/<KEY>`, but
setting one does **not** trigger a redeploy on this account either — always
follow up with an explicit deploy call.

### Frontend (Vercel)
```bash
cd web
rm -rf .next out .vercel/output
npm run build
cd out
vercel link --yes --project close-the-loop-dashboard --scope <your-scope>
vercel --prod --yes
```
Deploy from the built `out/` directory, not `web/` directly — see the local
setup note above about the static export. `web/public/vercel.json` sets
`"cleanUrls": true` so routes like `/dashboard` resolve without `.html`.

⚠️ **Be careful with `vercel link`** — it matches existing projects by name.
Always pass an explicit `--project` you know is dedicated to this app; a
name collision with an unrelated project (even one with a custom domain
attached) will silently deploy over it.

### Wiring a1mobile → phone service
```bash
curl -X POST https://hack.a1mobile.com/api/numbers/point -H "X-Team-Key: $TEAM_KEY" \
  -H "Content-Type: application/json" \
  -d '{"webhook_url":"https://close-the-loop-phone.onrender.com/voice"}'
```

## Vapi assistant config

Created and managed via Vapi's REST API (`https://api.vapi.ai`), not the
dashboard UI, using a private API key (Vapi dashboard → API Keys). Key
points if you need to recreate or modify it:

- **Voice:** provider `vapi` (built-in, no external TTS key needed),
  voiceId `Elliot`, version `2`. `Cole` and other legacy voice IDs are
  deprecated and rejected on new assistants — check
  `docs.vapi.ai/providers/voice/vapi-voices` for the current supported list.
- **Model:** `openai` / `gpt-4o-mini`.
- **Tools:** `get_chord_chart`, `advance_section`, and `finish_session`, each
  a `function` tool with its own `server.url` pointing at the phone
  service's `/vapi/*` endpoints (tool-level `server` takes precedence over
  assistant-level). `advance_section` (new — call it with `{"section":
  "verse"|"chorus"}` when the caller moves from the verse to the chorus or
  back) only moves the dashboard's "you are here" highlight; it never hides
  the other section's chords. **Not yet added to the live assistant** — the
  system prompt needs to be told to call it at the same points it currently
  narrates moving on, and remember PATCH replaces `tools` wholesale (see
  below).
  Each has a custom `request-start` message (`"messages": [{"type":
  "request-start", "content": "..."}]`) — **without this, Vapi injects one
  of its own default filler lines** ("Hold on a sec", "One moment", "Just a
  sec", "Give me a moment", "This'll just take a sec") automatically while
  waiting on the tool call, which is where an unwanted "Give me a moment"
  came from before this was set.
- **Transcript webhook:** assistant-level `server.url` = `/vapi/transcript`,
  `serverMessages: ["transcript", "end-of-call-report"]`. Note: the enum
  value is the bare string `"transcript"`, not
  `transcript[transcriptType="final"]` (that variant exists in the OpenAPI
  schema's `type` enum for the *message itself*, but isn't a valid
  dispatch key in `serverMessages` — using it there silently means the
  webhook never fires).
- **⚠️ PATCH replaces `model` wholesale**, not a deep merge. Updating just
  the system prompt via `PATCH /assistant/<id>` with only
  `{"model": {"messages": [...]}}` wipes the `tools` array. Always include
  the full `tools` array in the same request when changing anything under
  `model`.
- **Phone number / SIP address:** created with `provider: "vapi"` and a
  custom `sipUri` (not a real PSTN number — see
  [Known platform issue](#known-platform-issue-a1mobile-speech-gather)).
  `POST /phone-number` requires either `numberDesiredAreaCode` (buys a real
  number) or a custom `sipUri` string.
- **System prompt:** lives only in the live Vapi assistant config (not
  duplicated in this repo to avoid drift — fetch it with `GET
  /assistant/72a2acf3-c1d1-496e-b04b-afeb819bec68` if you need the current
  text). Current behavior: greet → ask song → look up chart → state the
  confidence caveat only if unconfident (no filler phrases) → present verse
  chords slowly, one at a time with pauses → wait for caller to say "ready"
  before counting in → react to what the caller actually says after each
  attempt (encourage, slow down, or move on — never claim to hear their
  playing) → same for chorus → call `finish_session` when done → relay the
  SMS result honestly.

## Operational notes / gotchas

- **Turbopack dev-server cache corruption:** running `rm -rf .next` while
  the Next dev server has it open leaves the server unrecoverable
  (`ENOENT`/"Persisting failed" errors). Fix: stop the preview server, `rm
  -rf web/.next`, then start it fresh — don't delete `.next` while a dev
  server is running against it.
- **a1mobile SMS 403s** for any number that isn't OTP-verified — this is
  the honesty/consent gate, not a bug. Verify via `POST
  /api/verified-numbers` → `POST /api/verified-numbers/confirm`.
- **curl + `+` in phone numbers:** `curl -d "From=+1..."` URL-decodes `+` to
  a space (form-urlencoded semantics), corrupting the number. Use `curl
  --data-urlencode "From=+1..."` instead.
- Render free-tier services cold-start slowly (~30-60s) after ~15min idle —
  the dashboard's wake buttons ping the real endpoint (not a HEAD/timeout
  probe) specifically so clicking them actually wakes the service, not just
  checks it.

## Build status

- [x] Supabase schema (3 tables), Python services, dashboard — all live.
- [x] Phone: real inbound calls work end to end via Vapi bridge; honest SMS
      success and failure paths both verified against the live a1mobile API.
- [x] Coaching flow: seed hit, generate-on-miss, confidence caveats, hard
      spot capture, interactive pacing (waits for "ready", reacts to caller).
- [x] Dashboard: practice log, live-call banner, live transcript, live chord
      chart (step cards), wake/status buttons, logs viewer — all realtime.
- [x] VoiceOS MCP connector: all four tools verified against the live
      Supabase project.
- [x] Every call — completed or not — appears in the practice log, honestly
      labeled either way.
- [ ] Full rehearsed dry run of both demo paths back to back on stage,
      including a deliberate SMS failure.
