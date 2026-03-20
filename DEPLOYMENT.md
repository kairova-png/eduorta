# Deployment Guide for lite.apec.edu.kz

## Requirements
- Python 3.10+
- Nginx (web server)
- SSL certificate (Let's Encrypt)

## Step 1: Prepare Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3 python3-pip python3-venv nginx -y
```

## Step 2: Upload Project

```bash
# Create project directory
sudo mkdir -p /var/www/lite.apec.edu.kz
sudo chown $USER:$USER /var/www/lite.apec.edu.kz

# Upload project files (use scp, rsync, or git)
# Example with rsync:
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
  ./college_schedule/ user@server:/var/www/lite.apec.edu.kz/
```

## Step 3: Setup Python Environment

```bash
cd /var/www/lite.apec.edu.kz

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 4: Configure Environment

```bash
# Copy production environment file
cp .env.production .env

# Edit .env and set:
# 1. SECRET_KEY - generate new: python -c "import secrets; print(secrets.token_hex(32))"
# 2. AUTH_PASSWORD - set strong password
# 3. DATABASE_URL - keep SQLite or configure PostgreSQL
nano .env
```

## Step 5: Database Setup

### Option A: SQLite (simple, for small loads)
```bash
# Create instance directory
mkdir -p instance

# Copy your existing database
scp local_machine:path/to/college.db instance/college.db

# Or initialize new database
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

### Option B: PostgreSQL (recommended for production)
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Create database
sudo -u postgres psql
CREATE DATABASE apec_schedule;
CREATE USER apec_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE apec_schedule TO apec_user;
\q

# Update .env
DATABASE_URL=postgresql://apec_user:your_password@localhost:5432/apec_schedule

# Install PostgreSQL driver
pip install psycopg2-binary

# Migrate data from SQLite (optional)
# Use tool like pgloader or manual export/import
```

## Step 6: Setup Gunicorn Service

```bash
# Create systemd service file
sudo nano /etc/systemd/system/apec-schedule.service
```

Content:
```ini
[Unit]
Description=APEC Schedule Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/lite.apec.edu.kz
Environment="PATH=/var/www/lite.apec.edu.kz/venv/bin"
EnvironmentFile=/var/www/lite.apec.edu.kz/.env
ExecStart=/var/www/lite.apec.edu.kz/venv/bin/gunicorn --workers 3 --bind unix:apec-schedule.sock -m 007 run:app

[Install]
WantedBy=multi-user.target
```

```bash
# Start and enable service
sudo systemctl start apec-schedule
sudo systemctl enable apec-schedule
sudo systemctl status apec-schedule
```

## Step 7: Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/lite.apec.edu.kz
```

Content:
```nginx
server {
    listen 80;
    server_name lite.apec.edu.kz;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/lite.apec.edu.kz/apec-schedule.sock;
    }

    location /static {
        alias /var/www/lite.apec.edu.kz/app/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/lite.apec.edu.kz /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

## Step 8: SSL Certificate (HTTPS)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d lite.apec.edu.kz

# Auto-renewal test
sudo certbot renew --dry-run
```

## Step 9: Firewall

```bash
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## Synchronization (Local <-> Server)

### Manual Database Sync

SQLite database can be copied manually:

```bash
# Download from server
scp user@server:/var/www/lite.apec.edu.kz/instance/college.db ./backup_$(date +%Y%m%d).db

# Upload to server
scp ./instance/college.db user@server:/var/www/lite.apec.edu.kz/instance/college.db

# Restart service after upload
ssh user@server "sudo systemctl restart apec-schedule"
```

### Automated Sync Script (sync.sh)

```bash
#!/bin/bash
SERVER="user@server"
REMOTE_PATH="/var/www/lite.apec.edu.kz"

# Backup local
cp instance/college.db "backup/college_$(date +%Y%m%d_%H%M%S).db"

# Sync to server
rsync -avz instance/college.db $SERVER:$REMOTE_PATH/instance/

# Restart remote service
ssh $SERVER "sudo systemctl restart apec-schedule"

echo "Sync completed!"
```

## Troubleshooting

### Check Logs
```bash
# Application logs
sudo journalctl -u apec-schedule -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
```

### Restart Services
```bash
sudo systemctl restart apec-schedule
sudo systemctl restart nginx
```

### Check Database Permissions
```bash
sudo chown www-data:www-data /var/www/lite.apec.edu.kz/instance/college.db
sudo chmod 664 /var/www/lite.apec.edu.kz/instance/college.db
```

## Security Checklist

- [ ] SECRET_KEY changed to random value
- [ ] AUTH_PASSWORD changed to strong password
- [ ] HTTPS enabled with valid certificate
- [ ] Firewall configured
- [ ] Database file permissions set correctly
- [ ] .env file not accessible from web
- [ ] Debug mode disabled (FLASK_DEBUG=0)
