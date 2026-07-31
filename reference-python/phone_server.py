"""
Guitar coaching voice agent — a1mobile / TeXML webhook server.

Flow:  /voice  ->  /handle-song  ->  /handle-turn (loops)  ->  /finish
The call is walkie-talkie (TeXML Gather turns), so we keep per-call state in
a dict keyed by CallSid. The whole point of the build is the honest side
effect: /finish only claims "sent" if the a1mobile SMS API confirms it.

Run:  OPENAI_API_KEY=... TEAM_KEY=... python server.py
Then expose with ngrok and point your number's webhook at https://<host>/voice
"""

import os
import html
import requests
from flask import Flask, request, Response

from songs import get_chart
from practice_store import add_entry

app = Flask(__name__)

A1_BASE = "https://hack.a1mobile.com"
TEAM_KEY = os.environ.get("TEAM_KEY", "team-ac4fb03a")

# in-memory per-call state. Fine for a hackathon; resets on restart.
SESSIONS = {}


# ---------------------------------------------------------------------------
# TeXML helpers
# ---------------------------------------------------------------------------
def texml(body: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{body}</Response>'
    return Response(xml, mimetype="application/xml")


def say(text: str) -> str:
    return f'<Say voice="alice">{html.escape(text)}</Say>'


def gather(prompt: str, action: str) -> str:
    """Speak a prompt, then listen for the caller's speech and POST it to action."""
    return (
        f'<Gather input="speech" speechTimeout="auto" '
        f'action="{action}" method="POST">{say(prompt)}</Gather>'
        # if they stay silent, loop back so the call doesn't dead-air
        f'<Redirect method="POST">{action}</Redirect>'
    )


def sess(call_sid: str) -> dict:
    return SESSIONS.setdefault(call_sid, {"section": "verse", "reps": 0})


# ---------------------------------------------------------------------------
# a1mobile SMS — the verifiable side effect
# ---------------------------------------------------------------------------
def send_sms(to_number: str, body: str) -> tuple[bool, str]:
    """Returns (ok, detail). ok=True ONLY if a1mobile confirms the send."""
    try:
        r = requests.post(
            f"{A1_BASE}/api/sms",
            headers={"X-Team-Key": TEAM_KEY, "Content-Type": "application/json"},
            json={"to": to_number, "body": body},
            timeout=10,
        )
        if r.status_code == 200:
            return True, "delivered"
        return False, f"status {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return False, f"exception: {e}"


def build_sms_text(chart: dict, hard_spot: str | None) -> str:
    lines = [f"Nice work on {chart['title']}! Your practice sheet:"]
    if chart.get("verse"):
        lines.append("Verse: " + "  ".join(chart["verse"]))
    if chart.get("chorus"):
        lines.append("Chorus: " + "  ".join(chart["chorus"]))
    if hard_spot:
        lines.append(f"Focus on: {hard_spot}")
    elif chart.get("hard_spots"):
        lines.append("Focus on: " + chart["hard_spots"][0])
    if not chart.get("confident", True):
        lines.append("(Double-check these chords - I wasn't 100% sure of the exact version.)")
    lines.append("Call back anytime to run it again.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 1. /voice — answer + greet + ask for the song
# ---------------------------------------------------------------------------
@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid", "")
    caller = request.form.get("From", "")
    s = sess(call_sid)
    s["caller"] = caller
    greeting = (
        "Hi! I'm your guitar coach. Tell me a song you want to play and sing, "
        "and I'll walk you through it. Which song?"
    )
    return texml(gather(greeting, "/handle-song"))


# ---------------------------------------------------------------------------
# 2. /handle-song — resolve the chart (seed hit or generate), honest on miss
# ---------------------------------------------------------------------------
@app.route("/handle-song", methods=["POST"])
def handle_song():
    call_sid = request.form.get("CallSid", "")
    s = sess(call_sid)
    heard = (request.form.get("SpeechResult") or "").strip()

    if not heard:
        return texml(gather("Sorry, I didn't catch that. What song?", "/handle-song"))

    chart, source = get_chart(heard)

    if chart is None:
        # honest failure: couldn't find or generate. Offer a seeded fallback.
        return texml(gather(
            f"I couldn't find chords for {heard}. I know Wonderwall, Let It Be, "
            "and Three Little Birds well. Want one of those, or another song?",
            "/handle-song",
        ))

    s["chart"] = chart
    s["source"] = source
    s["section"] = "verse"
    s["reps"] = 0

    first = chart["verse"][0] if chart["verse"] else (chart["chorus"][0] if chart["chorus"] else "the first chord")
    intro = f"Great, {chart['title']}. "
    if not chart.get("confident", True):
        # source == generated and unsure: say so BEFORE coaching invented chords
        intro += ("I'm not fully certain of the exact chords for this one, so treat "
                  "this as a common version. ")
    intro += (f"We'll start with the verse. First chord is {first}. "
              "Put your fingers there, and say ready when you want me to count you in.")
    return texml(gather(intro, "/handle-turn"))


# ---------------------------------------------------------------------------
# 3. /handle-turn — the coached practice loop (timing + delivery, never notes)
# ---------------------------------------------------------------------------
@app.route("/handle-turn", methods=["POST"])
def handle_turn():
    call_sid = request.form.get("CallSid", "")
    s = sess(call_sid)
    heard = (request.form.get("SpeechResult") or "").lower()
    chart = s.get("chart")

    if not chart:
        return texml(gather("Let's pick a song first. Which one?", "/handle-song"))

    # caller wants to wrap up -> go send the text
    if any(w in heard for w in ("done", "finish", "that's it", "text me", "send")):
        return texml(f'<Redirect method="POST">/finish</Redirect>')

    # caller flags a hard spot -> remember it for the SMS
    if any(w in heard for w in ("hard", "fast", "struggl", "again", "messed", "off")):
        s["hard_spot"] = f"{s['section']}: {chart.get('hard_spots', ['this change'])[0] if chart.get('hard_spots') else 'the tricky change'}"

    section = s["section"]
    chords = chart.get(section) or chart.get("verse") or []
    s["reps"] += 1

    # count them in and call the changes for the current section
    progression = " then ".join(chords) if chords else "the chords"
    line = (f"Okay, {section}. Count of four - one, two, three, four. "
            f"Play {progression}. Keep the strum steady and change on the beat.")

    # after a couple reps of the verse, move to the chorus, then offer to finish
    if section == "verse" and s["reps"] >= 2 and chart.get("chorus"):
        s["section"] = "chorus"
        s["reps"] = 0
        line += " Nice. Now let's try the chorus. Say ready."
    elif s["reps"] >= 2:
        line += (" You're getting it. Say 'done' and I'll text you the chords, "
                 "or 'again' to run it once more.")
    else:
        line += " Give it a go, then say 'again' or 'next'."

    return texml(gather(line, "/handle-turn"))


# ---------------------------------------------------------------------------
# 4. /finish — confirm number, fire the real SMS, report HONESTLY
# ---------------------------------------------------------------------------
@app.route("/finish", methods=["POST"])
def finish():
    call_sid = request.form.get("CallSid", "")
    s = sess(call_sid)
    chart = s.get("chart")
    caller = s.get("caller", "")

    if not chart:
        return texml(say("We didn't get to a song this time. Call back anytime!") + "<Hangup/>")

    body = build_sms_text(chart, s.get("hard_spot"))
    ok, detail = send_sms(caller, body)

    if ok:
        # phone surface also feeds the shared practice log / dashboard
        hard = [s["hard_spot"]] if s.get("hard_spot") else chart.get("hard_spots", [])
        add_entry("phone", chart["title"], hard, note="coached by phone")
        last4 = caller[-4:] if len(caller) >= 4 else caller
        msg = (f"Done! I've texted the chords for {chart['title']} to the number "
               f"ending {last4}. Check your messages. Keep practicing!")
    else:
        # THE honest branch. Never claim success the API didn't confirm.
        print(f"[finish] SMS failed for {caller}: {detail}")
        msg = ("I tried to text you the chords but the message didn't go through "
               "just now. Nothing was sent. You may need to verify your number "
               "first, or try calling back. Sorry about that!")

    return texml(say(msg) + "<Hangup/>")


# ---------------------------------------------------------------------------
# health check
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def health():
    return "guitar-agent up", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
