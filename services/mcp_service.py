"""
Custom VoiceOS MCP connector — guitar coaching tools, driven by voice.

Ported from reference-python/mcp_connector.py (tested reference): only the
practice-log write is changed, from the local JSON file to Supabase via
services/store.py. Tool shapes are unchanged.

Tools:
  get_chord_chart(song)          -> chords VoiceOS can read aloud
  log_practice(song, hard_spots) -> THE side effect: writes to the shared store
                                     (the live dashboard shows it land)
  schedule_practice(song, when)  -> records a follow-up in the same store
  recent_practices()             -> read back what's been logged

Run:   set -a; source ../.env; set +a; python mcp_service.py
Serves MCP over streamable HTTP at /mcp/.
Add to VoiceOS:  voiceos add mcp  ->  point it at http://localhost:8000/mcp/

VoiceOS confirms before it acts, so a spoken "log my Wonderwall practice" shows
a confirm card first; on approve, log_practice fires and the dashboard updates.
"""

import os
import sys
import time
import uuid
from collections import deque
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse, JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "reference-python"))
from songs import get_chart  # noqa: E402
from store import add_entry, recent_entries, set_call_chart, advance_call_section  # noqa: E402

mcp = FastMCP("guitar-coach")

# in-memory ring buffer of recent tool calls, surfaced at GET /logs for the
# dashboard's log viewer. Resets on restart/redeploy - not persisted.
LOG_BUFFER: deque = deque(maxlen=300)


def log_event(kind: str, message: str) -> None:
    LOG_BUFFER.append({"ts": time.time(), "kind": kind, "message": message})
    print(f"[{kind}] {message}")


# Health check — also doubles as the dashboard's wake/status ping. CORS-open
# since the dashboard (a different origin) polls this directly.
@mcp.custom_route("/", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("mcp-service up", headers={"Access-Control-Allow-Origin": "*"})


@mcp.custom_route("/logs", methods=["GET"])
async def logs(request: Request) -> JSONResponse:
    return JSONResponse(list(LOG_BUFFER), headers={"Access-Control-Allow-Origin": "*"})


@mcp.tool
def get_chord_chart(song: str) -> dict:
    """Get the chord chart for a song so it can be read aloud. Returns the
    chords plus a `confident` flag — if false, the chords are a common version,
    not guaranteed exact for this specific song, so say so before coaching it.
    Also returns a `session_id` — pass that same value to advance_section as
    you move the player from the verse to the chorus (and back), and pass the
    `confident` flag through to log_practice when the session ends, so the
    dashboard's "unverified chords" badge is accurate for generated songs
    too."""
    log_event("get_chord_chart", f"song={song!r}")
    chart, source = get_chart(song)
    if chart is None:
        return {"found": False, "message": f"Couldn't find or generate chords for {song}."}

    session_id = uuid.uuid4().hex[:8]
    try:
        set_call_chart(
            f"voiceos-{session_id}", chart["title"],
            chart.get("verse", []), chart.get("chorus", []),
            chart.get("hard_spots", []), chart.get("confident", True),
        )
    except Exception as e:
        log_event("get_chord_chart-error", f"set_call_chart failed for {session_id}: {e}")

    return {
        "found": True,
        "title": chart["title"],
        "verse": chart.get("verse", []),
        "chorus": chart.get("chorus", []),
        "hard_spots": chart.get("hard_spots", []),
        "confident": chart.get("confident", True),
        "source": source,  # 'seed' (verified) or 'generated'
        "session_id": session_id,
    }


@mcp.tool
def advance_section(session_id: str, section: str) -> dict:
    """Mark which section (verse or chorus) is currently being coached, using
    the session_id returned by get_chord_chart, so the live dashboard
    highlights it. Call this once right when you move the player from the
    verse to the chorus, and again if you go back to the verse for a repeat.
    Doesn't change what chords exist, only which one is highlighted."""
    log_event("advance_section", f"session_id={session_id!r} section={section!r}")
    if section not in ("verse", "chorus"):
        return {"advanced": False, "message": "section must be 'verse' or 'chorus'."}
    try:
        advance_call_section(f"voiceos-{session_id}", section)
    except Exception as e:
        log_event("advance_section_error", f"session_id={session_id!r}: {e}")
        return {"advanced": False, "message": f"Couldn't update section: {e}"}
    return {"advanced": True}


@mcp.tool
def log_practice(song: str, hard_spots: list[str] | None = None, note: str = "",
                  confident: bool = True) -> dict:
    """Log a completed practice session. This writes a real, visible entry to
    the practice log — the confirmable side effect. Pass the song, any parts
    the player found hard, and the `confident` flag from get_chord_chart's
    result for this song (false if the chords were generated/uncertain rather
    than a verified seed song) — never leave it defaulted to true for a song
    you weren't actually sure about."""
    log_event("log_practice", f"song={song!r} hard_spots={hard_spots!r} confident={confident!r}")
    try:
        entry = add_entry("voiceos", song, hard_spots or [], note, confident=confident)
    except Exception as e:
        # honesty rule: never claim a log happened if the write didn't succeed
        log_event("log_practice_error", f"song={song!r}: {e}")
        return {"logged": False, "message": f"Couldn't log this practice: {e}"}
    return {"logged": True, "entry": entry,
            "message": f"Logged practice for {song}."}


@mcp.tool
def schedule_practice(song: str, when: str) -> dict:
    """Record a follow-up practice session (e.g. 'Thursday 6pm') in the log."""
    log_event("schedule_practice", f"song={song!r} when={when!r}")
    try:
        entry = add_entry("voiceos", song, [], note=f"scheduled: {when}")
    except Exception as e:
        log_event("schedule_practice_error", f"song={song!r}: {e}")
        return {"scheduled": False, "message": f"Couldn't schedule this: {e}"}
    return {"scheduled": True, "entry": entry,
            "message": f"Follow-up for {song} noted for {when}."}


@mcp.tool
def recent_practices(limit: int = 5) -> dict:
    """Read back the most recent practice entries."""
    entries = recent_entries(limit)
    return {"count": len(entries), "entries": entries}


if __name__ == "__main__":
    # Render (and most PaaS) inject PORT; fall back to MCP_PORT for local dev.
    port = int(os.environ.get("PORT", os.environ.get("MCP_PORT", 8000)))
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    # streamable HTTP transport, mounted at /mcp/ (keep the trailing slash when adding to VoiceOS)
    mcp.run(transport="http", host=host, port=port)
