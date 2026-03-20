import os
import secrets

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    basedir = basedir
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'college.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Security settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') != 'development'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Performance settings
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year for static files
    
    # Logging settings
    LOGS_DIR = os.path.join(basedir, 'logs')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # Paths
    DATA_DIR = os.path.join(basedir, 'data')
    EXPORTS_DIR = os.path.join(basedir, 'exports')

    # Bell schedule
    PAIR_TIMES = {
        1: {"start": "08:30", "end": "09:50"},
        2: {"start": "10:00", "end": "11:20"},
        3: {"start": "11:30", "end": "12:50"},
        4: {"start": "13:30", "end": "14:50"},
        5: {"start": "15:00", "end": "16:20"},
        6: {"start": "16:30", "end": "17:50"},
        7: {"start": "18:00", "end": "19:20"},
    }

    # Schedule statuses
    SCHEDULE_STATUS = {
        "planned": {"name_ru": "Запланирована", "color": "#FFFFFF", "counts_as_hours": False},
        "done": {"name_ru": "Проведена", "color": "#D4EDDA", "counts_as_hours": True},
        "substitution": {"name_ru": "Замена", "color": "#FFF3CD", "counts_as_hours": True},
        "cancelled": {"name_ru": "Отменена", "color": "#F8D7DA", "counts_as_hours": False},
        "completed": {"name_ru": "Последняя пара", "color": "#E2D5F1", "counts_as_hours": True},
        "rescheduled": {"name_ru": "Перенесена", "color": "#E7F1FF", "counts_as_hours": False},
        "vacant": {"name_ru": "Вакант", "color": "#F0F0F0", "counts_as_hours": False}
    }

    # GUP week types that need schedule
    GUP_NEEDS_SCHEDULE = ["", None, "УП", "ОТ", "ӨО"]
    
    # Google Sheets Integration (старая версия)
    GOOGLE_SHEETS_WEBHOOK_URL = os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL') or 'https://script.google.com/macros/s/AKfycbx0pabq8S90z0B4PcvFCZP_ROY4QG8Z6eTr-D9ouJrke_ekzDqzJklsid_qxpcWOJm6/exec'
    GOOGLE_SHEETS_AUTO_UPDATE = os.environ.get('GOOGLE_SHEETS_AUTO_UPDATE', 'true').lower() == 'true'
    GOOGLE_SHEETS_UPDATE_ON_GENERATION = True
    GOOGLE_SHEETS_UPDATE_ON_SCHEDULE_CHANGE = True
    
    # Google Sheets Simple Integration (новая упрощенная версия)
    GOOGLE_SHEETS_SIMPLE_WEBHOOK_URL = os.environ.get('GOOGLE_SHEETS_SIMPLE_WEBHOOK_URL') or 'https://script.google.com/macros/s/AKfycbzq9a0LOBAj0Nm679RygAc11lWeUeK_v3-ryL4mbrnVL1_qeHz6N9KeIe0eyxif1HCVwQ/exec'
    GOOGLE_SHEETS_AUTO_SYNC = os.environ.get('GOOGLE_SHEETS_AUTO_SYNC', 'true').lower() == 'true'
    
    # Authentication settings
    # AUTH_ENABLED=true in production, false for local development
    AUTH_ENABLED = os.environ.get('AUTH_ENABLED', 'true').lower() == 'true'
    AUTH_USERNAME = os.environ.get('AUTH_USERNAME', 'admin')
    AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD')  # MUST be set in .env
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 360 * 60  # 360 minutes in seconds

    # Production security
    @staticmethod
    def check_production_config():
        """Check if production configuration is secure"""
        errors = []
        if Config.AUTH_ENABLED and not Config.AUTH_PASSWORD:
            errors.append("AUTH_PASSWORD must be set when AUTH_ENABLED=true")
        if os.environ.get('FLASK_ENV') == 'production':
            if not os.environ.get('SECRET_KEY'):
                errors.append("SECRET_KEY must be set in production")
        return errors
