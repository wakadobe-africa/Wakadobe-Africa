import base64
import hashlib
import hmac
import pyotp
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
from pkg import mail




def _get_totp_secret(email: str) -> str:
    secret_key = (current_app.config.get("OTP_SECRET") or current_app.config.get("SECRET_KEY") or "wakadobe-otp-secret").strip()
    if not secret_key:
        raise ValueError("OTP secret is not configured.")

    email_key = (email or "").strip().lower()
    digest = hmac.new(secret_key.encode("utf-8"),
    email_key.encode("utf-8"), hashlib.sha256).digest()
    return base64.b32encode(digest).decode("utf-8")


def generate_admin_otp(email: str, interval: int = 300, digits: int = 6) -> str:
    totp = pyotp.TOTP(_get_totp_secret(email), digits=digits, interval=interval)
    return totp.now()


def verify_admin_otp(email: str, otp_code: str, valid_window: int = 1, interval: int = 300) -> bool:
    totp = pyotp.TOTP(_get_totp_secret(email), digits=6, interval=interval)
    return bool(totp.verify((otp_code or "").strip(), valid_window=valid_window))


def generate_email_address_verify(email, salt):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(email, salt=salt)


def verify_signup_token(token, salt):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        return serializer.loads(token, salt=salt, max_age=3600)
    except Exception:
        return None


def send_email(to_email, url):
    msg = Message(
        subject="Verify your email address",
        sender=current_app.config["MAIL_USERNAME"],
        recipients=[to_email],
    )
    msg.body = f"Please click the following link to verify your email address: {url}"
    mail.send(msg)


def send_admin_otp_email(to_email, otp_code):
    msg = Message(
        subject="Your Wakadobe admin verification code",
        sender=current_app.config["MAIL_USERNAME"],
        recipients=[to_email],
    )
    msg.body = (
        "Use the verification code below to complete your Wakadobe admin action:\n\n"
        f"{otp_code}\n\n"
        "This code expires in 5 minutes. If you did not request this, please ignore this message."
    )
    mail.send(msg)
