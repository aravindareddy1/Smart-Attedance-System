import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
basedir = Path(__file__).resolve().parent.parent
load_dotenv(basedir / '.env')


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-key-please-change-in-production-7721')
    
    # Database
    _raw_db_url = os.getenv('DATABASE_URL')
    if _raw_db_url and _raw_db_url.startswith('postgres://'):
        _raw_db_url = _raw_db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _raw_db_url or f"sqlite:///{basedir / 'smart_attendance.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Attendance settings
    ATTENDANCE_THRESHOLD = float(os.getenv('ATTENDANCE_THRESHOLD', 75.0))
    FACE_DISTANCE_THRESHOLD = float(os.getenv('FACE_DISTANCE_THRESHOLD', 0.50))
    LBPH_CONFIDENCE_THRESHOLD = float(os.getenv('LBPH_CONFIDENCE_THRESHOLD', 65.0))
    MIN_SESSION_LENGTH = int(os.getenv('MIN_SESSION_LENGTH', 30))
    SESSION_TIMEOUT_MINUTES = int(os.getenv('SESSION_TIMEOUT_MINUTES', 60))
    LATE_THRESHOLD_MINUTES = int(os.getenv('LATE_THRESHOLD_MINUTES', 10))
    
    # Upload and data paths
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_UPLOAD_MB', 5)) * 1024 * 1024
    DATA_DIR = basedir / 'data'
    FACES_DIR = DATA_DIR / 'faces'
    EXPORTS_DIR = DATA_DIR / 'exports'
    BACKUPS_DIR = DATA_DIR / 'backups'
    LOGS_DIR = DATA_DIR / 'logs'
    
    # SMTP / Notifications
    SMTP_ENABLED = os.getenv('SMTP_ENABLED', 'false').lower() in ('true', '1', 't', 'yes')
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM = os.getenv('SMTP_FROM', 'no-reply@smartattendance.edu')
    
    # Application metadata
    APP_VERSION = "1.0.0"
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata')
    FACE_ENGINE = os.getenv('FACE_ENGINE', 'auto')
    
    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    ENV = 'development'


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = False
    ENV = 'testing'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': __import__('sqlalchemy.pool', fromlist=['StaticPool']).StaticPool,
        'connect_args': {'check_same_thread': False}
    }
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost.localdomain'


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    ENV = 'production'
    SESSION_COOKIE_SECURE = True


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

