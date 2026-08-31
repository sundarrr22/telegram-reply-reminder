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
