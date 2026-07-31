# Functional flow

What the agent actually does, with the honesty branches that win the hackathon.

## Phone surface (main build)

### Greeting
Agent answers, greets, asks for a song.

### Song selection (friction point 1)
- Caller names a song → normalize it.
- Seed hit (one of 5 verified songs) → coach from verified data, no LLM.
- Miss → LLM generates a chart with a `confident` flag.
  - `confident: true` → coach normally.
  - `confident: false` → say "this is a common version, I'm not certain it's
    exact" BEFORE coaching. Never state invented chords as fact.
- Couldn't find or generate → offer the seed songs by name. Do not pretend.
- Mumbled / silent → re-ask.

### Coached practice loop
Agent leads the practice by voice: names the section, counts in, calls the
changes, corrects TIMING and DELIVERY ("you're rushing, hold the Em7 a beat
longer, land G on 'today'"). It does NOT claim to hear the strings — phone audio
can't reliably detect chords, and a wrong "you played G" reads as fabrication.
Captures any spot the caller flags as hard.

### Confirm destination (friction point 2)
Use the caller ID; read back the last four digits. Only ask for a number if
caller ID is withheld or they want the text elsewhere.

### Attempt SMS + honest report (the deciding step)
- Send via a1mobile.
- API 200 → insert practice entry (source `phone`), say "texted you, ending
  XXXX."
- Any failure → say "the message didn't go through, nothing was sent." Never
  claim success. Offer to retry or note the number may need verifying.

## VoiceOS surface (bonus build)

### Voice command
User speaks a request, e.g. "log my Wonderwall practice, I struggled with the
Em7 to G change" or "get me the chords for Three Little Birds."

### Tool routing
VoiceOS maps the utterance to one of the connector's tools:
- `get_chord_chart(song)` → reads the brain, returns chords (with `confident`).
- `log_practice(song, hard_spots)` → the side-effecting tool.
- `schedule_practice(song, when)` → records a follow-up.
- `recent_practices()` → reads back the log.

### Confirm before acting
VoiceOS shows a confirm card for anything that writes. User approves.

### Side effect + live dashboard
The tool inserts into Supabase. The dashboard, subscribed to inserts, renders
the new row within a second, tagged `voiceos`. That visible append is the
confirmable side effect — not "an MCP was called," an actual row landing.

## The honesty branches, summarized
| Surface | Success says | Failure says |
|--------|--------------|--------------|
| Phone  | "texted you, ending XXXX" (only on API 200) | "nothing was sent" |
| VoiceOS| tool returns logged + row appears | tool returns an error, agent relays it |

Build each failure branch before its success branch. The judges test friction
(first option unavailable, payment fails, ambiguous request) — the agent that
adapts and stays honest wins.
