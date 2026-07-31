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
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "reference-python"))
from songs import get_chart  # noqa: E402
from store import add_entry, recent_entries  # noqa: E402

mcp = FastMCP("guitar-coach")


# Health check — also doubles as the dashboard's wake/status ping. CORS-open
# since the dashboard (a different origin) polls this directly.
@mcp.custom_route("/", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("mcp-service up", headers={"Access-Control-Allow-Origin": "*"})


@mcp.tool
def get_chord_chart(song: str) -> dict:
    """Get the chord chart for a song so it can be read aloud. Returns the
    chords plus a `confident` flag — if false, the chords are a common version,
    not guaranteed exact for this specific song."""
    chart, source = get_chart(song)
    if chart is None:
        return {"found": False, "message": f"Couldn't find or generate chords for {song}."}
    return {
        "found": True,
        "title": chart["title"],
        "verse": chart.get("verse", []),
        "chorus": chart.get("chorus", []),
        "hard_spots": chart.get("hard_spots", []),
        "confident": chart.get("confident", True),
        "source": source,  # 'seed' (verified) or 'generated'
    }


@mcp.tool
def log_practice(song: str, hard_spots: list[str] | None = None, note: str = "") -> dict:
    """Log a completed practice session. This writes a real, visible entry to
    the practice log — the confirmable side effect. Pass the song and any parts
    the player found hard."""
    try:
        entry = add_entry("voiceos", song, hard_spots or [], note)
    except Exception as e:
        # honesty rule: never claim a log happened if the write didn't succeed
        return {"logged": False, "message": f"Couldn't log this practice: {e}"}
    return {"logged": True, "entry": entry,
            "message": f"Logged practice for {song}."}


@mcp.tool
def schedule_practice(song: str, when: str) -> dict:
    """Record a follow-up practice session (e.g. 'Thursday 6pm') in the log."""
    try:
        entry = add_entry("voiceos", song, [], note=f"scheduled: {when}")
    except Exception as e:
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
