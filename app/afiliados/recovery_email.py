"""SMTP delivery for password recovery; credentials must be server-side secrets."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote, urlsplit


def send_reset_email(recipient: str, token: str) -> None:
    host = os.environ.get("AFILIADOS_SMTP_HOST", "")
    username = os.environ.get("AFILIADOS_SMTP_USER", "")
    password = os.environ.get("AFILIADOS_SMTP_PASSWORD", "")
    sender = os.environ.get("AFILIADOS_SMTP_FROM", "")
    base_url = os.environ.get("AFILIADOS_RESET_PAGE_URL", "")
    port = int(os.environ.get("AFILIADOS_SMTP_PORT", "465"))
    parsed = urlsplit(base_url)
    if (not all((host, username, password, sender, base_url))
            or parsed.scheme != "https" or not parsed.netloc
            or parsed.username or parsed.password or parsed.fragment or parsed.query
            or port != 465):
        raise RuntimeError("Envio de recuperação não configurado com segurança")
    link = base_url.rstrip("/") + "?reset_token=" + quote(token, safe="")
    message = EmailMessage()
    message["Subject"] = "Afiliados Creator — recuperação de senha"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Recebemos uma solicitação para redefinir sua senha.\n\n"
        f"Acesse o link (válido por 30 minutos):\n{link}\n\n"
        "Se não solicitou a alteração, ignore esta mensagem.\n"
    )
    with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)
