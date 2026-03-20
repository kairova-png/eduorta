"""WSGI entry point for production deployment."""

import os
from app import create_app

# Set production environment
os.environ['FLASK_ENV'] = 'production'

app = create_app()

if __name__ == "__main__":
    app.run()