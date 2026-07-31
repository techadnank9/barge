# Close the Loop — guitar coaching voice agent

A voice agent that coaches guitar over two surfaces and produces verifiable side
effects:
- **Phone (main):** call a real number, get coached through a song, receive the
  chords by SMS. The text is the confirmable result.
- **VoiceOS (bonus):** a custom MCP connector VoiceOS drives by voice; "log my
  practice" writes a row that appears live on a dashboard.

Both share one coaching brain and one practice log (Supabase).

## For Claude Code
Read `CLAUDE.md` first. It has the stack, the rules, and the build order. Build
one feature at a time and run the test in `docs/BUILD_PLAN.md` after each before
moving on.

## Stack
- **Voice services:** Python — Flask (phone TeXML webhook) + fastmcp (VoiceOS MCP
  connector). Proven, tested reference in `reference-python/`.
- **Dashboard + persistence:** Next.js (App Router) + Supabase (realtime).
- They communicate only through the Supabase `practice_entries` table.

## Layout
```
CLAUDE.md              instructions for Claude Code (read first)
README.md              this file
.env.example           all secrets/config (copy to .env)
docs/
  ARCHITECTURE.md      how the pieces connect
  FUNCTIONAL_FLOW.md   what the agent does + honesty branches
  BUILD_PLAN.md        phased build with a test gate per step
  API_REFERENCE.md     a1mobile endpoints + VoiceOS Add-dialog values
supabase/
  schema.sql           the one shared table
reference-python/      TESTED voice logic — reuse, port storage to Supabase
  songs.py             coaching brain (5 seed songs + generate-on-miss)
  phone_server.py      Flask TeXML endpoints
  mcp_connector.py     fastmcp connector, four tools
  practice_store.py    local-file store (replace with Supabase)
  verify_number.py     a1mobile OTP verification
services/              (Claude Code builds) Python services wired to Supabase
web/                   (Claude Code builds) Next.js + Supabase dashboard
```

## The one rule
Never claim a side effect that didn't happen. The agent says "texted you" only
on an SMS API success, "logged" only on a successful write. On failure it says
so. A fabricated success is an automatic disqualifying flag. Build the honesty
path first.

## Quick start (after Claude Code builds it out)
1. `cp .env.example .env` and fill in TEAM_KEY, OPENAI_API_KEY, Supabase keys.
2. Apply `supabase/schema.sql` in your Supabase project.
3. Python services: `pip install -r reference-python/requirements.txt`, then run
   the phone service and the MCP service.
4. Dashboard: `cd web && npm install && npm run dev`.
5. Expose the phone webhook with ngrok, point your a1mobile number at it.
6. Add the MCP connector to VoiceOS by URL (`http://localhost:8000/mcp/`).

Full demo steps live in `docs/BUILD_PLAN.md` and `docs/API_REFERENCE.md`.
