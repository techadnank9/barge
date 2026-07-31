# API reference

## a1mobile (from the participant guides)

Base: `https://hack.a1mobile.com` · Auth header: `X-Team-Key: <TEAM_KEY>`

| Purpose | Method + path | Body |
|--------|---------------|------|
| Claim number | POST `/api/numbers/claim` | — (returns phone_number, sip creds) |
| Point webhook | POST `/api/numbers/point` | `{"webhook_url":"https://.../voice"}` |
| Send SMS | POST `/api/sms` | `{"to":"+1...","body":"..."}` |
| Request OTP | POST `/api/verified-numbers` | `{"phone":"+1..."}` |
| Confirm OTP | POST `/api/verified-numbers/confirm` | `{"phone":"+1...","code":"..."}` |

Rules:
- SMS only delivers to OTP-verified numbers or organizer test lines. Else 403.
- Webhook must return `application/xml` with a `<Response>` root, fast.
- Judging is a live demo; a fabricated success is an automatic critical flag.

### TeXML verbs you use
- `<Say voice="alice">text</Say>` — text to speech.
- `<Gather input="speech" speechTimeout="auto" action="/next" method="POST">…</Gather>`
  — capture speech, POST `SpeechResult` to action.
- `<Redirect method="POST">/path</Redirect>` — jump to another endpoint.
- `<Hangup/>` — end the call.

### Optional: a1mobile AI gateway (saves LLM budget)
- `OPENAI_BASE_URL=https://hack.a1mobile.com/gw/v1`, model `openai.gpt-5.6-sol`.
- $50 shared allowance. Non-streaming (fine for turn-based; laggy for realtime).

### a1mobile MCP (alternative to REST)
- `https://hack.a1mobile.com/mcp/` (keep trailing slash). Tools:
  `claim_number`, `point_number`, `send_confirmation_sms`,
  `request_number_verification`, `confirm_number_verification`. Pass `team_key`.

## VoiceOS — adding the custom MCP connector

VoiceOS → Agent → Integrations → Create → Custom MCP → **+ Add**.

Two tabs:
- **URL (use this):** connects to a running HTTP MCP server.
  - Name: `Guitar Coach`
  - Server URL: `http://localhost:8000/mcp/` (keep trailing slash)
  - Authorization: leave blank (local, open)
  - Connect.
- **Command:** launches a stdio server (`npx tsc /path/to/server.ts` style). Not
  needed for our HTTP server; fallback only.

Tips:
- Click "Try example" first to confirm the connect mechanism works on the
  machine, before your own server is involved.
- If URL mode refuses localhost, expose with `ngrok http 8000` and use the https
  URL.
- VoiceOS confirms before any write, so a spoken write shows a confirm card.

## Supabase
- One table `practice_entries` (see `supabase/schema.sql`).
- Python services use the service-role key (server-side only).
- The dashboard uses the anon key + realtime subscription to inserts.
- Never expose the service-role key to the browser.
