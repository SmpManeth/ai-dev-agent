"""Tests for username validation."""

from validators import validate_username


def test_invalid_username_message_not_email() -> None:
    ok, err = validate_username("!!")
    assert ok is False
    assert err is not None
    assert "email" not in err.lower()
    assert "username" in err.lower()
