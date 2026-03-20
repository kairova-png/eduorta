"""
GitHub Pages integration routes
Только синхронизация с GitHub Pages без Google Sheets
"""

from flask import Blueprint, request, flash, redirect, url_for, jsonify, render_template
from datetime import datetime, date, timedelta
from app.services.google_sites_service import GoogleSitesService

bp = Blueprint('github_pages', __name__, url_prefix='/github-pages')


@bp.route('/')
def index():
    """Главная страница GitHub Pages интеграции"""
    from app.models import Group, Teacher
    
    # Получаем все группы и преподавателей
    groups = Group.query.all()
    teachers = Teacher.query.all()
    
    # Получаем информацию о текущей и следующей неделе
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    next_monday = current_monday + timedelta(days=7)
    
    context = {
        'groups': groups,
        'teachers': teachers,
        'current_week': {
            'start': current_monday,
            'end': current_monday + timedelta(days=6),
            'description': f"{current_monday.strftime('%d.%m')} - {(current_monday + timedelta(days=6)).strftime('%d.%m.%Y')}"
        },
        'next_week': {
            'start': next_monday,
            'end': next_monday + timedelta(days=6),
            'description': f"{next_monday.strftime('%d.%m')} - {(next_monday + timedelta(days=6)).strftime('%d.%m.%Y')}"
        }
    }
    
    return render_template('github_pages/index.html', **context)


@bp.route('/api/generate-github-package', methods=['POST'])
def api_generate_github_package():
    """API для генерации GitHub Pages пакета"""
    try:
        data = request.get_json() or {}
        
        # Параметры периода
        week_offset = data.get('week', 0)
        
        # Вычисляем даты
        today = date.today()
        current_monday = today - timedelta(days=today.weekday())
        
        if week_offset == 0:
            # Текущая неделя
            period_start = current_monday
            period_end = current_monday + timedelta(days=6)
        elif week_offset == 1:
            # Следующая неделя
            next_monday = current_monday + timedelta(days=7)
            period_start = next_monday
            period_end = next_monday + timedelta(days=6)
        else:
            # Произвольная неделя (смещение в неделях от текущей)
            target_monday = current_monday + timedelta(days=week_offset * 7)
            period_start = target_monday
            period_end = target_monday + timedelta(days=6)
        
        # Создание сервиса
        service = GoogleSitesService()
        
        # Генерация GitHub Pages пакета
        result = service.generate_github_pages_package(period_start, period_end)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка при генерации GitHub Pages пакета: {str(e)}'
        }), 500


@bp.route('/api/sync-to-github', methods=['POST'])
def api_sync_to_github():
    """API для синхронизации с GitHub репозиторием"""
    try:
        data = request.get_json() or {}
        
        # Параметры запроса
        repo_url = data.get('repo_url', 'https://github.com/Azamat313/apec_schedule.git')
        auto_push = data.get('auto_push', False)
        github_dir = data.get('github_dir', 'exports/github_pages')
        
        # Создание сервиса
        service = GoogleSitesService()
        
        # Синхронизация с GitHub
        result = service.sync_to_github_repository(repo_url, github_dir, auto_push)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка синхронизации с GitHub: {str(e)}'
        }), 500


@bp.route('/exports/github_pages/')
@bp.route('/exports/github_pages/index.html')
def serve_github_template():
    """Прямой доступ к HTML шаблону для GitHub Pages"""
    try:
        from flask import send_file
        import os
        
        file_path = os.path.join('exports', 'github_pages', 'index.html')
        if not os.path.exists(file_path):
            return """
            <html>
            <head><title>Шаблон не найден</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h1>GitHub Pages шаблон не найден</h1>
                <p>Пожалуйста, сначала сгенерируйте файлы через интерфейс.</p>
                <a href="/github-pages/">← Вернуться к генератору</a>
            </body>
            </html>
            """
        
        return send_file(file_path)
        
    except Exception as e:
        return f"Ошибка: {str(e)}", 500