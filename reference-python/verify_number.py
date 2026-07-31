"""
Verify a phone number so a1mobile will let you text it (consent gate).
Run this ONCE for each number you'll demo with, before the call.

  TEAM_KEY=team-... python verify_number.py +1XXXXXXXXXX

It requests an OTP, waits for you to type the code you receive, confirms it,
then that number is allowed to receive SMS from your claimed number.
"""

import os
import sys
import requests

A1_BASE = "https://hack.a1mobile.com"
TEAM_KEY = os.environ.get("TEAM_KEY", "team-ac4fb03a")


def main():
    if len(sys.argv) < 2:
        print("usage: python verify_number.py +1XXXXXXXXXX")
        sys.exit(1)
    phone = sys.argv[1]
    headers = {"X-Team-Key": TEAM_KEY, "Content-Type": "application/json"}

    r = requests.post(f"{A1_BASE}/api/verified-numbers",
                      headers=headers, json={"phone": phone}, timeout=10)
    print(f"request OTP -> {r.status_code} {r.text}")
    if r.status_code != 200:
        print("Couldn't send OTP. Check the number format (+1...) and your team key.")
        sys.exit(1)

    code = input(f"Enter the code sent to {phone}: ").strip()
    r = requests.post(f"{A1_BASE}/api/verified-numbers/confirm",
                      headers=headers, json={"phone": phone, "code": code}, timeout=10)
    print(f"confirm -> {r.status_code} {r.text}")
    if r.status_code == 200:
        print(f"\n{phone} is verified. You can now text it from your agent.")
    else:
        print("Confirmation failed. Double-check the code and retry.")


if __name__ == "__main__":
    main()
