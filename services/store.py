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

# from supabase import create_client, Client
#
# _client: "Client" = create_client(
#     os.environ["SUPABASE_URL"],
#     os.environ["SUPABASE_SERVICE_ROLE_KEY"],
# )


def add_entry(source: str, song: str, hard_spots=None, note: str = "",
              confident: bool = True) -> dict:
    """
    Insert one practice entry and return the created row.
    `source` is 'phone' or 'voiceos'. Must succeed or raise - callers rely on
    this to decide whether to claim success to the user (the honesty rule).

    Implement:
        row = {
            "source": source, "song": song,
            "hard_spots": hard_spots or [], "note": note,
            "confident": confident,
        }
        res = _client.table("practice_entries").insert(row).execute()
        return res.data[0]
    """
    raise NotImplementedError("Claude Code: implement against supabase-py")


def recent_entries(limit: int = 5) -> list[dict]:
    """
    Return the most recent entries, newest first.

    Implement:
        res = (_client.table("practice_entries")
               .select("*").order("created_at", desc=True)
               .limit(limit).execute())
        return res.data
    """
    raise NotImplementedError("Claude Code: implement against supabase-py")
