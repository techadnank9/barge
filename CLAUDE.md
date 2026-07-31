# CLAUDE.md — read this first

You are building **Close the Loop**, a voice-AI hackathon project. A guitar
coaching agent that works over two surfaces and produces verifiable side
effects. This file tells you the stack, the rules, and the exact order to build
in. Build one feature, test it, then move to the next. Do not build everything
at once.

## What this project is
A guitar coach the user talks to:
- **Phone (main):** user calls a real number, the agent coaches them through a
  song by voice, then texts them the chords. The SMS is the verifiable side
  effect.
- **VoiceOS (bonus):** a custom MCP connector the desktop app VoiceOS drives by
  voice. "Log my practice" writes a row that appears live on a dashboard. That
  visible write is the verifiable side effect.

Both surfaces share one coaching brain and one practice log.

## The one rule that cannot be broken
**Never claim a side effect that did not happen.** The agent says "texted you"
ONLY when the SMS API returns success. It says "logged" ONLY when the write
succeeded. On failure it says so plainly. In this hackathon a fabricated success
is an automatic disqualifying flag; an honest "I couldn't do that" scores better
than a confident lie. Build the failure/honesty path FIRST for each feature, not
last.

## Stack (decided — do not change without asking)
- **Voice services: Python.** The phone webhook (Flask) and the VoiceOS MCP
  connector (fastmcp). These are the scoring parts and there is proven, tested
  reference code in `reference-python/`. Reuse it. Do not rewrite these in
  TypeScript.
- **Dashboard + persistence: Next.js (App Router) + Supabase.** The dashboard is
  what judges watch; Supabase gives realtime so rows appear the instant a tool
  fires. Practice entries live in a Supabase table both Python services write to.
- **Why split:** each half uses the right tool. Python where working code and
  every MCP reference already exist; Next.js/Supabase where realtime UI and
  persistence matter. They communicate only through Supabase.

## reference-python/ — proven, reuse it
These files are already written and TESTED (phone flow + all four MCP tools
passed). Treat them as the source of truth for the voice logic:
- `songs.py` — 5 verified seed songs + generate-on-miss with a `confident` flag.
  The shared coaching brain. Use as-is.
- `phone_server.py` — Flask TeXML endpoints. Port the SMS write to go to
  Supabase instead of a local JSON file, keep everything else.
- `mcp_connector.py` — fastmcp connector, four tools. Port the writes to
  Supabase; keep the tool shapes.
- `practice_store.py` — the local-file store. REPLACE this with a Supabase
  client in both services. It shows the interface you need to preserve.
- `verify_number.py` — a1mobile OTP verification. Use as-is.

The known gotchas already solved in that code: TeXML must return
`application/xml`; a1mobile SMS only sends to OTP-verified numbers; fastmcp 3.x
tools are called as plain functions; the honest-failure branch in `/finish`.

## Build order — one feature at a time, test gate after each
Do these IN ORDER. After each, run the test in `docs/BUILD_PLAN.md` and confirm
it passes before moving on. Commit after each green step.

1. **Supabase + schema.** Stand up the project, apply `supabase/schema.sql`,
   confirm you can insert and read a practice entry from a script.
2. **Phone: answer + honest SMS failure.** Port `phone_server.py`. Prove the
   `/finish` honest-failure path first (unverified number → "nothing sent").
   THEN make a real verified send work.
3. **Phone: full coaching flow.** Song selection (seed hit + generate-on-miss),
   the coached turn loop, hard-spot capture.
4. **Dashboard (Next.js + Supabase realtime).** A row appears live when a
   practice entry is inserted. Test by inserting a row by hand.
5. **VoiceOS MCP connector.** Port `mcp_connector.py`, writes go to Supabase.
   Confirm an MCP client can list + call the tools, and the dashboard updates.
6. **End-to-end + polish.** Both surfaces write to the same dashboard. Rehearse.

Do NOT start feature N+1 until feature N's test passes. If a step fails, fix it
before moving on. Ship a working feature 2 over a broken feature 5.

## Docs in this repo
- `docs/ARCHITECTURE.md` — technical architecture, how the pieces connect.
- `docs/FUNCTIONAL_FLOW.md` — what the agent does, step by step, with the
  honesty branches.
- `docs/BUILD_PLAN.md` — the phased plan with the exact test for each step.
- `docs/API_REFERENCE.md` — a1mobile endpoints, VoiceOS Add-dialog values.
- `README.md` — human setup instructions.

## Secrets
Never hardcode keys. Everything comes from env vars / `.env` (see
`.env.example`). If a key was pasted anywhere, treat it as compromised and tell
the user to rotate it.
