import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'forte-dev-secret-change-in-prod')

    _db_url = os.environ.get('DATABASE_URL', '')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif _db_url.startswith('postgresql://'):
        _db_url = _db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    # Append SSL for Neon.tech if not already present
    if _db_url and 'neon.tech' in _db_url and 'sslmode' not in _db_url:
        _db_url += '?sslmode=require'
    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{os.path.join(BASE_DIR, 'forte.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'connect_args': {'sslmode': 'require'} if os.environ.get('DATABASE_URL', '') and 'neon.tech' in os.environ.get('DATABASE_URL', '') else {},
    }

    DEV_MODE      = os.environ.get('DEV_MODE', '0') == '1'
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
