# telegram-reply-reminder — Design

## Purpose

A personal automation that scans your Telegram 1:1 chats, figures out which ones
genuinely need a reply from you, and moves those into a Telegram folder called
"To Reply Soon". Runs unattended on a cron schedule (EC2), self-heals its own
folder state (removes chats you've since replied to), and reports failures via
CloudWatch.

## Components

- `login.py` — one-time interactive login (phone + code via Telethon). Produces
  a `.session` file that every later run reuses. No bot token — this acts as
  your real account so it can see your existing DMs.
- `reminder/db.py` — SQLite helpers. `reminder.sqlite3` holds:
  - `chat_thresholds(chat_id INTEGER PRIMARY KEY, threshold_hours REAL)` — per-chat
    override. Falls back to `DEFAULT_THRESHOLD_HOURS` (from `.env`) when absent.
  - `flagged_chats(chat_id INTEGER PRIMARY KEY, flagged_at TEXT)` — chats currently
    sitting in the "To Reply Soon" folder, so a later run knows what to check for
    un-flagging.
  - `run_state(id INTEGER PRIMARY KEY CHECK (id = 1), last_run_at TEXT)` — single
    row, powers the 36h throttle.
- `reminder/logic.py` — pure, unit-testable decision functions (no Telethon/DB
  imports), covered by pytest:
  - `resolve_threshold(chat_id, override_hours, default_hours)`
  - `needs_reply(batch, my_reaction_on_last)` — see **Unanswered logic** below
  - `should_run(last_run_at, now, interval_hours=36)` — throttle check
- `reminder/telegram_client.py` — thin Telethon wrapper: iterate 1:1 dialogs,
  fetch the trailing unreplied batch of messages for a dialog, check reactions,
  add/remove a peer from the "To Reply Soon" dialog filter (folder).
- `set_threshold.py` — CLI: lists your chats (name + id), lets you set/clear a
  custom `threshold_hours` for one, writes to `chat_thresholds`.
- `run.py` — the cron entry point. See **Run flow** below.
- `tests/test_logic.py` — pytest covering `logic.py` with fake message objects.

## Unanswered logic

For each 1:1 dialog:

1. Find the **unreplied batch**: every consecutive message from the other
   person since your last sent message (could be 0, 1, or many messages).
   - Batch empty (your last message is the latest, or chat has no messages) →
     not unanswered, skip.
2. **Reaction check**: if you've placed a reaction on the last message in the
   batch → treat as acknowledged, skip (never flag).
3. **Triviality check**: classify the batch as *trivial* if every message in
   it is a sticker, GIF/animated media, or emoji-only text (regex: after
   stripping whitespace, the text is empty or composed solely of emoji
   codepoints). A trivial batch never needs a reply → skip, regardless of age.
4. Otherwise the batch is real content. Compare the *oldest* message in the
   batch's timestamp against `resolve_threshold(...)`. If older than the
   threshold → this chat is unanswered.

## Run flow (`run.py`)

1. `should_run()`: read `run_state.last_run_at`; if `now - last_run_at < 36h`,
   log "not due yet" and exit 0 immediately.
2. Connect Telethon using the saved session (fail loudly + exit 1 if no
   session file — points the user at `login.py`).
3. Ensure the "To Reply Soon" dialog filter exists (create it if missing).
4. For every 1:1 dialog:
   - Run the unanswered logic above.
   - **Needs flagging** → add chat's peer to the folder (if not already) +
     upsert `flagged_chats`.
   - **Currently flagged but no longer unanswered** (you replied, or it's now
     trivial/reacted) → remove peer from the folder + delete from
     `flagged_chats`.
5. Update `run_state.last_run_at = now`.
6. Structured logging throughout (`logging` to stdout, one line per action:
   flagged / unflagged / skipped-trivial / skipped-reacted / error). Any
   unhandled exception is logged with `logger.exception` and the process exits
   1, so a CloudWatch metric filter on `ERROR`/non-zero exit can alarm on it.

### Why cron fires hourly, not every 36h

Standard cron can't express "every 36 hours" (36 doesn't divide 24 cleanly).
The crontab entry is `0 * * * *` (hourly); `run.py`'s own throttle in step 1
is what actually enforces the 36h cadence. This keeps the real interval
correct even if the box reboots or a run is skipped, since it's driven by
the last successful run's timestamp, not by cron's schedule math.

## Config (`.env`)

```
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
DEFAULT_THRESHOLD_HOURS=24
FOLDER_NAME=To Reply Soon
RUN_INTERVAL_HOURS=36
```

## Testing

- `tests/test_logic.py`: `needs_reply` against fabricated message batches
  (text-only, sticker-only, mixed, reacted, empty-emoji, aged vs fresh) and
  `should_run` against various `last_run_at` deltas. No live Telegram
  connection is used or possible in this environment — Telethon/DB code is
  a thin wrapper kept out of the unit-tested surface intentionally.

## Deployment (documented in README only)

No IaC/scripts are created — the user deploys this by hand to their own EC2
box. README covers: venv setup, running `login.py` once interactively,
the crontab line, a CloudWatch agent config snippet to ship `run.py`'s log
output to a log group, and a metric-filter alarm on `ERROR` lines plus a
basic EC2 status-check alarm.

## Out of scope

- Group chats / channels (1:1 only, per original description: "unanswered
  chats" implies personal conversations).
- Any actual AWS provisioning — this repo is the application only.
- Multi-account support.
