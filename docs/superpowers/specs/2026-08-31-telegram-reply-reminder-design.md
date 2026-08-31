# telegram-reply-reminder — Design

## Purpose

A personal automation that scans your Telegram 1:1 chats and small group chats,
figures out which ones genuinely need a reply from you, and moves those into a
Telegram folder called "To Reply Soon". Runs unattended on a cron schedule
(EC2), self-heals its own folder state (removes chats you've since replied
to), lets you manage "close friends" / "family" tiers by texting yourself
commands, and reports failures via CloudWatch.

## Components

- `login.py` — one-time interactive login (phone + code via Telethon). Produces
  a `.session` file that every later run reuses. No bot token — this acts as
  your real account so it can see your existing DMs.
- `reminder/db.py` — SQLite helpers. `reminder.sqlite3` holds:
  - `chat_thresholds(chat_id INTEGER PRIMARY KEY, threshold_hours REAL)` — per-chat
    manual override. Highest priority.
  - `chat_tiers(chat_id INTEGER PRIMARY KEY, tier TEXT CHECK (tier IN ('close','family')))`
    — tier assigned via Saved Messages commands (see **Tiers** below).
  - `flagged_chats(chat_id INTEGER PRIMARY KEY, flagged_at TEXT)` — chats currently
    sitting in the "To Reply Soon" folder, so a later run knows what to check for
    un-flagging.
  - `run_state(id INTEGER PRIMARY KEY CHECK (id = 1), last_run_at TEXT)` — single
    row, powers the 36h throttle.
- `reminder/logic.py` — pure, unit-testable decision functions (no Telethon/DB
  imports), covered by pytest:
  - `resolve_threshold(override_hours, tier, tier_hours, default_hours)`
  - `needs_reply(batch, my_reaction_on_last)` — see **Unanswered logic** below
  - `should_run(last_run_at, now, interval_hours=36)` — throttle check
- `reminder/commands.py` — pure command parser (no Telethon/DB imports),
  covered by pytest: `parse_command(text) -> (action, username) | None` for
  `/close`, `/family`, `/remove` messages. See **Tiers** below.
- `reminder/telegram_client.py` — thin Telethon wrapper: iterate dialogs
  (1:1 and eligible groups), fetch the trailing unreplied batch of messages
  for a dialog, check reactions, get a group's participant count, add/remove
  a peer from the "To Reply Soon" dialog filter (folder), and read/apply/clear
  tier commands from Saved Messages.
- `set_threshold.py` — CLI: lists your chats (name + id), lets you set/clear a
  custom `threshold_hours` for one, writes to `chat_thresholds`. (Tiers are
  managed via Telegram commands, not this CLI — see **Tiers**.)
- `run.py` — the cron entry point. See **Run flow** below.
- `tests/test_logic.py`, `tests/test_commands.py` — pytest covering the pure
  modules with fake message objects / raw command strings.

## Tiers: close friends & family (`reminder/commands.py`)

You manage tiers by sending yourself a command in Saved Messages. Each run,
before scanning dialogs, `run.py` reads Saved Messages for command-shaped
text messages and applies them:

- `/close @username` — assign that chat to the **close** tier.
- `/family @username` — assign that chat to the **family** tier.
- `/remove @username` — clear any tier assignment for that chat (back to
  default threshold behavior).

Processing a command: resolve `@username` to a chat id via
`client.get_entity(username)`, write/clear the row in `chat_tiers`, then
**delete the command message** from Saved Messages so it isn't reprocessed
and Saved Messages doesn't accumulate clutter. If the username can't be
resolved, log a warning and **leave the message in place** (so the user
notices and can fix the typo) instead of silently dropping it.

Tiers only affect the default threshold used when no manual per-chat
override exists (see `resolve_threshold` below): `CLOSE_THRESHOLD_HOURS` and
`FAMILY_THRESHOLD_HOURS` (from `.env`) replace `DEFAULT_THRESHOLD_HOURS` for
chats in that tier. Precedence, highest first: manual `chat_thresholds`
override → tier default → `DEFAULT_THRESHOLD_HOURS`.

## Group chat eligibility

Only two kinds of dialogs are ever considered:

- **1:1 chats** — always eligible.
- **Group chats with fewer than `MAX_GROUP_SIZE` members** (default 10, from
  `.env`) — eligible, and run through the *exact same* unanswered logic as
  1:1s (the trailing batch can span multiple senders; that's fine, the same
  trivial/reaction/threshold rules apply uniformly).

Groups with `MAX_GROUP_SIZE` or more members, and any broadcast channel, are
skipped entirely — never fetched, never checked, never flagged.

## Unanswered logic

For each eligible dialog (1:1, or a group under the member-count cap):

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
3. Read Saved Messages for `/close`, `/family`, `/remove` commands and apply
   each (see **Tiers**) before doing anything else.
4. Ensure the "To Reply Soon" dialog filter exists (create it if missing).
5. For every dialog that passes **Group chat eligibility**:
   - Look up its manual override / tier, resolve the threshold.
   - Run the unanswered logic above.
   - **Needs flagging** → add chat's peer to the folder (if not already) +
     upsert `flagged_chats`.
   - **Currently flagged but no longer unanswered** (you replied, or it's now
     trivial/reacted) → remove peer from the folder + delete from
     `flagged_chats`.
6. Update `run_state.last_run_at = now`.
7. Structured logging throughout (`logging` to stdout, one line per action:
   command applied, flagged / unflagged / skipped-trivial / skipped-reacted /
   skipped-large-group / error). Any unhandled exception is logged with
   `logger.exception` and the process exits 1, so a CloudWatch metric filter
   on `ERROR`/non-zero exit can alarm on it.

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
CLOSE_THRESHOLD_HOURS=6
FAMILY_THRESHOLD_HOURS=12
MAX_GROUP_SIZE=10
FOLDER_NAME=To Reply Soon
RUN_INTERVAL_HOURS=36
```

## Testing

- `tests/test_logic.py`: `needs_reply` against fabricated message batches
  (text-only, sticker-only, mixed, reacted, empty-emoji, aged vs fresh),
  `resolve_threshold` across override/tier/default precedence, and
  `should_run` against various `last_run_at` deltas.
- `tests/test_commands.py`: `parse_command` against valid `/close`, `/family`,
  `/remove` strings (with and without `@`), and invalid/unrelated text.
- No live Telegram connection is used or possible in this environment —
  Telethon/DB code is a thin wrapper kept out of the unit-tested surface
  intentionally.

## Deployment (documented in README only)

No IaC/scripts are created — the user deploys this by hand to their own EC2
box. README covers: venv setup, running `login.py` once interactively,
the crontab line, a CloudWatch agent config snippet to ship `run.py`'s log
output to a log group, and a metric-filter alarm on `ERROR` lines plus a
basic EC2 status-check alarm.

## Out of scope

- Broadcast channels, and groups at or above `MAX_GROUP_SIZE` members.
- Any actual AWS provisioning — this repo is the application only.
- Multi-account support.
- Tiers beyond "close" and "family" (no arbitrary custom tier names).
