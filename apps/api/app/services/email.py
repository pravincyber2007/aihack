import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_action_email(*, recipient: str, subject: str, action_url: str) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST must be configured to send account emails")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        f"Use this link to continue. It can only be used once and will expire soon:\n\n"
        f"{action_url}\n"
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        if settings.smtp_starttls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
