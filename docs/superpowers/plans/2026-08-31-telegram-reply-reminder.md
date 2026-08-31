# telegram-reply-reminder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telethon-based script that flags Telegram 1:1 chats and
small group chats needing a reply (skipping trivial sticker/emoji-only
exchanges and anything you've reacted to), moves them into a "To Reply Soon"
Telegram folder, auto-removes them once you reply, supports "close
friend"/"family" tiers managed via Saved Messages commands, and skips large
groups — runnable unattended via cron.

**Architecture:** Pure decision logic (`reminder/logic.py`) and pure command
parsing (`reminder/commands.py`) are fully unit tested with fake objects and
raw strings, zero Telethon/DB dependencies. SQLite persistence
(`reminder/db.py`) is a thin, independently-tested layer. The Telethon
wrapper (`reminder/telegram_client.py`) and `run.py` glue these together but
are not unit tested — they require a live Telegram session this environment
cannot create. `login.py` and `set_threshold.py` are small standalone CLI
entry points.

**Tech Stack:** Python 3.11+, Telethon, python-dotenv, sqlite3 (stdlib),
pytest.

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `reminder/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
telethon>=1.36
python-dotenv>=1.0
```

- [ ] **Step 2: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest>=8.0
```

- [ ] **Step 3: Create `.env.example`**

```
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
SESSION_NAME=reminder
DEFAULT_THRESHOLD_HOURS=24
CLOSE_THRESHOLD_HOURS=6
FAMILY_THRESHOLD_HOURS=12
MAX_GROUP_SIZE=10
FOLDER_NAME=To Reply Soon
RUN_INTERVAL_HOURS=36
DB_PATH=reminder.sqlite3
```

- [ ] **Step 4: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
*.session
*.session-journal
reminder.sqlite3
```

- [ ] **Step 5: Create `reminder/__init__.py`** (empty file, makes `reminder` a package)

- [ ] **Step 6: Install dependencies and verify**

Run: `pip install -r requirements-dev.txt`
Expected: installs without error.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt requirements-dev.txt .env.example .gitignore reminder/__init__.py
git commit -m "Scaffold project: deps, env template, gitignore"
```

---

### Task 2: Core decision logic (`reminder/logic.py`)

**Files:**
- Create: `reminder/logic.py`
- Test: `tests/test_logic.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_logic.py`:

```python
from datetime import datetime, timedelta, timezone

from reminder.logic import (
    Message,
    is_trivial_message,
    needs_reply,
    resolve_threshold,
    should_run,
    unreplied_batch,
)

NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)


def msg(id, from_me, hours_ago, text="", is_sticker=False, is_gif=False):
    return Message(
        id=id,
        from_me=from_me,
        date=NOW - timedelta(hours=hours_ago),
        text=text,
        is_sticker=is_sticker,
        is_gif=is_gif,
    )


def test_unreplied_batch_stops_at_my_message():
    messages = [msg(3, False, 1, "yo"), msg(2, False, 2, "hey"), msg(1, True, 5, "hi")]
    batch = unreplied_batch(messages)
    assert [m.id for m in batch] == [3, 2]


def test_unreplied_batch_empty_when_i_replied_last():
    messages = [msg(2, True, 1), msg(1, False, 5)]
    assert unreplied_batch(messages) == []


def test_is_trivial_message_sticker():
    assert is_trivial_message(msg(1, False, 1, is_sticker=True)) is True


def test_is_trivial_message_gif():
    assert is_trivial_message(msg(1, False, 1, is_gif=True)) is True


def test_is_trivial_message_emoji_only():
    assert is_trivial_message(msg(1, False, 1, text="  😂😂  ")) is True


def test_is_trivial_message_empty_text():
    assert is_trivial_message(msg(1, False, 1, text="   ")) is True


def test_is_trivial_message_real_text():
    assert is_trivial_message(msg(1, False, 1, text="are you free tomorrow?")) is False


def test_needs_reply_false_when_batch_empty():
    assert needs_reply([], NOW, 24) is False


def test_needs_reply_false_when_reacted():
    batch = [msg(1, False, 48, text="hey call me")]
    assert needs_reply(batch, NOW, 24, my_reaction_on_last=True) is False


def test_needs_reply_false_when_batch_all_trivial():
    batch = [msg(2, False, 48, is_sticker=True), msg(1, False, 50, text="😂")]
    assert needs_reply(batch, NOW, 24) is False


def test_needs_reply_true_when_real_content_past_threshold():
    batch = [msg(1, False, 48, text="are you free tomorrow?")]
    assert needs_reply(batch, NOW, 24) is True


def test_needs_reply_false_when_within_threshold():
    batch = [msg(1, False, 2, text="are you free tomorrow?")]
    assert needs_reply(batch, NOW, 24) is False


def test_needs_reply_uses_oldest_message_in_batch():
    batch = [msg(2, False, 1, text="ok"), msg(1, False, 48, text="are you free tomorrow?")]
    assert needs_reply(batch, NOW, 24) is True


def test_resolve_threshold_uses_manual_override_first():
    assert resolve_threshold(6, "family", {"close": 6, "family": 12}, 24) == 6


def test_resolve_threshold_uses_tier_when_no_override():
    assert resolve_threshold(None, "close", {"close": 6, "family": 12}, 24) == 6


def test_resolve_threshold_falls_back_to_default_when_no_override_or_tier():
    assert resolve_threshold(None, None, {"close": 6, "family": 12}, 24) == 24


def test_should_run_true_when_never_run():
    assert should_run(None, NOW, 36) is True


def test_should_run_false_when_recent():
    assert should_run(NOW - timedelta(hours=10), NOW, 36) is False


def test_should_run_true_when_overdue():
    assert should_run(NOW - timedelta(hours=40), NOW, 36) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_logic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reminder.logic'`

- [ ] **Step 3: Write `reminder/logic.py`**

```python
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Sequence

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U0001F900-\U0001F9FF"
    "️"
    "]+",
    flags=re.UNICODE,
)


@dataclass
class Message:
    id: int
    from_me: bool
    date: datetime
    text: str = ""
    is_sticker: bool = False
    is_gif: bool = False


def is_trivial_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    without_emoji = _EMOJI_PATTERN.sub("", stripped)
    return without_emoji.strip() == ""


def is_trivial_message(message: Message) -> bool:
    if message.is_sticker or message.is_gif:
        return True
    return is_trivial_text(message.text)


def unreplied_batch(messages: Sequence[Message]) -> list:
    """messages ordered newest-first. Returns the consecutive run of
    not-from-me messages at the head of the list, i.e. everything sent
    since your last message (works for both 1:1 and group dialogs)."""
    batch = []
    for m in messages:
        if m.from_me:
            break
        batch.append(m)
    return batch


def resolve_threshold(
    override_hours: Optional[float],
    tier: Optional[str],
    tier_hours: Dict[str, float],
    default_hours: float,
) -> float:
    if override_hours is not None:
        return override_hours
    if tier and tier in tier_hours:
        return tier_hours[tier]
    return default_hours


def needs_reply(
    batch: Sequence[Message],
    now: datetime,
    threshold_hours: float,
    my_reaction_on_last: bool = False,
) -> bool:
    if not batch:
        return False
    if my_reaction_on_last:
        return False
    if all(is_trivial_message(m) for m in batch):
        return False
    oldest = min(batch, key=lambda m: m.date)
    age_hours = (now - oldest.date).total_seconds() / 3600
    return age_hours >= threshold_hours


def should_run(
    last_run_at: Optional[datetime], now: datetime, interval_hours: float = 36
) -> bool:
    if last_run_at is None:
        return True
    return (now - last_run_at).total_seconds() / 3600 >= interval_hours
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_logic.py -v`
Expected: all tests PASS (18 passed)

- [ ] **Step 5: Commit**

```bash
git add reminder/logic.py tests/test_logic.py
git commit -m "Add core unanswered-chat decision logic with tests"
```

---

### Task 3: Command parser (`reminder/commands.py`)

**Files:**
- Create: `reminder/commands.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_commands.py`:

```python
from reminder.commands import parse_command


def test_parse_close_with_at():
    assert parse_command("/close @alice") == ("close", "alice")


def test_parse_close_without_at():
    assert parse_command("/close alice") == ("close", "alice")


def test_parse_family():
    assert parse_command("/family @bob") == ("family", "bob")


def test_parse_remove():
    assert parse_command("/remove @carol") == ("remove", "carol")


def test_parse_ignores_unrelated_text():
    assert parse_command("hey are you free tomorrow?") is None


def test_parse_ignores_unknown_command():
    assert parse_command("/block @dave") is None


def test_parse_ignores_missing_username():
    assert parse_command("/close") is None


def test_parse_strips_whitespace():
    assert parse_command("  /close   @alice  ") == ("close", "alice")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_commands.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reminder.commands'`

- [ ] **Step 3: Write `reminder/commands.py`**

```python
import re
from typing import Optional, Tuple

_COMMAND_PATTERN = re.compile(r"^/(close|family|remove)\s+@?(\w+)$")


def parse_command(text: str) -> Optional[Tuple[str, str]]:
    match = _COMMAND_PATTERN.match(text.strip())
    if not match:
        return None
    action, username = match.groups()
    return action, username
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_commands.py -v`
Expected: all tests PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add reminder/commands.py tests/test_commands.py
git commit -m "Add /close, /family, /remove command parser with tests"
```

---

### Task 4: SQLite persistence (`reminder/db.py`)

**Files:**
- Create: `reminder/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db.py`:

```python
from datetime import datetime, timezone

from reminder import db


def make_conn(tmp_path):
    return db.connect(str(tmp_path / "test.sqlite3"))


def test_threshold_roundtrip(tmp_path):
    conn = make_conn(tmp_path)
    assert db.get_threshold(conn, 1) is None
    db.set_threshold(conn, 1, 6.0)
    assert db.get_threshold(conn, 1) == 6.0
    db.set_threshold(conn, 1, 9.0)
    assert db.get_threshold(conn, 1) == 9.0
    db.clear_threshold(conn, 1)
    assert db.get_threshold(conn, 1) is None


def test_tier_roundtrip(tmp_path):
    conn = make_conn(tmp_path)
    assert db.get_tier(conn, 1) is None
    db.set_tier(conn, 1, "close")
    assert db.get_tier(conn, 1) == "close"
    db.set_tier(conn, 1, "family")
    assert db.get_tier(conn, 1) == "family"
    db.clear_tier(conn, 1)
    assert db.get_tier(conn, 1) is None


def test_flagged_roundtrip(tmp_path):
    conn = make_conn(tmp_path)
    now = datetime.now(timezone.utc)
    assert db.is_flagged(conn, 1) is False
    db.mark_flagged(conn, 1, now)
    assert db.is_flagged(conn, 1) is True
    db.unmark_flagged(conn, 1)
    assert db.is_flagged(conn, 1) is False


def test_run_state_roundtrip(tmp_path):
    conn = make_conn(tmp_path)
    assert db.get_last_run_at(conn) is None
    now = datetime.now(timezone.utc)
    db.set_last_run_at(conn, now)
    assert db.get_last_run_at(conn) == now
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reminder.db'`

- [ ] **Step 3: Write `reminder/db.py`**

```python
import sqlite3
from datetime import datetime
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_thresholds (
    chat_id INTEGER PRIMARY KEY,
    threshold_hours REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_tiers (
    chat_id INTEGER PRIMARY KEY,
    tier TEXT NOT NULL CHECK (tier IN ('close', 'family'))
);
CREATE TABLE IF NOT EXISTS flagged_chats (
    chat_id INTEGER PRIMARY KEY,
    flagged_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_run_at TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def get_threshold(conn: sqlite3.Connection, chat_id: int) -> Optional[float]:
    row = conn.execute(
        "SELECT threshold_hours FROM chat_thresholds WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return row[0] if row else None


def set_threshold(conn: sqlite3.Connection, chat_id: int, hours: float) -> None:
    conn.execute(
        "INSERT INTO chat_thresholds (chat_id, threshold_hours) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET threshold_hours = excluded.threshold_hours",
        (chat_id, hours),
    )
    conn.commit()


def clear_threshold(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute("DELETE FROM chat_thresholds WHERE chat_id = ?", (chat_id,))
    conn.commit()


def get_tier(conn: sqlite3.Connection, chat_id: int) -> Optional[str]:
    row = conn.execute(
        "SELECT tier FROM chat_tiers WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return row[0] if row else None


def set_tier(conn: sqlite3.Connection, chat_id: int, tier: str) -> None:
    conn.execute(
        "INSERT INTO chat_tiers (chat_id, tier) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET tier = excluded.tier",
        (chat_id, tier),
    )
    conn.commit()


def clear_tier(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute("DELETE FROM chat_tiers WHERE chat_id = ?", (chat_id,))
    conn.commit()


def is_flagged(conn: sqlite3.Connection, chat_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM flagged_chats WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return row is not None


def mark_flagged(conn: sqlite3.Connection, chat_id: int, flagged_at: datetime) -> None:
    conn.execute(
        "INSERT INTO flagged_chats (chat_id, flagged_at) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET flagged_at = excluded.flagged_at",
        (chat_id, flagged_at.isoformat()),
    )
    conn.commit()


def unmark_flagged(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute("DELETE FROM flagged_chats WHERE chat_id = ?", (chat_id,))
    conn.commit()


def get_last_run_at(conn: sqlite3.Connection) -> Optional[datetime]:
    row = conn.execute("SELECT last_run_at FROM run_state WHERE id = 1").fetchone()
    return datetime.fromisoformat(row[0]) if row else None


def set_last_run_at(conn: sqlite3.Connection, when: datetime) -> None:
    conn.execute(
        "INSERT INTO run_state (id, last_run_at) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_run_at = excluded.last_run_at",
        (when.isoformat(),),
    )
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: all tests PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add reminder/db.py tests/test_db.py
git commit -m "Add SQLite persistence layer with tier support and tests"
```

---

### Task 5: Telethon wrapper (`reminder/telegram_client.py`)

Not unit tested — requires a live Telegram session that cannot exist in this
environment. Manual verification happens in Task 7 once `login.py` has been
run against a real account.

**Files:**
- Create: `reminder/telegram_client.py`

- [ ] **Step 1: Write `reminder/telegram_client.py`**

```python
import logging

from telethon.tl import functions, types

from reminder.commands import parse_command
from reminder.logic import Message

logger = logging.getLogger(__name__)


async def get_or_create_folder(client, folder_title: str):
    result = await client(functions.messages.GetDialogFiltersRequest())
    filters = getattr(result, "filters", result)
    for f in filters:
        if getattr(f, "title", None) == folder_title:
            return f
    existing_ids = [f.id for f in filters if hasattr(f, "id")]
    new_id = max(existing_ids, default=1) + 1
    new_filter = types.DialogFilter(
        id=new_id,
        title=folder_title,
        pinned_peers=[],
        include_peers=[],
        exclude_peers=[],
    )
    await client(
        functions.messages.UpdateDialogFilterRequest(id=new_id, filter=new_filter)
    )
    return new_filter


def _peer_key(peer):
    return getattr(
        peer, "user_id", getattr(peer, "channel_id", getattr(peer, "chat_id", None))
    )


async def add_peer_to_folder(client, folder, entity) -> None:
    input_peer = await client.get_input_entity(entity)
    if not any(_peer_key(p) == _peer_key(input_peer) for p in folder.include_peers):
        folder.include_peers.append(input_peer)
        await client(
            functions.messages.UpdateDialogFilterRequest(id=folder.id, filter=folder)
        )


async def remove_peer_from_folder(client, folder, entity) -> None:
    input_peer = await client.get_input_entity(entity)
    before = len(folder.include_peers)
    folder.include_peers = [
        p for p in folder.include_peers if _peer_key(p) != _peer_key(input_peer)
    ]
    if len(folder.include_peers) != before:
        await client(
            functions.messages.UpdateDialogFilterRequest(id=folder.id, filter=folder)
        )


async def fetch_unreplied_batch(client, dialog, limit: int = 20) -> list:
    messages = []
    async for msg in client.iter_messages(dialog.entity, limit=limit):
        messages.append(
            Message(
                id=msg.id,
                from_me=bool(msg.out),
                date=msg.date,
                text=msg.message or "",
                is_sticker=msg.sticker is not None,
                is_gif=msg.gif is not None,
            )
        )
        if msg.out:
            break
    return messages


async def my_reaction_on_last(client, dialog, batch) -> bool:
    if not batch:
        return False
    last = batch[0]
    fetched = await client.get_messages(dialog.entity, ids=last.id)
    if not fetched or not fetched.reactions:
        return False
    me = await client.get_me()
    for reaction in fetched.reactions.recent_reactions or []:
        if getattr(reaction.peer_id, "user_id", None) == me.id:
            return True
    return False


async def get_participant_count(client, entity) -> int:
    if isinstance(entity, types.Chat):
        full = await client(functions.messages.GetFullChatRequest(entity.id))
        return full.full_chat.participants_count
    if isinstance(entity, types.Channel):
        full = await client(functions.channels.GetFullChannelRequest(entity))
        return full.full_chat.participants_count
    return 0


async def is_eligible_dialog(client, dialog, max_group_size: int) -> bool:
    if dialog.is_user:
        return True
    if dialog.is_group:
        count = await get_participant_count(client, dialog.entity)
        return count < max_group_size
    return False


async def fetch_pending_commands(client) -> list:
    """Returns (message_id, action, username) for command-shaped text
    messages in Saved Messages ("me")."""
    commands = []
    async for msg in client.iter_messages("me"):
        if not msg.message:
            continue
        parsed = parse_command(msg.message)
        if parsed:
            action, username = parsed
            commands.append((msg.id, action, username))
    return commands


async def apply_command(client, conn, message_id: int, action: str, username: str) -> None:
    from reminder import db

    try:
        entity = await client.get_entity(username)
    except (ValueError, TypeError):
        logger.warning(
            "Could not resolve @%s for command %s, leaving message in place",
            username,
            action,
        )
        return

    if action == "remove":
        db.clear_tier(conn, entity.id)
    else:
        db.set_tier(conn, entity.id, action)

    await client.delete_messages("me", message_id)
    logger.info("Applied /%s @%s (chat_id=%s)", action, username, entity.id)
```

- [ ] **Step 2: Commit**

```bash
git add reminder/telegram_client.py
git commit -m "Add Telethon wrapper: folders, message batches, tiers, group eligibility"
```

---

### Task 6: One-time login script (`login.py`)

**Files:**
- Create: `login.py`

- [ ] **Step 1: Write `login.py`**

```python
import os

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_NAME = os.environ.get("SESSION_NAME", "reminder")

if __name__ == "__main__":
    with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        me = client.get_me()
        print(f"Logged in as {me.first_name} (id={me.id})")
        print(f"Session saved to {SESSION_NAME}.session — keep this file secret.")
```

- [ ] **Step 2: Commit**

```bash
git add login.py
git commit -m "Add one-time interactive login script"
```

---

### Task 7: Main run script (`run.py`)

**Files:**
- Create: `run.py`

- [ ] **Step 1: Write `run.py`**

```python
import asyncio
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient

from reminder import db
from reminder import telegram_client as tg
from reminder.logic import needs_reply, resolve_threshold, should_run

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("reminder")

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_NAME = os.environ.get("SESSION_NAME", "reminder")
DEFAULT_THRESHOLD_HOURS = float(os.environ.get("DEFAULT_THRESHOLD_HOURS", 24))
TIER_HOURS = {
    "close": float(os.environ.get("CLOSE_THRESHOLD_HOURS", 6)),
    "family": float(os.environ.get("FAMILY_THRESHOLD_HOURS", 12)),
}
MAX_GROUP_SIZE = int(os.environ.get("MAX_GROUP_SIZE", 10))
FOLDER_NAME = os.environ.get("FOLDER_NAME", "To Reply Soon")
RUN_INTERVAL_HOURS = float(os.environ.get("RUN_INTERVAL_HOURS", 36))
DB_PATH = os.environ.get("DB_PATH", "reminder.sqlite3")


async def process_dialog(client, conn, folder, dialog, now: datetime) -> None:
    chat_id = dialog.id
    batch = await tg.fetch_unreplied_batch(client, dialog)
    reacted = await tg.my_reaction_on_last(client, dialog, batch)
    override = db.get_threshold(conn, chat_id)
    tier = db.get_tier(conn, chat_id)
    threshold = resolve_threshold(override, tier, TIER_HOURS, DEFAULT_THRESHOLD_HOURS)
    unanswered = needs_reply(batch, now, threshold, reacted)

    if unanswered and not db.is_flagged(conn, chat_id):
        await tg.add_peer_to_folder(client, folder, dialog.entity)
        db.mark_flagged(conn, chat_id, now)
        logger.info("Flagged chat %s (%s)", chat_id, dialog.name)
    elif not unanswered and db.is_flagged(conn, chat_id):
        await tg.remove_peer_from_folder(client, folder, dialog.entity)
        db.unmark_flagged(conn, chat_id)
        logger.info("Unflagged chat %s (%s)", chat_id, dialog.name)


async def main() -> None:
    conn = db.connect(DB_PATH)
    now = datetime.now(timezone.utc)

    last_run = db.get_last_run_at(conn)
    if not should_run(last_run, now, RUN_INTERVAL_HOURS):
        logger.info("Not due yet (last run %s), skipping", last_run)
        return

    if not os.path.exists(f"{SESSION_NAME}.session"):
        logger.error("No session file found at %s.session. Run login.py first.", SESSION_NAME)
        raise SystemExit(1)

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    try:
        commands = await tg.fetch_pending_commands(client)
        for message_id, action, username in commands:
            await tg.apply_command(client, conn, message_id, action, username)

        folder = await tg.get_or_create_folder(client, FOLDER_NAME)
        async for dialog in client.iter_dialogs():
            if not await tg.is_eligible_dialog(client, dialog, MAX_GROUP_SIZE):
                continue
            await process_dialog(client, conn, folder, dialog, now)
    except Exception:
        logger.exception("Run failed")
        raise SystemExit(1)
    finally:
        await client.disconnect()

    db.set_last_run_at(conn, now)
    logger.info("Run complete")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Manual smoke test (requires real Telegram credentials)**

Run: `python login.py` (once, interactively, enters phone + code)
Run: `python run.py`
Expected: log lines showing dialogs scanned and any chats flagged/unflagged;
check Telegram that a "To Reply Soon" folder now exists. Send yourself
`/close @someusername` in Saved Messages, run again, confirm the log shows
"Applied /close" and the Saved Messages command is gone.

- [ ] **Step 3: Commit**

```bash
git add run.py
git commit -m "Add main run script: commands, tiers, group filtering, folder sync"
```

---

### Task 8: Per-chat threshold CLI (`set_threshold.py`)

**Files:**
- Create: `set_threshold.py`

- [ ] **Step 1: Write `set_threshold.py`**

```python
import asyncio
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient

from reminder import db

load_dotenv()

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_NAME = os.environ.get("SESSION_NAME", "reminder")
DB_PATH = os.environ.get("DB_PATH", "reminder.sqlite3")

USAGE = "Usage: python set_threshold.py [list | set <chat_id> <hours> | clear <chat_id>]"


async def list_chats(client) -> None:
    async for dialog in client.iter_dialogs():
        if dialog.is_user:
            print(f"{dialog.id}\t{dialog.name}")


async def main() -> None:
    conn = db.connect(DB_PATH)
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    try:
        args = sys.argv[1:]
        if not args or args[0] == "list":
            await list_chats(client)
        elif args[0] == "set" and len(args) == 3:
            chat_id, hours = int(args[1]), float(args[2])
            db.set_threshold(conn, chat_id, hours)
            print(f"Set threshold for {chat_id} to {hours}h")
        elif args[0] == "clear" and len(args) == 2:
            chat_id = int(args[1])
            db.clear_threshold(conn, chat_id)
            print(f"Cleared threshold for {chat_id}")
        else:
            print(USAGE)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```bash
git add set_threshold.py
git commit -m "Add CLI to list chats and set per-chat reply thresholds"
```

---

### Task 9: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README** covering: what it does and why, tech
stack, setup (`.env`, `pip install`, `python login.py`), usage (`python
run.py`, `python set_threshold.py`), the `/close` `/family` `/remove` Saved
Messages commands, the trivial/reaction skip rules, the group-size cutoff,
the 36h cron-throttle explanation, and full EC2 + cron + CloudWatch
deployment instructions. Written in the user's own voice (short sentences,
casual/slightly-broken English, technical terms kept, no AI-essay filler).

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Add README"
```

---

### Task 10: Publish to GitHub

**Files:** none (repo-level operations only)

- [ ] **Step 1: Verify all previous commits are in place**

Run: `git log --oneline`
Expected: one commit per prior task, working tree clean (`git status`)

- [ ] **Step 2: Create the GitHub repository**

Run: `gh repo create telegram-reply-reminder --public --source=. --remote=origin --description "Telethon bot that flags Telegram chats you haven't replied to and files them into a To-Reply-Soon folder"`

- [ ] **Step 3: Push**

Run: `git push -u origin main`
Expected: push succeeds, `gh repo view --web` opens the new repo

---

## Plan self-review notes

- Spec coverage: reaction skip ✅ (Task 2), trailing-batch triviality skip ✅
  (Task 2), per-chat manual thresholds ✅ (Tasks 2, 4, 8), close/family tiers
  via Saved Messages commands ✅ (Tasks 3, 4, 5, 7), tier precedence
  (override > tier > default) ✅ (Task 2 `resolve_threshold` + tests), group
  chats under `MAX_GROUP_SIZE` included with identical logic ✅ (Task 5
  `is_eligible_dialog`, Task 7), large groups/channels skipped entirely ✅
  (Task 5), 36h throttle via hourly cron ✅ (Task 2 `should_run`, Task 7,
  documented in README Task 9), CloudWatch/EC2 docs-only ✅ (Task 9).
- No placeholders: every step has complete, runnable code.
- Type/name consistency checked across tasks: `Message`, `needs_reply`,
  `unreplied_batch`, `resolve_threshold(override_hours, tier, tier_hours,
  default_hours)`, `should_run`, `parse_command`, `db.get_tier`/`set_tier`/
  `clear_tier` are defined once and used with identical names/signatures
  everywhere they're referenced later.
