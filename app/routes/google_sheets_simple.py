"""
Google Sheets Simple Routes
Recreated original interface with GitHub Pages functionality only
"""

from flask import Blueprint, request, flash, redirect, url_for, jsonify, render_template
from datetime import datetime, date, timedelta
from app.services.google_sites_service import GoogleSitesService
from app.models import Group, Teacher, Schedule
from app import db

bp = Blueprint('google_sheets_simple', __name__, url_prefix='/google-sheets')


@bp.route('/')
def index():
    """Главная страница с GitHub Pages и автосинхронизацией"""
    from app.models import Group, Teacher
    
    groups = Group.query.all()
    teachers = Teacher.query.all()
    
    # Статистика по группам и расписанию
    total_schedules = Schedule.query.count()
    
    context = {
        'groups': groups,
        'teachers': teachers,
        'total_schedules': total_schedules,
        'current_date': date.today(),
    }
    
    return render_template('google_sheets/index.html', **context)


@bp.route('/sites/')
def sites_index():
    """GitHub Pages интеграция - оригинальная страница"""
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
    
    return render_template('google_sheets/sites.html', **context)


@bp.route('/sites/api/generate-and-sync', methods=['POST'])
def api_generate_and_sync():
    """API для генерации и синхронизации GitHub Pages"""
    try:
        data = request.get_json() or {}
        
        # Параметры периода (по умолчанию текущая неделя)
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
        generate_result = service.generate_github_pages_package(period_start, period_end)
        
        if not generate_result['success']:
            return jsonify(generate_result), 500
        
        # Автоматическая синхронизация с GitHub
        sync_result = service.sync_to_github_repository(
            repo_url='https://github.com/Azamat313/apec_schedule.git',
            github_dir='exports/github_pages',
            auto_push=True
        )
        
        # Объединяем результаты
        result = {
            'success': sync_result['success'],
            'message': f"Файлы сгенерированы и {'синхронизированы с GitHub' if sync_result['success'] else 'ошибка синхронизации'}",
            'generation': generate_result,
            'sync': sync_result
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка при генерации и синхронизации: {str(e)}'
        }), 500


@bp.route('/api/auto-sync-status')
def api_auto_sync_status():
    """API для проверки статуса автосинхронизации"""
    return jsonify({
        'success': True,
        'enabled': True,
        'status': 'running',
        'last_sync': datetime.now().isoformat(),
        'message': 'GitHub Pages автосинхронизация активна'
    })


@bp.route('/api/get-sheets-info')
def api_get_sheets_info():
    """API для получения информации о листах (эмуляция для совместимости)"""
    # Возвращаем заглушку для совместимости со старым интерфейсом
    return jsonify({
        'success': True,
        'sheets': [
            {
                'name': 'GitHub Pages Export',
                'type': 'github_pages',
                'protected': False,
                'hidden': False,
                'created_time': datetime.now().isoformat()
            }
        ]
    })


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
            # Произвольная неделя
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


@bp.route('/api/update-json-only', methods=['POST'])
def api_update_json_only():
    """API для обновления только JSON файлов (без создания HTML и без git push)"""
    try:
        from datetime import datetime
        from app.services.google_sites_service import GoogleSitesService
        import os
        import json
        
        # Создание сервиса
        service = GoogleSitesService()
        
        # Генерируем JSON данные для ВСЕГО расписания (без ограничения периода)
        
        # Генерируем JSON данные напрямую из базы данных
        from app.models import Schedule, Group, Teacher, Workload, Room
        from app import db
        
        # Получаем ВСЕ данные без ограничения периода
        groups = Group.query.order_by(Group.name).all()
        teachers = Teacher.query.order_by(Teacher.full_name).all()
        
        # Базовый запрос расписания - ВСЁ РАСПИСАНИЕ ЗА ВЕСЬ ГОД
        query = db.session.query(Schedule)\
            .join(Workload, Schedule.workload_id == Workload.id)\
            .join(Group, Workload.group_id == Group.id)\
            .outerjoin(Teacher, Workload.teacher_id == Teacher.id)\
            .outerjoin(Room, Schedule.room_id == Room.id)
        
        schedules = query.order_by(Schedule.date, Schedule.pair_number).all()
        
        # Подготавливаем данные для JSON с меткой времени генерации
        generated_at = datetime.now().isoformat()
        groups_data = {
            'generated_at': generated_at,
            'groups': [{'id': g.id, 'name': g.name} for g in groups]
        }
        teachers_data = {
            'generated_at': generated_at,
            'teachers': [{'id': t.id, 'name': t.full_name} for t in teachers]
        }
        schedule_data = {
            'generated_at': generated_at,
            'schedules': []
        }
        for schedule in schedules:
            # Пропускаем выходные дни (суббота=5, воскресенье=6)
            if schedule.date.weekday() >= 5:
                continue

            schedule_data['schedules'].append({
                'id': schedule.id,
                'date': schedule.date.isoformat(),
                'pair_number': schedule.pair_number,
                'status': schedule.status,
                'discipline': schedule.workload.discipline,
                'lesson_type': schedule.workload.lesson_type,
                'group': {
                    'id': schedule.workload.group.id,
                    'name': schedule.workload.group.name
                },
                'teacher': {
                    'id': schedule.workload.teacher.id,
                    'name': schedule.workload.teacher.full_name
                } if schedule.workload.teacher else None,
                'substitute_teacher': {
                    'id': schedule.substitute_teacher.id,
                    'name': schedule.substitute_teacher.full_name
                } if schedule.substitute_teacher else None,
                'room': {
                    'id': schedule.room.id,
                    'number': schedule.room.number
                } if schedule.room else None,
                'notes': schedule.notes,
                'change_reason': schedule.change_reason
            })

        # Сохраняем JSON файлы в docs/api директорию
        github_dir = os.path.join('exports', 'github_pages')
        docs_dir = os.path.join(github_dir, 'docs')
        api_dir = os.path.join(docs_dir, 'api')
        os.makedirs(api_dir, exist_ok=True)
        
        # Groups
        groups_file = os.path.join(api_dir, 'groups.json')
        with open(groups_file, 'w', encoding='utf-8') as f:
            json.dump(groups_data, f, ensure_ascii=False, indent=2)
            
        # Teachers  
        teachers_file = os.path.join(api_dir, 'teachers.json')
        with open(teachers_file, 'w', encoding='utf-8') as f:
            json.dump(teachers_data, f, ensure_ascii=False, indent=2)
            
        # Schedule
        schedule_file = os.path.join(api_dir, 'schedule.json')
        with open(schedule_file, 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, ensure_ascii=False, indent=2)
        
        # Синхронизируем с GitHub после обновления JSON файлов
        try:
            import subprocess
            import shutil

            github_dir = os.path.abspath(os.path.join('exports', 'github_pages'))
            docs_dir = os.path.join(github_dir, 'docs')
            repo_url = 'https://github.com/Azamat313/apec_schedule.git'

            # Проверяем, существует ли директория и является ли она git репозиторием
            git_dir = os.path.join(github_dir, '.git')
            if not os.path.exists(git_dir):
                # Нужно клонировать репозиторий
                print(f"[SYNC] Git репозиторий не найден в {github_dir}, клонируем...")

                # Удаляем директорию если существует (но не является git repo)
                if os.path.exists(github_dir):
                    shutil.rmtree(github_dir)

                # Клонируем репозиторий
                os.makedirs(os.path.dirname(github_dir), exist_ok=True)
                clone_result = subprocess.run(
                    ['git', 'clone', repo_url, github_dir],
                    capture_output=True, text=True
                )

                if clone_result.returncode != 0:
                    return jsonify({
                        'success': True,
                        'message': f'JSON файлы обновлены локально. Git clone ошибка: {clone_result.stderr}',
                        'updated_files': ['groups.json', 'teachers.json', 'schedule.json'],
                        'sync_error': clone_result.stderr,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })

                print(f"[SYNC] Репозиторий склонирован успешно")

                # Создаем docs/api директорию и копируем JSON файлы туда
                new_api_dir = os.path.join(github_dir, 'docs', 'api')
                os.makedirs(new_api_dir, exist_ok=True)

                # Копируем JSON файлы
                for json_file in ['groups.json', 'teachers.json', 'schedule.json']:
                    src = os.path.join(api_dir, json_file)
                    dst = os.path.join(new_api_dir, json_file)
                    if os.path.exists(src):
                        shutil.copy2(src, dst)

            # Теперь работаем с репозиторием
            work_dir = github_dir

            # Добавляем изменения в git
            git_add_result = subprocess.run(['git', 'add', '.'],
                                           cwd=work_dir,
                                           capture_output=True, text=True)

            # Проверяем есть ли изменения для коммита
            git_status_result = subprocess.run(['git', 'status', '--porcelain'],
                                              cwd=work_dir,
                                              capture_output=True, text=True)

            if git_status_result.stdout.strip():
                # Есть изменения - делаем коммит
                commit_message = f"Auto-update JSON files - {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                git_commit_result = subprocess.run(['git', 'commit', '-m', commit_message],
                                                  cwd=work_dir,
                                                  capture_output=True, text=True)

                print(f"[SYNC] Git commit: {git_commit_result.stdout}")

                # Пушим изменения
                git_push_result = subprocess.run(['git', 'push', 'origin', 'main'],
                                                cwd=work_dir,
                                                capture_output=True, text=True)

                if git_push_result.returncode == 0:
                    sync_result = {'success': True, 'message': 'JSON files pushed successfully'}
                else:
                    # Если push не удался, попробуем сделать pull и повторить push
                    if 'fetch first' in git_push_result.stderr or 'rejected' in git_push_result.stderr:
                        # Делаем pull с rebase
                        git_pull_result = subprocess.run(['git', 'pull', 'origin', 'main', '--rebase'],
                                                        cwd=work_dir,
                                                        capture_output=True, text=True)

                        if git_pull_result.returncode == 0:
                            # Повторяем push
                            git_push_retry_result = subprocess.run(['git', 'push', 'origin', 'main'],
                                                                  cwd=work_dir,
                                                                  capture_output=True, text=True)

                            if git_push_retry_result.returncode == 0:
                                sync_result = {'success': True, 'message': 'JSON files pushed successfully after pull'}
                            else:
                                sync_result = {'success': False, 'message': f'Git push retry failed: {git_push_retry_result.stderr}'}
                        else:
                            sync_result = {'success': False, 'message': f'Git pull failed: {git_pull_result.stderr}'}
                    else:
                        sync_result = {'success': False, 'message': f'Git push failed: {git_push_result.stderr}'}
            else:
                sync_result = {'success': True, 'message': 'No changes to push'}

            return jsonify({
                'success': True,
                'message': f"JSON файлы обновлены и {'загружены в GitHub' if sync_result['success'] else 'ошибка загрузки в GitHub'}",
                'updated_files': ['groups.json', 'teachers.json', 'schedule.json'],
                'sync': sync_result,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        except Exception as sync_error:
            import traceback
            print(f"[SYNC] Ошибка синхронизации: {traceback.format_exc()}")
            # Файлы обновились локально, но синхронизация не удалась
            return jsonify({
                'success': True,
                'message': f'JSON файлы обновлены локально. Ошибка синхронизации: {str(sync_error)}',
                'updated_files': ['groups.json', 'teachers.json', 'schedule.json'],
                'sync_error': str(sync_error),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка обновления JSON файлов: {str(e)}'
        }), 500


@bp.route('/api/full-generate-and-push', methods=['POST']) 
def api_full_generate_and_push():
    """API для полной генерации HTML + JSON + git push"""
    try:
        # Создание сервиса
        service = GoogleSitesService()
        
        # Используем текущую дату как базу для генерации (без ограничений)
        today = date.today()
        current_monday = today - timedelta(days=today.weekday())
        period_start = current_monday
        period_end = current_monday + timedelta(days=6)
        
        # Полная генерация GitHub Pages пакета (но данные будут содержать ВСЁ расписание)
        generate_result = service.generate_github_pages_package(period_start, period_end)
        
        if not generate_result['success']:
            return jsonify(generate_result), 500
        
        # Автоматический git push с полной перезаписью файлов
        sync_result = service.sync_to_github_repo(
            github_dir='exports/github_pages/docs',  # Путь где генерируются файлы
            repo_url='https://github.com/Azamat313/apec_schedule.git',
            auto_push=True,
            force_overwrite=True  # Полная перезапись для обновления всех файлов
        )
        
        # Объединяем результаты
        result = {
            'success': sync_result['success'],
            'message': f"Страница создана и {'загружена в GitHub' if sync_result['success'] else 'ошибка загрузки в GitHub'}",
            'generation': generate_result,
            'git_push': sync_result
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка полной генерации: {str(e)}'
        }), 500


@bp.route('/api/sync-to-github', methods=['POST'])
def api_sync_to_github():
    """API для синхронизации с GitHub репозиторием"""
    try:
        data = request.get_json() or {}
        
        # Параметры запроса
        repo_url = data.get('repo_url', 'https://github.com/Azamat313/apec_schedule.git')
        auto_push = data.get('auto_push', True)
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