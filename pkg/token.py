import base64
import hashlib
import hmac
from urllib.parse import urlencode

import pyotp
from itsdangerous import URLSafeTimedSerializer
from flask import current_app, request, url_for

from pkg.tasks import enqueue_admin_otp_email, enqueue_verification_email

# The app now routes email delivery through task functions instead of sending
# mail directly inside the request. This keeps the request path short and makes
# it easier to replace this with a real queue worker later.




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


def build_signed_url(endpoint, token, **values):
    path = url_for(endpoint, **values)
    query = urlencode({"token": token}, safe="")

    if request.url_root:
        base_url = request.url_root.rstrip("/")
        return f"{base_url}{path}?{query}"

    scheme = current_app.config.get("PREFERRED_URL_SCHEME", "http")
    server_name = current_app.config.get("SERVER_NAME") or "127.0.0.1:5000"
    return f"{scheme}://{server_name}{path}?{query}"


def send_email(to_email, url):
    enqueue_verification_email(to_email, url)


def send_admin_otp_email(to_email, otp_code):
    enqueue_admin_otp_email(to_email, otp_code)
