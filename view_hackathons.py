"""Quick script to view all stored hackathons in the database."""

import sqlite3

conn = sqlite3.connect("data/hackathons.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT platform, name, url, location, deadline, is_online "
    "FROM hackathons ORDER BY first_seen DESC"
).fetchall()

print(f"=== HACKATHON HUNTER DATABASE ({len(rows)} entries) ===\n")
for i, r in enumerate(rows, 1):
    if r["is_online"] == 1:
        status = "[Online]"
    elif r["is_online"] == 0:
        status = "[In-Person]"
    else:
        status = "[Unknown]"

    print(f"{i:>3}. [{r['platform'].upper()}] {r['name']}")
    print(f"     URL      : {r['url']}")
    print(f"     Status   : {status}")
    if r["location"]:
        print(f"     Location : {r['location']}")
    if r["deadline"]:
        print(f"     Deadline : {r['deadline']}")
    print()

conn.close()
