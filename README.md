# Intel internship notifier

Checks Intel's Workday careers board (Gdańsk, Poland, interns/students) every 30 minutes on GitHub Actions.
When a new job appears, it sends a push notification to your phone through [ntfy](https://ntfy.sh), plus one reminder 2 hours later.

## Setup
1. Install the **ntfy** app (iOS/Android) and subscribe to your private topic name.
2. Add that topic name as a repo secret called `NTFY_TOPIC`.
3. Actions → "Check Intel internships" → Run workflow, then tick "test" to get a test notification.

## Settings
Edit `config.json`:
- `applied_facets`: Workday filters (location / job family IDs, copied from the careers site URL)
- `search_text`: optional keyword
- `reminder_after_hours`: when the single reminder is sent

Run locally: `NTFY_TOPIC=your-topic python3 check_jobs.py`
