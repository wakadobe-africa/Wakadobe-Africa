import os
from dotenv import load_dotenv

load_dotenv()

class General(object):
    APP_NAME='wakadobeblog'
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    
    # Validate required variables
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "SQLALCHEMY_DATABASE_URI environment variable is not set. "
            "Please set it in your environment or .env file."
        )
    DEBUG = True
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATION=False
    RATELIMIT_DEFAULT = '120 per hour'
    RATELIMIT_STORAGE_URI = 'memory://'
    RATELIMIT_HEADERS_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True  # helps prevent XSS attacks
    SESSION_COOKIE_SECURE = False  # set to True in production with HTTPS
    SESSION_COOKIE_SAMESITE = 'Lax'  # helps prevent CSRF attacks
    PERMANENT_SESSION_LIFETIME = 3600  # session expires after 1 hour of inactivity
    # Mail (shared defaults)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').strip().lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_TIMEOUT = 5  # 5-second timeout for SMTP connections
    CLOUDINARY_URL = os.getenv('CLOUDINARY_URL')
    CLOUDINARY_FOLDER = os.getenv('CLOUDINARY_FOLDER', 'wakadobe/cover_images')
    OTP_SECRET = os.getenv('OTP_SECRET', SECRET_KEY)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')


class LiveConfig(General):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_HTTPONLY = True  # helps prevent XSS attacks
    SESSION_COOKIE_SECURE = True  # set to True in production with HTTPS
    SESSION_COOKIE_SAMESITE = 'Lax'  # helps prevent CSRF attacks
    PERMANENT_SESSION_LIFETIME = 3600  
    
class TestConfig(General):
    DEBUG = True
    TESTING = True