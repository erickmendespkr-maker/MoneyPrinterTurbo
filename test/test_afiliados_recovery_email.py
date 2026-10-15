"""Checks that password recovery links target the configured Streamlit page."""
from unittest.mock import patch

import pytest

from app.afiliados.recovery_email import send_reset_email


def test_recovery_link_targets_exact_page(monkeypatch):
    settings = {
        "AFILIADOS_SMTP_HOST": "smtp.example.org",
        "AFILIADOS_SMTP_USER": "mailer",
        "AFILIADOS_SMTP_PASSWORD": "local-test-secret",
        "AFILIADOS_SMTP_FROM": "support@example.org",
        "AFILIADOS_SMTP_PORT": "465",
        "AFILIADOS_RESET_PAGE_URL": "https://app.example.org/Afiliados",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    sent = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, *args):
            pass

        def send_message(self, message):
            sent.append(message)

    with patch("app.afiliados.recovery_email.smtplib.SMTP_SSL", FakeSMTP):
        send_reset_email("member@example.org", "example-token")
    assert "https://app.example.org/Afiliados?reset_token=example-token" in sent[0].get_content()


def test_recovery_rejects_query_in_base_url(monkeypatch):
    monkeypatch.setenv("AFILIADOS_RESET_PAGE_URL", "https://app.example.org/Afiliados?other=value")
    with pytest.raises(RuntimeError):
        send_reset_email("member@example.org", "example-token")
