import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'finsight_ultra_secret_key_2024_change_in_production')

    MYSQL_HOST     = os.environ.get('MYSQL_HOST',     'localhost')
    MYSQL_PORT     = int(os.environ.get('MYSQL_PORT', 3307))
    MYSQL_USER     = os.environ.get('MYSQL_USER',     'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'root@123')
    MYSQL_DB       = os.environ.get('MYSQL_DB',       'finsight')
    MYSQL_SSL      = os.environ.get('MYSQL_SSL',      'false').lower() == 'true'
    MYSQL_CURSORCLASS = 'DictCursor'

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

