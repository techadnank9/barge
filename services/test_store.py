"""
Step 1 test (docs/BUILD_PLAN.md): insert one practice entry via services/store.py
and read it back. Requires SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY in the
environment and supabase/schema.sql already applied to the project.

Run:  set -a; source ../.env; set +a; python test_store.py
"""

from store import add_entry, recent_entries

if __name__ == "__main__":
    entry = add_entry("phone", "Wonderwall", ["Em7 to G change"], note="step1 smoke test")
    print("inserted:", entry)

    entries = recent_entries(limit=5)
    print(f"read back {len(entries)} entries, newest first:")
    for e in entries:
        print(" -", e)

    assert entries and entries[0]["song"] == "Wonderwall", "inserted row not found on read-back"
    print("\nSTEP 1 TEST PASSED")
