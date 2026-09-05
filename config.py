import os

class Config:
    # Security key
    SECRET_KEY = os.environ.get('SECRET_KEY', 'finsight_ultra_secret_key_2024_change_in_production')

    # Local = False (default), Render/TiDB = set USE_TIDB=true in Render environment variables
    USE_TIDB = os.environ.get('USE_TIDB', 'false').lower() == 'true'

    if USE_TIDB:
        # ---------------------------------------------------------
        # TiDB Cloud Configuration (for Render deployment)
        # ---------------------------------------------------------
        MYSQL_HOST     = os.environ.get('MYSQL_HOST',     'gateway01.us-west-2.prod.aws.tidbcloud.com')
        MYSQL_PORT     = int(os.environ.get('MYSQL_PORT', 4000))
        MYSQL_USER     = os.environ.get('MYSQL_USER',     '2J7P9todcFuFhcR.root')
        MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'ONincsXT0DJjUfl')
        MYSQL_DB       = os.environ.get('MYSQL_DB',       'test')
        
        # SSL is mandatory for TiDB Cloud
        MYSQL_SSL      = True
    else:
        # ---------------------------------------------------------
        # Local Database Configuration (default for development)
        # ---------------------------------------------------------
        MYSQL_HOST     = os.environ.get('MYSQL_HOST',     'localhost')
        MYSQL_PORT     = int(os.environ.get('MYSQL_PORT', 3307))
        MYSQL_USER     = os.environ.get('MYSQL_USER',     'root')
        MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'root@123')
        MYSQL_DB       = os.environ.get('MYSQL_DB',       'finsight')
        
        MYSQL_SSL      = False

    # Common Configurations
    MYSQL_CURSORCLASS = 'DictCursor'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
