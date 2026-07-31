"""
Custom VoiceOS MCP connector — guitar coaching tools, driven by voice.

This is the "Best on VoiceOS" build: a purpose-built MCP server, not a
turned-on off-the-shelf connector. It reuses the SAME coaching brain as the
phone agent (songs.get_chart) so there's one source of truth.

Tools:
  get_chord_chart(song)          -> chords VoiceOS can read aloud
  log_practice(song, hard_spots) -> THE side effect: writes to the shared store
                                     (the live dashboard shows it land)
  schedule_practice(song, when)  -> records a follow-up in the same store
  recent_practices()             -> read back what's been logged

Run:   python mcp_connector.py         (serves MCP over streamable HTTP at /mcp/)
Add to VoiceOS:  voiceos add mcp  ->  point it at http://localhost:8000/mcp/

VoiceOS confirms before it acts, so a spoken "log my Wonderwall practice" shows
a confirm card first; on approve, log_practice fires and the dashboard updates.
"""

import os
from fastmcp import FastMCP

from songs import get_chart
from practice_store import add_entry, all_entries

mcp = FastMCP("guitar-coach")


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
    entry = add_entry("voiceos", song, hard_spots or [], note)
    return {"logged": True, "entry": entry,
            "message": f"Logged practice for {song}."}


@mcp.tool
def schedule_practice(song: str, when: str) -> dict:
    """Record a follow-up practice session (e.g. 'Thursday 6pm') in the log."""
    entry = add_entry("voiceos", song, [], note=f"scheduled: {when}")
    return {"scheduled": True, "entry": entry,
            "message": f"Follow-up for {song} noted for {when}."}


@mcp.tool
def recent_practices(limit: int = 5) -> dict:
    """Read back the most recent practice entries."""
    entries = all_entries()[-limit:]
    return {"count": len(entries), "entries": entries}


if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", 8000))
    # streamable HTTP transport, mounted at /mcp/ (keep the trailing slash when adding to VoiceOS)
    mcp.run(transport="http", host="127.0.0.1", port=port)
