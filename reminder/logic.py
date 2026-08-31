"""Pure decision logic for telegram-reply-reminder.

This module contains zero I/O and zero Telethon/DB dependencies. It is the
fully-unit-tested core that decides whether a chat needs a reply. Later
layers (Telethon client wrapper, SQLite persistence, run.py) call into these
functions but this file must stay importable on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence

# Common emoji unicode ranges, the variation selector, the misc-symbols/arrows
# block (stars, arrows, etc.), and the zero-width joiner (used to glue
# multi-codepoint emoji like family/profession sequences together) — all
# stripped to detect "emoji-only" text so it can be treated as trivial (like
# a sticker).
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "☀-➿"
    "\U00002B00-\U00002BFF"
    "\U0001F1E6-\U0001F1FF"
    "\U0001F900-\U0001F9FF"
    "️"
    "‍"
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
    """True if text is empty/whitespace-only, or only emoji after stripping."""
    stripped = text.strip()
    if not stripped:
        return True
    without_emoji = _EMOJI_PATTERN.sub("", stripped)
    return without_emoji.strip() == ""


def is_trivial_message(message: Message) -> bool:
    if message.is_sticker or message.is_gif:
        return True
    return is_trivial_text(message.text)


def unreplied_batch(messages: Sequence[Message]) -> List[Message]:
    """Return the consecutive run of not-from_me messages at the head of
    `messages` (which is ordered newest-first). Stops at the first
    from_me=True message.
    """
    batch: List[Message] = []
    for message in messages:
        if message.from_me:
            break
        batch.append(message)
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
    if all(is_trivial_message(message) for message in batch):
        return False

    oldest = min(batch, key=lambda message: message.date)
    age_hours = (now - oldest.date).total_seconds() / 3600
    return age_hours >= threshold_hours


def should_run(
    last_run_at: Optional[datetime],
    now: datetime,
    interval_hours: float = 36,
) -> bool:
    if last_run_at is None:
        return True
    elapsed_hours = (now - last_run_at).total_seconds() / 3600
    return elapsed_hours >= interval_hours
