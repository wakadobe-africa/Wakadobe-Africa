import os
import threading

from flask import current_app
from flask_mail import Message
from redis import Redis
from rq import Queue

from pkg import app, mail


# This module is the first step toward a background worker.
# The web request will enqueue a task, and a separate worker process can later
# execute the email sending work outside the request lifecycle.


def get_queue():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return Queue(connection=Redis.from_url(redis_url))


def _send_message_now(msg):
    try:
        import socket
        socket.setdefaulttimeout(5)
        mail.send(msg)
    except Exception as exc:
        current_app.logger.exception("Email send failed: %s", exc)
        return False
    finally:
        import socket
        socket.setdefaulttimeout(None)

    return True


def send_verification_email(to_email, url):
    with app.app_context():
        msg = Message(
            subject="Verify your email address",
            sender=current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME"),
            recipients=[to_email],
        )
        msg.body = f"Please click the following link to verify your email address: {url}"
        return _send_message_now(msg)


def enqueue_verification_email(to_email, url):
    queue = get_queue()
    queue.enqueue(send_verification_email, to_email, url)


def send_admin_otp_email(to_email, otp_code):
    with app.app_context():
        msg = Message(
            subject="Your Wakadobe admin verification code",
            sender=current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME"),
            recipients=[to_email],
        )
        msg.body = (
            "Use the verification code below to complete your Wakadobe admin action:\n\n"
            f"{otp_code}\n\n"
            "This code expires in 5 minutes. If you did not request this, please ignore this message."
        )
        return _send_message_now(msg)


def enqueue_admin_otp_email(to_email, otp_code):
    queue = get_queue()
    queue.enqueue(send_admin_otp_email, to_email, otp_code)
