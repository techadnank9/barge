"""
Shared practice store. Both surfaces write here:
  - the a1mobile phone agent (after a coached call)
  - the VoiceOS MCP connector (when log_practice is called by voice)

Deliberately a plain JSON file with a file lock - no database to stand up at
the event, and the dashboard just polls it. Append-only so the judge sees the
log grow, never shrink.
"""

import os
import json
import time
import threading

STORE_PATH = os.environ.get("PRACTICE_STORE", os.path.join(os.path.dirname(__file__), "practice_log.json"))
_lock = threading.Lock()


def _read_raw():
    if not os.path.exists(STORE_PATH):
        return []
    try:
        with open(STORE_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []


def add_entry(source: str, song: str, hard_spots=None, note: str = "") -> dict:
    """
    Append one practice entry and return it. `source` is 'phone' or 'voiceos'
    so the dashboard can show which surface logged it.
    """
    entry = {
        "id": int(time.time() * 1000),
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "song": song,
        "hard_spots": hard_spots or [],
        "note": note,
    }
    with _lock:
        data = _read_raw()
        data.append(entry)
        tmp = STORE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, STORE_PATH)  # atomic, so the dashboard never reads a half-written file
    return entry


def all_entries():
    with _lock:
        return _read_raw()


if __name__ == "__main__":
    print(add_entry("voiceos", "Wonderwall", ["Em7 to G change"], "logged by voice"))
    print(f"{len(all_entries())} entries in {STORE_PATH}")
