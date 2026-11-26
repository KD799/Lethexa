
import os
import smtplib
import ssl

from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()


class EmailDeliveryError(Exception):
    pass


def send_otp_email(recipient: str, otp: str):
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM_EMAIL", username)

    if not username or not password or not sender:
        raise EmailDeliveryError(
            "Email delivery is not configured"
        )

    message = EmailMessage()
    message["Subject"] = "Lethexa - Identity Verification Code"
    message["From"] = sender
    message["To"] = recipient

    message.set_content(
        f"""
Hello,

Your Lethexa identity verification code is:

{otp}

This code expires in 5 minutes.

Do not share this code with anyone.

If you did not request this verification, please ignore this email.

Regards,
Lethexa Security Team
"""
    )

    try:
        context = ssl.create_default_context()

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(username, password)
            server.send_message(message)

    except (smtplib.SMTPException, OSError) as error:
        raise EmailDeliveryError(
            "Unable to deliver verification email"
        ) from error
