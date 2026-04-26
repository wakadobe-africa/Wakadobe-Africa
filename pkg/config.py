import os
from dotenv import load_dotenv

load_dotenv()

class General(object):
    APP_NAME='wakadobeblog'
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    DEBUG = False
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATION=False
    RATELIMIT_DEFAULT = '120 per hour'
    RATELIMIT_STORAGE_URI = 'memory://'
    RATELIMIT_HEADERS_ENABLED = True

class LiveConfig(General):
    DATABASE = 'wakadobedb'
    
class TestConfig(General):
    DATABASE='wakadobedb'