#!/usr/bin/env python3
"""Check Intel's Workday board for new internships and push them to ntfy.

Each new job triggers one notification right away and one reminder
`reminder_after_hours` later. Nothing else is ever sent.

Env vars:
  NTFY_TOPIC  (required) your private ntfy topic name
  NTFY_SERVER (optional) defaults to https://ntfy.sh
Flags:
  --test      send a single test notification and exit
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())
STATE_FILE = ROOT / "seen_jobs.json"
PAGE_SIZE = 20


def fetch_jobs():
    jobs, offset = {}, 0
    while True:
        body = json.dumps({
            "appliedFacets": CONFIG["applied_facets"],
            "limit": PAGE_SIZE,
            "offset": offset,
            "searchText": CONFIG.get("search_text", ""),
        }).encode()
        req = urllib.request.Request(
            CONFIG["api_url"], data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                # Workday returns 429 for Python's default User-Agent.
                "User-Agent": "Mozilla/5.0 (job-notifier)",
            },
        )
        data = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.load(r)
                break
            except urllib.error.URLError:
                if attempt == 2:
                    raise
                time.sleep(10 * (attempt + 1))
        postings = data.get("jobPostings", [])
        for p in postings:
            path = p.get("externalPath", "")
            job_id = (p.get("bulletFields") or [path.rsplit("_", 1)[-1]])[0]
            jobs[job_id] = {
                "title": p.get("title", "Unknown title"),
                "location": p.get("locationsText", ""),
                "posted": p.get("postedOn", ""),
                "url": CONFIG["job_base_url"] + path,
            }
        offset += PAGE_SIZE
        if not postings or offset >= data.get("total", 0):
            return jobs


def notify(title, message, url, tags="briefcase"):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        sys.exit("NTFY_TOPIC env var is not set")
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    payload = {
        "topic": topic,
        "title": title,
        "message": message,
        "click": url,
        "tags": [tags],
        "priority": 4,
        "actions": [{"action": "view", "label": "Open job", "url": url}],
    }
    req = urllib.request.Request(
        server, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=30).read()


def send_job(job_id, job, reminder=False):
    prefix = "Reminder: " if reminder else "New: "
    title = f"{prefix}{CONFIG['company']}: {job['title']}"
    msg = f"{job['location']} · {job_id} · {job['posted']}"
    notify(title, msg, job["url"], tags="alarm_clock" if reminder else "briefcase")


def main():
    if "--test" in sys.argv:
        notify("Job notifier works", "You'll get alerts here when new Intel internships appear.",
               CONFIG["job_base_url"])
        print("Test notification sent.")
        return

    first_run = not STATE_FILE.exists()
    state = {} if first_run else json.loads(STATE_FILE.read_text())
    now = time.time()
    jobs = fetch_jobs()
    print(f"Fetched {len(jobs)} jobs.")

    for job_id, job in jobs.items():
        if job_id in state:
            continue
        if first_run:
            # Baseline: don't spam about jobs that already existed.
            state[job_id] = {**job, "first_seen": now, "reminded": True}
        else:
            print(f"NEW: {job_id} {job['title']}")
            send_job(job_id, job)
            state[job_id] = {**job, "first_seen": now, "reminded": False}

    remind_after = CONFIG.get("reminder_after_hours", 2) * 3600
    for job_id, s in state.items():
        if not s.get("reminded") and now - s["first_seen"] >= remind_after:
            if job_id in jobs:  # skip reminder if the posting was already taken down
                print(f"REMIND: {job_id} {s['title']}")
                send_job(job_id, s, reminder=True)
            s["reminded"] = True

    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    if first_run:
        print(f"First run: saved {len(state)} existing jobs as baseline, no notifications sent.")


if __name__ == "__main__":
    main()
