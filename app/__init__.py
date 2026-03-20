from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
import logging
from logging.handlers import RotatingFileHandler
import os

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes import main, groups, teachers, rooms, workload, schedule, reports, settings, gup, periods, github_pages, google_sheets_simple, schedule_wizard, auth, workload_templates, cmk
    app.register_blueprint(main.bp)
    app.register_blueprint(groups.bp)
    app.register_blueprint(teachers.bp)
    app.register_blueprint(rooms.bp)
    app.register_blueprint(workload.bp)
    app.register_blueprint(schedule.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(gup.bp)
    app.register_blueprint(periods.bp)
    app.register_blueprint(github_pages.bp)
    app.register_blueprint(google_sheets_simple.bp)
    app.register_blueprint(schedule_wizard.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(workload_templates.bp)
    app.register_blueprint(cmk.bp)

    # Инициализация глобальной аутентификации
    from app.routes.auth import init_global_auth
    init_global_auth(app)

    # Инициализация автосинхронизации Google Sheets (временно отключено)
    # from app.services.auto_sync import init_auto_sync
    # init_auto_sync(app)

    # Configure logging for production
    if not app.debug and not app.testing:
        if not os.path.exists(app.config['LOGS_DIR']):
            os.makedirs(app.config['LOGS_DIR'])
        
        file_handler = RotatingFileHandler(
            os.path.join(app.config['LOGS_DIR'], 'college_schedule.log'),
            maxBytes=app.config['LOG_MAX_SIZE'],
            backupCount=app.config['LOG_BACKUP_COUNT']
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(getattr(logging, app.config['LOG_LEVEL']))
        app.logger.addHandler(file_handler)
        app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))
        app.logger.info('College Schedule application startup')

    return app
