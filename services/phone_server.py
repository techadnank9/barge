"""
Guitar coaching voice agent — a1mobile / TeXML webhook server.

Ported from reference-python/phone_server.py (tested reference): only the
practice-log write is changed, from the local JSON file to Supabase via
services/store.py. Everything else — TeXML shape, honest SMS failure branch,
coaching flow — is unchanged.

Flow:  /voice  ->  /handle-song  ->  /handle-turn (loops)  ->  /finish
The call is walkie-talkie (TeXML Gather turns), so we keep per-call state in
a dict keyed by CallSid. The whole point of the build is the honest side
effect: /finish only claims "sent" if the a1mobile SMS API confirms it.

Run:  set -a; source ../.env; set +a; python phone_server.py
Then expose with ngrok and point your number's webhook at https://<host>/voice
"""

import os
import sys
import json
import time
import html
import requests
from collections import deque
from flask import Flask, request, Response, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "reference-python"))
from songs import get_chart  # noqa: E402
from store import add_entry, add_turn  # noqa: E402

app = Flask(__name__)

A1_BASE = "https://hack.a1mobile.com"
TEAM_KEY = os.environ.get("TEAM_KEY", "team-ac4fb03a")
# a1mobile's TeXML <Gather input="speech"> doesn't reliably transcribe on this
# platform (confirmed: real calls return SpeechResult='' / Confidence 0.0 every
# time - not documented anywhere in a1mobile's TeXML guide, which only shows
# input="dtmf"). So the phone surface bridges into a Vapi assistant instead,
# which brings its own STT/TTS/natural voice. Vapi calls back into this
# service via the /vapi/* tool endpoints below for the actual side effects.
VAPI_SIP_URI = os.environ.get("VAPI_SIP_URI", "")

# in-memory per-call state. Fine for a hackathon; resets on restart.
SESSIONS = {}

# in-memory ring buffer of recent events, surfaced at GET /logs for the
# dashboard's log viewer. Resets on restart/redeploy - not persisted.
LOG_BUFFER: deque = deque(maxlen=300)


def log_event(kind: str, message: str) -> None:
    entry = {"ts": time.time(), "kind": kind, "message": message}
    LOG_BUFFER.append(entry)
    print(f"[{kind}] {message}")


# ---------------------------------------------------------------------------
# TeXML helpers
# ---------------------------------------------------------------------------
def texml(body: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{body}</Response>'
    return Response(xml, mimetype="application/xml")


def say(text: str) -> str:
    return f'<Say voice="alice">{html.escape(text)}</Say>'


def sess(call_sid: str) -> dict:
    return SESSIONS.setdefault(call_sid, {"section": "verse", "reps": 0})


def log_turn(call_sid: str, speaker: str, text: str) -> None:
    """
    Best-effort live transcript write. Never lets a logging failure break the
    call — the transcript is a nice-to-have for the dashboard, not something
    the honesty rule depends on.
    """
    try:
        add_turn(call_sid, speaker, text)
    except Exception as e:
        log_event("log_turn_error", f"failed for {call_sid}: {e}")


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
# 1. /voice — answer + bridge straight into the Vapi assistant over SIP.
# Vapi handles all conversation (STT/TTS/LLM); this service only answers
# Vapi's tool-call webhooks below for the actual side effects.
# ---------------------------------------------------------------------------
@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid", "")
    caller = request.form.get("From", "")
    log_event("voice", f"call {call_sid} from {caller}: {dict(request.form)}")
    s = sess(call_sid)
    s["caller"] = caller

    if not VAPI_SIP_URI:
        line = "Sorry, the coach isn't set up right now. Try again later."
        return texml(say(line) + "<Hangup/>")

    return texml(f"<Dial><Sip>{html.escape(VAPI_SIP_URI)}</Sip></Dial>")


# ---------------------------------------------------------------------------
# Vapi tool-call webhooks — the assistant calls these mid-conversation.
# Shape: {"message": {"type": "tool-calls", "toolCallList": [...],
#         "call": {...}, "customer": {"number": "+1..."}}}
# Expected reply: {"results": [{"toolCallId": "...", "result": "..."}]}
# ---------------------------------------------------------------------------
def _vapi_tool_calls(payload: dict) -> list[dict]:
    message = payload.get("message", {})
    calls = message.get("toolCallList") or []
    if not calls:
        # some Vapi versions nest under toolWithToolCallList[].toolCall
        calls = [c.get("toolCall", c) for c in message.get("toolWithToolCallList") or []]
    return calls


def _vapi_args(call: dict) -> dict:
    fn = call.get("function", {})
    args = fn.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, TypeError):
            args = {}
    return args or {}


@app.route("/vapi/get-chord-chart", methods=["POST"])
def vapi_get_chord_chart():
    payload = request.get_json(force=True, silent=True) or {}
    results = []
    for call in _vapi_tool_calls(payload):
        args = _vapi_args(call)
        song = args.get("song", "")
        log_event("vapi-get-chord-chart", f"song={song!r}")
        chart, source = get_chart(song)
        if chart is None:
            result = json.dumps({"found": False, "message": f"Couldn't find or generate chords for {song}."})
        else:
            result = json.dumps({
                "found": True,
                "title": chart["title"],
                "verse": chart.get("verse", []),
                "chorus": chart.get("chorus", []),
                "hard_spots": chart.get("hard_spots", []),
                "confident": chart.get("confident", True),
                "source": source,
            })
        results.append({"toolCallId": call.get("id", ""), "result": result})
    return jsonify({"results": results})


@app.route("/vapi/finish", methods=["POST"])
def vapi_finish():
    """
    The assistant calls this once coaching wraps up. Sends the real SMS and
    only claims success / logs the practice entry if a1mobile confirms the
    send — same honesty rule as the original /finish, just triggered by a
    Vapi tool call instead of a TeXML redirect.
    """
    payload = request.get_json(force=True, silent=True) or {}
    message = payload.get("message", {})
    customer = message.get("customer") or {}
    call_info = message.get("call") or {}
    caller = customer.get("number") or call_info.get("customer", {}).get("number") or ""
    call_sid = call_info.get("id", "")

    results = []
    for call in _vapi_tool_calls(payload):
        args = _vapi_args(call)
        song = args.get("song", "")
        hard_spots = args.get("hard_spots") or []
        confident = args.get("confident", True)
        verse = args.get("verse") or []
        chorus = args.get("chorus") or []
        log_event("vapi-finish", f"call {call_sid} song={song!r} caller={caller!r} hard_spots={hard_spots!r}")

        if not song or not caller:
            result = json.dumps({
                "texted": False,
                "message": "Missing song or caller number - nothing was sent.",
            })
            results.append({"toolCallId": call.get("id", ""), "result": result})
            continue

        chart = {"title": song, "verse": verse, "chorus": chorus,
                 "hard_spots": hard_spots, "confident": confident}
        body = build_sms_text(chart, hard_spots[0] if hard_spots else None)
        ok, detail = send_sms(caller, body)

        if ok:
            add_entry("phone", song, hard_spots, note="coached by phone (vapi)",
                       confident=confident, call_sid=call_sid or None)
            last4 = caller[-4:] if len(caller) >= 4 else caller
            result = json.dumps({
                "texted": True,
                "message": f"Texted the chords to the number ending {last4}.",
            })
        else:
            # THE honest branch. Never claim success the API didn't confirm.
            log_event("vapi-finish", f"SMS failed for call {call_sid} to {caller}: {detail}")
            result = json.dumps({
                "texted": False,
                "message": "The text didn't go through just now. Nothing was sent.",
            })

        results.append({"toolCallId": call.get("id", ""), "result": result})

    return jsonify({"results": results})


# ---------------------------------------------------------------------------
# health check — also doubles as the dashboard's wake/status ping.
# CORS-open since the dashboard (a different origin) polls this directly.
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def health():
    resp = Response("guitar-agent up", mimetype="text/plain")
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# ---------------------------------------------------------------------------
# recent events — for the dashboard's log viewer. CORS-open, in-memory only.
# ---------------------------------------------------------------------------
@app.route("/logs", methods=["GET"])
def logs():
    resp = jsonify(list(LOG_BUFFER))
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    # Render (and most PaaS) inject PORT; fall back to PHONE_PORT for local dev.
    port = int(os.environ.get("PORT", os.environ.get("PHONE_PORT", 5000)))
    app.run(host="0.0.0.0", port=port)
