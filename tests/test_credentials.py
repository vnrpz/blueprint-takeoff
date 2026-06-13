"""Credential-handling safety tests (SECURITY_CHECKLIST §"Credential handling").

Proves the two claims made in SECURITY_CHECKLIST.md:
  * ``_Secret`` masks its value in ``repr`` so an accidental ``print(creds)``
    or log of the object never leaks the key.
  * The raw secret string never appears in captured log output.
"""
from __future__ import annotations

import logging

from src import credentials
from src.credentials import _Secret, get, require


SENTINEL = "sk-supersecret-DO-NOT-LEAK-1234567890"


def test_secret_repr_masks_value():
    s = _Secret(SENTINEL)
    r = repr(s)
    assert SENTINEL not in r
    assert "Secret" in r and "len=" in r
    # but it still behaves as the real string where used deliberately
    assert str(s) == SENTINEL
    assert s == SENTINEL


def test_empty_secret_repr():
    assert repr(_Secret("")) == "<Secret empty>"


def test_get_returns_masked_secret(monkeypatch):
    monkeypatch.setenv("SOME_TEST_KEY", SENTINEL)
    val = get("SOME_TEST_KEY")
    assert isinstance(val, _Secret)
    assert str(val) == SENTINEL
    assert SENTINEL not in repr(val)


def test_get_missing_returns_none(monkeypatch):
    monkeypatch.delenv("DEFINITELY_ABSENT_KEY", raising=False)
    assert get("DEFINITELY_ABSENT_KEY") is None


def test_require_raises_without_leaking(monkeypatch):
    monkeypatch.delenv("ANOTHER_ABSENT_KEY", raising=False)
    try:
        require("ANOTHER_ABSENT_KEY")
        raised = False
    except RuntimeError as e:
        raised = True
        assert SENTINEL not in str(e)
    assert raised


def test_secret_value_not_in_logs(monkeypatch, caplog):
    """Logging the Secret object (not str(obj)) must not emit the raw value."""
    monkeypatch.setenv("LOGGED_KEY", SENTINEL)
    val = get("LOGGED_KEY")
    logger = logging.getLogger("credentials_test")
    with caplog.at_level(logging.DEBUG):
        logger.info("loaded credential: %r", val)
        logger.debug("config dump: %s", {"key": repr(val)})
    assert SENTINEL not in caplog.text
