import json
import logging

from app.core.logging import JSONFormatter, RedactionFilter


def _render(msg: str, *args: object) -> dict:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )
    RedactionFilter().filter(record)
    rendered = JSONFormatter().format(record)
    return json.loads(rendered)


def test_api_key_is_redacted():
    secret = "sk-abcdefghijklmnopqrstuvwxyz0123456789"
    payload = _render("calling provider with key=%s", secret)
    assert secret not in json.dumps(payload)
    assert "REDACTED" in json.dumps(payload)


def test_bearer_token_is_redacted():
    payload = _render("Authorization: Bearer ab12cd34ef56gh78")
    rendered = json.dumps(payload)
    assert "ab12cd34ef56gh78" not in rendered
    assert "REDACTED" in rendered


def test_password_field_is_redacted():
    payload = _render('login attempt with password="hunter2-secret"')
    rendered = json.dumps(payload)
    assert "hunter2-secret" not in rendered
    assert "REDACTED" in rendered


def test_non_secret_message_untouched():
    payload = _render("job %s completed successfully", "abc123")
    assert payload["message"] == "job abc123 completed successfully"
