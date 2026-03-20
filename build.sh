#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Initialize database
python3 -c "
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', full_name='Администратор', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Admin user created')
    print('Database ready')
"
