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
