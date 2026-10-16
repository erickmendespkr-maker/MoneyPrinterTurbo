"""Send one-time account-verification links through configured SMTP SSL.

No external request is made unless explicitly called after configuration.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote, urlsplit


def send_verification_email(recipient: str, token: str) -> None:
    host = os.environ.get("AFILIADOS_SMTP_HOST", "")
    username = os.environ.get("AFILIADOS_SMTP_USER", "")
    password = os.environ.get("AFILIADOS_SMTP_PASSWORD", "")
    sender = os.environ.get("AFILIADOS_SMTP_FROM", "")
    base_url = os.environ.get("AFILIADOS_VERIFY_PAGE_URL", "")
    try:
        port = int(os.environ.get("AFILIADOS_SMTP_PORT", "465"))
        parsed = urlsplit(base_url)
    except ValueError as exc:
        raise RuntimeError("Envio de verificação não configurado") from exc
    if (not all((host, username, password, sender, base_url, recipient, token))
            or parsed.scheme != "https" or not parsed.netloc
            or parsed.username or parsed.password or parsed.fragment or parsed.query
            or port != 465):
        raise RuntimeError("Envio de verificação não configurado com segurança")
    link = base_url.rstrip("/") + "?verify_token=" + quote(token, safe="")
    message = EmailMessage()
    message["Subject"] = "Afiliados Creator — confirme seu e-mail"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Confirme seu endereço de e-mail para gerar vídeos no Afiliados Creator.\n\n"
        f"Abra este link em até 24 horas:\n{link}\n\n"
        "Se não criou essa conta, ignore esta mensagem.\n"
    )
    with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)
