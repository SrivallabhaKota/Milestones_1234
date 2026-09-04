import os

class Config:
    # Security key
    SECRET_KEY = os.environ.get('SECRET_KEY', 'finsight_ultra_secret_key_2024_change_in_production')

    # Database Configuration (Auto-switches between Local and Render/TiDB)
    MYSQL_HOST     = os.environ.get('MYSQL_HOST',     'localhost')
    MYSQL_PORT     = int(os.environ.get('MYSQL_PORT', 3307)) # Local default 3307, TiDB is 4000
    MYSQL_USER     = os.environ.get('MYSQL_USER',     'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'root@123')
    MYSQL_DB       = os.environ.get('MYSQL_DB',       'finsight')
    
    # TiDB Cloud ki SSL mandatory kabatti idi add chesthunnam
    MYSQL_SSL      = os.environ.get('MYSQL_SSL',      'false').lower() == 'true'
    MYSQL_CURSORCLASS = 'DictCursor'

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'