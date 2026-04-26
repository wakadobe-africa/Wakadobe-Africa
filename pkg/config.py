class General(object):
    APP_NAME='wakadobeblog'
    SQLALCHEMY_TRACK_MODIFICATION=False
    RATELIMIT_DEFAULT = '120 per hour'
    RATELIMIT_STORAGE_URI = 'memory://'
    RATELIMIT_HEADERS_ENABLED = True
class LiveConfig(General):
    DATABASE = 'wakadobedb'
    
class TestConfig(General):
    DATABASE='wakadobedb'