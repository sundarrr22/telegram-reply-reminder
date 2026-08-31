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
