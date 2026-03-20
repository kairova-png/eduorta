#!/usr/bin/env python
"""Entry point for the college schedule application."""

import os

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import AcademicYear, Department, Specialty, Group, Teacher, Room, GUP, Workload, Schedule

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'AcademicYear': AcademicYear,
        'Department': Department,
        'Specialty': Specialty,
        'Group': Group,
        'Teacher': Teacher,
        'Room': Room,
        'GUP': GUP,
        'Workload': Workload,
        'Schedule': Schedule
    }


@app.cli.command('init-db')
def init_db():
    """Initialize the database."""
    db.create_all()
    print('Database initialized.')


@app.cli.command('import-data')
def import_data_cmd():
    """Import college data from JSON files."""
    from app.services.importer import import_college_data, import_gup
    from config import Config

    print('Importing college data...')
    result = import_college_data(Config.DATA_DIR)
    print(f'Imported: {result}')

    print('Importing GUP...')
    count = import_gup(Config.DATA_DIR)
    print(f'Imported {count} GUP entries.')


if __name__ == '__main__':
    flask_env = os.environ.get('FLASK_ENV', 'development')
    flask_debug = os.environ.get('FLASK_DEBUG', '1')

    # Debug mode based on environment
    debug_mode = flask_env == 'development' or flask_debug == '1'

    # Check production config
    from config import Config
    if flask_env == 'production':
        errors = Config.check_production_config()
        if errors:
            print("PRODUCTION CONFIG ERRORS:")
            for err in errors:
                print(f"  - {err}")
            exit(1)

    print(f"Starting Flask server:")
    print(f"  FLASK_ENV: {flask_env}")
    print(f"  DEBUG mode: {debug_mode}")
    print(f"  AUTH_ENABLED: {Config.AUTH_ENABLED}")
    print(f"  Host: 127.0.0.1:5000")

    app.run(
        debug=debug_mode,
        host='127.0.0.1',
        port=5000,
        use_reloader=debug_mode
    )
