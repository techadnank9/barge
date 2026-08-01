"""
services/store.py — the Supabase seam.

This REPLACES reference-python/practice_store.py. Both voice services import
add_entry / recent_entries from here. Same interface as the reference file, but
writes to Supabase instead of a local JSON file, so the dashboard sees inserts
in realtime.

Claude Code: implement the two functions against supabase-py. Keep the
signatures identical to the reference so phone_server.py and mcp_connector.py
need no other changes.

Requires: pip install supabase
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  (service role - server side only)
"""

import os

from supabase import create_client, Client

_client: "Client" = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)


def add_entry(source: str, song: str, hard_spots=None, note: str = "",
              confident: bool = True, call_sid: str | None = None) -> dict:
    """
    Insert one practice entry and return the created row.
    `source` is 'phone' or 'voiceos'. Must succeed or raise - callers rely on
    this to decide whether to claim success to the user (the honesty rule).
    `call_sid` links a phone entry to its call_turns transcript; left null
    for voiceos entries (no phone call to transcribe).
    """
    row = {
        "source": source, "song": song,
        "hard_spots": hard_spots or [], "note": note,
        "confident": confident, "call_sid": call_sid,
    }
    res = _client.table("practice_entries").insert(row).execute()
    return res.data[0]


def recent_entries(limit: int = 5) -> list[dict]:
    """Return the most recent entries, newest first."""
    res = (_client.table("practice_entries")
           .select("*").order("created_at", desc=True)
           .limit(limit).execute())
    return res.data


def add_turn(call_sid: str, speaker: str, text: str) -> dict:
    """
    Log one turn of a phone call transcript. `speaker` is 'caller' or 'agent'.
    Best-effort: the live transcript is a nice-to-have, never lets a logging
    failure break the call, so callers should wrap this in try/except.
    """
    row = {"call_sid": call_sid, "speaker": speaker, "text": text}
    res = _client.table("call_turns").insert(row).execute()
    return res.data[0]


def has_turns(call_sid: str) -> bool:
    """Whether any turns are already logged for this call."""
    res = (_client.table("call_turns").select("id")
           .eq("call_sid", call_sid).limit(1).execute())
    return bool(res.data)


def set_call_chart(call_sid: str, song: str, verse=None, chorus=None,
                    hard_spots=None, confident: bool = True,
                    current_section: str = "verse") -> dict:
    """
    Upsert the chord chart currently being coached on a call, so the
    dashboard can show "what to press" live alongside the transcript.
    """
    row = {
        "call_sid": call_sid, "song": song,
        "verse": verse or [], "chorus": chorus or [],
        "hard_spots": hard_spots or [], "confident": confident,
        "current_section": current_section,
    }
    res = _client.table("call_charts").upsert(row, on_conflict="call_sid").execute()
    return res.data[0]


def advance_call_section(call_sid: str, section: str) -> dict:
    """
    Move the "you are here" marker on the current call's chord chart, e.g.
    when the caller finishes the verse and moves to the chorus. Doesn't
    touch verse/chorus/hard_spots - both stay visible, only the highlight
    moves. Raises if no chart row exists yet for this call.
    """
    res = (_client.table("call_charts")
           .update({"current_section": section})
           .eq("call_sid", call_sid).execute())
    return res.data[0]


def get_call_chart(call_sid: str) -> dict | None:
    """The chart last looked up on this call, if any."""
    res = (_client.table("call_charts").select("*")
           .eq("call_sid", call_sid).limit(1).execute())
    return res.data[0] if res.data else None


def has_entry_for_call(call_sid: str) -> bool:
    """Whether a practice_entries row already exists for this call."""
    res = (_client.table("practice_entries").select("id")
           .eq("call_sid", call_sid).limit(1).execute())
    return bool(res.data)
