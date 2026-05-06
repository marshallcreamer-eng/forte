import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'forte-dev-secret-change-in-prod')

    _db_url = os.environ.get('DATABASE_URL', '')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif _db_url.startswith('postgresql://'):
        _db_url = _db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{os.path.join(BASE_DIR, 'forte.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    # Most managed Postgres (Koyeb, Neon, Railway) require SSL
    _ssl_required = bool(_db_url) and 'sslmode' not in _db_url
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'connect_args': {'sslmode': 'require'} if _ssl_required else {},
    }

    DEV_MODE      = os.environ.get('DEV_MODE', '0') == '1'
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
