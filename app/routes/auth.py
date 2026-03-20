from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from config import Config

bp = Blueprint('auth', __name__, url_prefix='/auth')


def requires_auth():
    """Check if authentication is required and user is authenticated"""
    if not Config.AUTH_ENABLED:
        return False
    
    if 'user_authenticated' not in session:
        return True
    return False


def init_global_auth(app):
    """Initialize global authentication for all routes except auth and some API endpoints"""
    @app.before_request
    def check_auth():
        # Skip authentication for auth routes
        if request.endpoint and request.endpoint.startswith('auth.'):
            return
        
        # Skip for CMK routes (has its own auth system)
        if request.endpoint and request.endpoint.startswith('cmk.'):
            return

        # Skip for some API endpoints if needed (you can customize this)
        if request.endpoint and request.endpoint.startswith('api.'):
            return
        
        # Skip for workload templates API endpoints for development
        if request.endpoint and request.endpoint.startswith('workload_templates.'):
            return
            
        # Skip for static files
        if request.endpoint == 'static':
            return
            
        if requires_auth():
            return redirect(url_for('auth.login'))


def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not Config.AUTH_ENABLED:
            return f(*args, **kwargs)
        
        if 'user_authenticated' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if not Config.AUTH_ENABLED:
        return redirect(url_for('main.index'))
    
    # If already logged in, redirect to main page
    if 'user_authenticated' in session:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == Config.AUTH_USERNAME and password == Config.AUTH_PASSWORD:
            session['user_authenticated'] = True
            session['username'] = username
            session.permanent = True
            flash('Успешный вход в систему', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Неверные данные для входа', 'error')
    
    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('auth.login'))