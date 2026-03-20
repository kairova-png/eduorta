from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from datetime import datetime, date, timedelta
from sqlalchemy import and_
from app import db
from app.models import Schedule, Workload, Group, Teacher, Room, AcademicYear, ScheduleChange, GUP, SchedulePeriod, RoomPreference
from app.services.scheduler import ScheduleGenerator, get_available_rooms, update_hours_completed
from app.services.smart_scheduler import SmartScheduleGenerator
from app.services.schedule_changes import ScheduleChangeService
from app.routes.schedule_utils import is_period_closed, perform_detailed_placement_diagnostic, generation_progress
from config import Config
import threading
import uuid
import time

# Safe print for Windows with Kazakh/Russian characters
def safe_print(msg):
    try:
        print(str(msg))
    except UnicodeEncodeError:
        # Skip output if encoding fails - don't crash the app
        pass


def auto_mark_past_weeks_done():
    """
    Автоматически отмечает все пары прошедших недель как проведенные ('done')
    для всех групп. Вызывается при загрузке страницы расписания.
    Оптимизация: выполняется только раз в день (проверяется через session).
    """
    today = datetime.now().date()
    today_str = today.isoformat()

    # Проверяем, была ли уже выполнена проверка сегодня
    last_auto_mark_date = session.get('last_auto_mark_past_weeks_date')
    if last_auto_mark_date == today_str:
        return 0  # Уже выполнялось сегодня

    # Начало текущей недели (понедельник)
    current_week_start = today - timedelta(days=today.weekday())

    # Находим все пары со статусом 'planned', у которых дата меньше начала текущей недели
    past_planned_schedules = Schedule.query.filter(
        Schedule.status == 'planned',
        Schedule.date < current_week_start
    ).all()

    # Запоминаем, что проверка выполнена сегодня (даже если нечего отмечать)
    session['last_auto_mark_past_weeks_date'] = today_str

    if not past_planned_schedules:
        return 0

    # Собираем уникальные workload_id для обновления счетчиков
    affected_workload_ids = set()

    # Массово обновляем статусы
    for schedule in past_planned_schedules:
        schedule.status = 'done'
        affected_workload_ids.add(schedule.workload_id)

    db.session.commit()

    # Обновляем счетчики выполненных часов для затронутых нагрузок
    for workload_id in affected_workload_ids:
        update_hours_completed(workload_id)

    safe_print(f"Auto-marked {len(past_planned_schedules)} past schedules as done for {len(affected_workload_ids)} workloads")

    return len(past_planned_schedules)


bp = Blueprint('schedule', __name__, url_prefix='/schedule')


# Utility functions moved to schedule_utils.py


@bp.route('/')
def index():
    """Schedule view - main page"""
    # Автоматически отмечаем все пары прошедших недель как проведенные
    auto_mark_past_weeks_done()

    group_id = request.args.get('group_id', type=int)
    teacher_id = request.args.get('teacher_id', type=int)
    week_offset = request.args.get('week', 0, type=int)
    view_type = request.args.get('view', 'week')  # week, month, year

    # Calculate date ranges based on view type
    today = datetime.now().date()
    
    if view_type == 'week':
        # Правильный расчет начала недели (понедельник)
        # В Python weekday(): Пн=0, Вт=1, Ср=2, Чт=3, Пт=4, Сб=5, Вс=6
        period_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        period_end = period_start + timedelta(days=4)  # Friday
        
    elif view_type == 'month':
        # Current month + month_offset
        month_offset = request.args.get('month', 0, type=int)
        if month_offset != 0:
            if month_offset > 0:
                month = today.month + month_offset
                year = today.year + (month - 1) // 12
                month = ((month - 1) % 12) + 1
            else:
                month = today.month + month_offset
                year = today.year + month // 12
                if month <= 0:
                    year -= 1
                    month = 12 + month
        else:
            month, year = today.month, today.year
        
        from calendar import monthrange
        period_start = datetime(year, month, 1).date()
        _, last_day = monthrange(year, month)
        period_end = datetime(year, month, last_day).date()
        
    elif view_type == 'year':
        year_offset = request.args.get('year_offset', 0, type=int)
        year = today.year + year_offset
        period_start = datetime(year, 1, 1).date()
        period_end = datetime(year, 12, 31).date()
        
    else:
        # Default to week view
        view_type = 'week'
        period_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        period_end = period_start + timedelta(days=4)

    # Only show groups and teachers that have schedule or workloads
    groups = db.session.query(Group).join(Workload).join(Schedule).distinct().order_by(Group.name).all()

    # Получаем преподавателей: основных из Workload + заменяющих из Schedule
    from sqlalchemy import union, select
    # Основные преподаватели (имеют workload с расписанием)
    main_teachers = db.session.query(Teacher.id).join(Workload).join(Schedule).distinct()
    # Заменяющие преподаватели
    substitute_teachers = db.session.query(Schedule.substitute_teacher_id).filter(
        Schedule.substitute_teacher_id.isnot(None)
    ).distinct()
    # Объединяем ID и получаем уникальных преподавателей
    all_teacher_ids = set([t[0] for t in main_teachers.all()] + [t[0] for t in substitute_teachers.all() if t[0]])
    teachers = Teacher.query.filter(Teacher.id.in_(all_teacher_ids)).order_by(Teacher.full_name).all()

    # Get schedule data
    schedules = []
    view_title = "Выберите группу или преподавателя"

    if group_id:
        group = Group.query.get(group_id)
        if group:
            if view_type == 'week':
                view_title = f"Группа: {group.name} • Неделя"
            elif view_type == 'month':
                month_names = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                              'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
                view_title = f"Группа: {group.name} • {month_names[period_start.month]} {period_start.year}"
            else:
                view_title = f"Группа: {group.name} • {period_start.year} год"
                
            # Добавляем загрузку связанных объектов для корректного отображения
            from sqlalchemy.orm import joinedload
            schedules = Schedule.query\
                .join(Workload)\
                .options(joinedload(Schedule.workload).joinedload(Workload.group))\
                .options(joinedload(Schedule.workload).joinedload(Workload.teacher))\
                .options(joinedload(Schedule.room))\
                .filter(
                    Workload.group_id == group_id,
                    Schedule.date >= period_start,
                    Schedule.date <= period_end
                ).order_by(Schedule.date, Schedule.pair_number).all()
    elif teacher_id:
        teacher = Teacher.query.get(teacher_id)
        if teacher:
            if view_type == 'week':
                view_title = f"Преподаватель: {teacher.full_name} • Неделя"
            elif view_type == 'month':
                month_names = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                              'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
                view_title = f"Преподаватель: {teacher.full_name} • {month_names[period_start.month]} {period_start.year}"
            else:
                view_title = f"Преподаватель: {teacher.full_name} • {period_start.year} год"

            # Добавляем загрузку связанных объектов для корректного отображения
            from sqlalchemy.orm import joinedload
            from sqlalchemy import or_

            # Показываем пары где преподаватель:
            # 1. Является основным учителем (Workload.teacher_id)
            # 2. Является заменяющим (Schedule.substitute_teacher_id)
            schedules = Schedule.query\
                .join(Workload)\
                .options(joinedload(Schedule.workload).joinedload(Workload.group))\
                .options(joinedload(Schedule.workload).joinedload(Workload.teacher))\
                .options(joinedload(Schedule.room))\
                .options(joinedload(Schedule.substitute_teacher))\
                .filter(
                    or_(
                        Workload.teacher_id == teacher_id,
                        Schedule.substitute_teacher_id == teacher_id
                    ),
                    Schedule.date >= period_start,
                    Schedule.date <= period_end
                ).order_by(Schedule.date, Schedule.pair_number).all()
            safe_print(f"DEBUG: Found {len(schedules)} schedules for teacher {teacher.full_name} (including substitutions)")

    # Build schedule grid and additional data based on view type
    schedule_grid = {}
    schedule_data = {}
    gup_info = {}
    
    if view_type == 'week':
        # Week view: grid by day/pair
        for s in schedules:
            day_idx = s.date.weekday()
            if day_idx < 5:  # Mon-Fri
                key = (day_idx, s.pair_number)
                schedule_grid[key] = s

        # Add GUP information for week view
        if group_id:
            current_date = period_start
            while current_date <= period_end:
                gup_record = GUP.query.filter(
                    GUP.group_id == group_id,
                    GUP.start_date <= current_date,
                    GUP.end_date >= current_date
                ).first()
                
                if gup_record:
                    day_idx = current_date.weekday()
                    if day_idx < 5:  # Mon-Fri only
                        gup_info[day_idx] = {
                            'activity_code': gup_record.activity_code,
                            'activity_name': gup_record.activity_name,
                            'week_number': gup_record.week_number
                        }
                current_date += timedelta(days=1)
                
    elif view_type == 'month':
        # Month view: group by dates
        from collections import defaultdict
        month_schedule_data = {}
        for s in schedules:
            date_str = s.date.strftime('%Y-%m-%d')
            if date_str not in month_schedule_data:
                month_schedule_data[date_str] = []
            month_schedule_data[date_str].append(s)
        schedule_data = month_schedule_data
            
    elif view_type == 'year':
        # Year view: group by months
        from collections import defaultdict
        year_schedule_data = {}
        for month in range(1, 13):
            month_schedules = [s for s in schedules if s.date.month == month]
            done_pairs = len([s for s in month_schedules if s.status in ['done', 'completed', 'substitution']])
            planned_pairs = len([s for s in month_schedules if s.status == 'planned'])
            total_pairs = len(month_schedules)
            
            year_schedule_data[month] = {
                'done_pairs': done_pairs,
                'planned_pairs': planned_pairs, 
                'total_pairs': total_pairs
            }
        schedule_data = year_schedule_data

    # Convert schedule objects to JSON-serializable dictionaries for year view
    schedules_for_json = []
    if schedules:
        for schedule in schedules:
            schedule_dict = {
                'id': schedule.id,
                'date': schedule.date.strftime('%Y-%m-%d'),
                'pair_number': schedule.pair_number,
                'status': schedule.status,
                'workload': {
                    'discipline': schedule.workload.discipline if schedule.workload else '',
                    'group': {
                        'name': schedule.workload.group.name if schedule.workload and schedule.workload.group else ''
                    } if schedule.workload else None,
                    'teacher': {
                        'full_name': schedule.workload.teacher.full_name if schedule.workload and schedule.workload.teacher else ''
                    } if schedule.workload else None
                },
                'room': {
                    'number': schedule.room.number if schedule.room else ''
                } if schedule.room else None,
                'notes': schedule.notes or ''
            }
            schedules_for_json.append(schedule_dict)

    return render_template('schedule/index.html',
                           groups=groups,
                           teachers=teachers,
                           selected_group=group_id,
                           selected_teacher=teacher_id,
                           view_type=view_type,
                           period_start=period_start,
                           period_end=period_end,
                           week_offset=week_offset,
                           view_title=view_title,
                           schedules=schedules,  # Keep original for server-side template logic
                           schedules_json=schedules_for_json,  # JSON-safe version for client-side
                           schedule_grid=schedule_grid,
                           schedule_data=schedule_data,
                           month_schedule_data=schedule_data if view_type == 'month' else {},
                           year_schedule_data=schedule_data if view_type == 'year' else {},
                           gup_info=gup_info,
                           pair_times=Config.PAIR_TIMES,
                           config=Config,  # Add full config for template
                           status_colors=Config.SCHEDULE_STATUS,
                           timedelta=timedelta,
                           # For backward compatibility
                           week_start=period_start,
                           week_end=period_end)


@bp.route('/generate', methods=['GET', 'POST'])
def generate():
    """Generate schedule for a group"""
    if request.method == 'POST':
        group_id = request.form.get('group_id', type=int)
        semester = request.form.get('semester', type=int)
        generation_mode = request.form.get('generation_mode', 'remaining')
        
        # Получаем дополнительные настройки
        room_ids = request.form.getlist('room_ids[]')
        room_priorities = request.form.getlist('room_priorities[]')
        room_reasons = request.form.getlist('room_reasons[]')
        
        preferred_days = request.form.getlist('preferred_days[]')
        preferred_pairs = request.form.getlist('preferred_pairs[]')
        repeat_interval = request.form.get('repeat_interval', 'weekly')
        follow_gup = bool(request.form.get('follow_gup'))

        if not group_id or not semester:
            flash('Выберите группу и семестр', 'error')
            return redirect(url_for('schedule.generate'))

        # Get current academic year
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            flash('Не установлен текущий учебный год', 'error')
            return redirect(url_for('schedule.generate'))

        # Generate schedule with selected mode
        safe_print(f"DEBUG: Starting generation for group {group_id}, semester {semester}, mode {generation_mode}")
        generator = ScheduleGenerator(group_id, semester, current_year.id, generation_mode)
        
        # Применяем дополнительные настройки
        # Сохраняем предпочтения аудиторий в базу данных (как в мастере)
        if room_ids and any(room_ids):  # Если выбраны аудитории
            # Очищаем старые предпочтения для группы
            RoomPreference.query.filter_by(group_id=group_id).delete()
            
            # Добавляем новые предпочтения  
            for i, room_id in enumerate(room_ids):
                if room_id:  # Если выбрана аудитория
                    priority = int(room_priorities[i]) if i < len(room_priorities) else 1
                    reason = room_reasons[i] if i < len(room_reasons) else ''
                    
                    preference = RoomPreference(
                        group_id=group_id,
                        room_id=room_id,
                        priority=priority,
                        reason=reason
                    )
                    db.session.add(preference)
            
            db.session.commit()
            
            # Загружаем предпочтения в генератор
            preferences = RoomPreference.query.filter_by(group_id=group_id).all()
            if hasattr(generator, 'set_room_preferences'):
                generator.set_room_preferences(preferences)
        
        # Устанавливаем настройки времени 
        if hasattr(generator, 'set_time_preferences'):
            time_settings = {
                'preferred_days': [int(d) for d in preferred_days] if preferred_days else [1,2,3,4,5],
                'preferred_pairs': [int(p) for p in preferred_pairs] if preferred_pairs else [1,2,3,4],
                'repeat_interval': repeat_interval,
                'follow_gup': follow_gup
            }
            generator.set_time_preferences(time_settings)
        
        success = generator.generate()
        result = generator.get_result()
        safe_print(f"DEBUG: Generation result - success: {success}, created: {result.get('created_count', 0)}")

        # Принудительно обновляем счетчики часов всегда, независимо от успеха
        # Даже если генерация частично неудачна, занятия могли быть созданы
        from app.services.scheduler import update_hours_completed
        workloads_to_update = Workload.query.filter_by(
            group_id=group_id,
            semester=semester,
            academic_year_id=current_year.id
        ).all()
        
        safe_print(f"DEBUG: Updating {len(workloads_to_update)} workloads for group {group_id}, semester {semester}")
        for wl in workloads_to_update:
            old_completed = wl.hours_completed
            update_hours_completed(wl.id)
            # Перечитываем после обновления
            wl_updated = Workload.query.get(wl.id)
            safe_print(f"DEBUG: {wl.discipline} - was: {old_completed}h, now: {wl_updated.hours_completed}h, total: {wl.total_hours}h")

        # Показываем детальный результат генерации
        if result["created_count"] > 0:
            today = date.today()
            
            # Получаем созданные пары для статистики
            new_schedules = Schedule.query.join(Workload).filter(
                Workload.group_id == group_id,
                Schedule.status == 'planned',
                Schedule.date >= today
            ).all()
            
            # Группируем по дисциплинам
            by_discipline = {}
            for s in new_schedules:
                disc = s.workload.discipline[:30]
                if disc not in by_discipline:
                    by_discipline[disc] = 0
                by_discipline[disc] += 1
            
            # Период созданных пар
            dates = sorted(set([s.date for s in new_schedules]))
            date_range = f"{dates[0]} — {dates[-1]}" if len(dates) > 1 else str(dates[0]) if dates else ""
            
            # Формируем детальное сообщение
            success_msg = f'✅ Генерация завершена: создано {result["created_count"]} пар ({result["created_count"] * 2}ч)'
            if result["deleted_count"] > 0:
                success_msg += f', удалено {result["deleted_count"]} старых'
            
            flash(success_msg, 'success')
            
            if date_range:
                flash(f'📅 Период: {date_range}', 'info')
            
            if by_discipline:
                disc_info = ', '.join([f'{disc} ({count})' for disc, count in list(by_discipline.items())[:3]])
                if len(by_discipline) > 3:
                    disc_info += f' и еще {len(by_discipline) - 3}'
                flash(f'📚 По дисциплинам: {disc_info}', 'info')
            
            flash('💡 Совет: Проверьте расписание, используя навигацию по неделям →', 'info')
        
        if not success:
            if result["created_count"] > 0:
                flash(f'⚠️ Частичная генерация: создано {result["created_count"]} пар из возможных', 'warning')
            else:
                flash('❌ Генерация не создала ни одной пары', 'error')
            
            for error in result.get('errors', []):
                flash(f'Ошибка: {error}', 'error')
        
        # Show warnings if any
        for warning in result.get('warnings', []):
            # Определяем тип предупреждения для разного отображения
            if warning.startswith('⚠️'):
                flash(warning, 'warning')
            elif warning.startswith('💡'):
                flash(warning, 'info')
            elif warning.startswith('✅'):
                flash(warning, 'success')
            else:
                flash(warning, 'warning')

        # Отправка данных в Google Sheets если включена интеграция
        if current_app.config.get('GOOGLE_SHEETS_UPDATE_ON_GENERATION') and result["created_count"] > 0:
            try:
                from app.services.google_sheets_webhook import send_group_schedule_to_sheets
                webhook_result = send_group_schedule_to_sheets(group_id)
                
                if webhook_result.get('success'):
                    safe_print(f"DEBUG: Data sent to Google Sheets. Records: {webhook_result.get('records_sent', 0)}")
                else:
                    safe_print(f"WARNING: Google Sheets error: {webhook_result.get('error')}")

            except Exception as e:
                safe_print(f"WARNING: Failed to send to Google Sheets: {e}")

        return redirect(url_for('schedule.index', group_id=group_id))
    
    # GET запрос - показываем форму генерации
    # Get groups with detailed workload information
    from sqlalchemy import func, case
    
    groups_data = []
    groups_with_workload = db.session.query(Group).join(Workload).distinct().order_by(Group.name).all()
    
    # Get available semesters with remaining workloads
    # Используем подзапрос для точного расчета остатков
    from sqlalchemy import text
    available_semesters = db.session.query(
        Workload.semester.label('semester')
    ).filter(
        text("""
        total_hours > COALESCE(
            (SELECT COUNT(*) * 2 FROM schedule s 
             WHERE s.workload_id = workload.id 
             AND s.status IN ('done', 'completed', 'substitution')
            ), 0
        )""")
    ).distinct().order_by(Workload.semester).all()
    
    available_semester_numbers = [s.semester for s in available_semesters if s.semester]
    
    for group in groups_with_workload:
        # Get workload summary for this group using actual schedule data
        workloads_for_group = db.session.query(Workload).filter_by(group_id=group.id).all()
        
        total_workloads = len(workloads_for_group)
        total_hours = sum(wl.total_hours for wl in workloads_for_group)
        completed_hours = 0
        remaining_hours = 0
        active_workloads = 0
        remaining_disciplines = []
        group_semester_numbers = set()
        
        for wl in workloads_for_group:
            # Считаем фактически выполненные часы из расписания (без planned)
            completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status.in_(['done', 'completed', 'substitution'])
            ).count()
            actual_completed_hours = completed_pairs * 2
            
            completed_hours += min(actual_completed_hours, wl.total_hours)
            wl_remaining = max(0, wl.total_hours - actual_completed_hours)
            
            if wl_remaining > 0:
                remaining_hours += wl_remaining
                active_workloads += 1
                remaining_disciplines.append(wl)
                group_semester_numbers.add(wl.semester)
        
        group_semester_numbers = sorted(list(group_semester_numbers))
        
        groups_data.append({
            'group': group,
            'total_workloads': total_workloads,
            'total_hours': total_hours,
            'completed_hours': completed_hours,
            'remaining_hours': remaining_hours,
            'active_workloads': active_workloads,
            'remaining_disciplines': remaining_disciplines[:5],  # Показываем первые 5
            'available_semesters': group_semester_numbers
        })
    
    # Получаем информацию о семестрах ГУП для подсказок
    semester_gup_info = {}
    from sqlalchemy import distinct
    
    for semester in available_semester_numbers:
        # Определяем период ГУП по семестру
        if semester in [1, 3, 5, 7]:
            gup_period = "1-й семестр (сент-янв)"
        else:
            gup_period = "2-й семестр (февр-июнь)"
        
        # Получаем примерные месяцы из ГУП
        gup_records = db.session.query(GUP.activity_name, GUP.start_date, GUP.end_date).filter(
            GUP.activity_code.in_(['', None, 'УП', 'ОТ', 'ӨО'])
        ).distinct().limit(3).all()
        
        semester_gup_info[semester] = {
            'period': gup_period,
            'sample_dates': gup_records
        }

    # Получаем все аудитории для настроек предпочтений
    rooms = Room.query.order_by(Room.number).all()
    
    return render_template('schedule/generate.html', 
                         groups_data=groups_data, 
                         available_semesters=available_semester_numbers,
                         semester_gup_info=semester_gup_info,
                         rooms=rooms)


@bp.route('/generate_smart', methods=['GET', 'POST'])
def generate_smart():
    """Smart schedule generation for a group"""
    if request.method == 'POST':
        group_id = request.form.get('group_id', type=int)
        semester = request.form.get('semester', type=int)
        workload_ids = request.form.getlist('workload_ids')  # Multiple selection
        
        # Если выбрано "all", генерируем для всех нагрузок
        if 'all' in workload_ids:
            workload_ids = []  # Empty list means all workloads
        else:
            workload_ids = [int(wid) for wid in workload_ids if wid and wid != 'all']
        
        if not group_id or not semester:
            flash('Выберите группу и семестр', 'error')
            return redirect(url_for('schedule.generate_smart'))
            
        # Get current academic year
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            flash('Не установлен текущий учебный год', 'error')
            return redirect(url_for('schedule.generate_smart'))
        
        # Generate schedule with smart generator
        safe_print(f"Starting smart generation for group {group_id}, semester {semester}, workloads: {workload_ids}")
        generator = SmartScheduleGenerator(group_id, semester, current_year.id, workload_ids=workload_ids)
        
        success = generator.generate()
        
        # Show results
        if success:
            pairs_count = len(generator.created_schedules)
            hours_count = pairs_count * 2
            flash(f'Умная генерация завершена! Создано {pairs_count} пар ({hours_count} часов), качество: {generator.quality_score}/100', 'success')

            # Save results
            if generator.created_schedules:
                if generator.save_results():
                    flash(f'Сохранено {pairs_count} новых пар ({hours_count} часов)', 'info')
                else:
                    flash('Ошибка сохранения результатов', 'error')
        else:
            flash('Ошибка умной генерации', 'error')
        
        # Show warnings and errors
        for warning in generator.warnings:
            flash(f'Предупреждение: {warning}', 'warning')
        for error in generator.errors:
            flash(f'Ошибка: {error}', 'error')
        
        return redirect(url_for('schedule.generate_smart'))
    
    # GET request - show form
    groups = Group.query.all()
    return render_template('schedule/generate_smart.html', groups=groups)


@bp.route('/generate_all_remaining', methods=['POST'])  
def generate_all_remaining():
    """Массовая генерация остатков для всех групп"""
    generation_mode = request.form.get('generation_mode', 'remaining')
    
    # Получаем все группы с остатками
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    if not current_year:
        flash('Не установлен текущий учебный год', 'error')
        return redirect(url_for('schedule.generate'))
    
    groups_with_remaining = []
    all_groups = db.session.query(Group).join(Workload).distinct().all()
    
    for group in all_groups:
        workloads = Workload.query.filter_by(group_id=group.id, academic_year_id=current_year.id).all()
        
        remaining_hours = 0
        for wl in workloads:
            # Фактический подсчет из Schedule
            completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status.in_(['done', 'completed', 'substitution'])
            ).count()
            actual_completed_hours = completed_pairs * 2
            wl_remaining = max(0, wl.total_hours - actual_completed_hours)
            remaining_hours += wl_remaining
        
        if remaining_hours > 0:
            groups_with_remaining.append({
                'group': group,
                'remaining_hours': remaining_hours,
                'semesters': list(set([wl.semester for wl in workloads if (wl.total_hours - (Schedule.query.filter_by(workload_id=wl.id).filter(Schedule.status.in_(['done', 'completed', 'substitution'])).count() * 2)) > 0]))
            })
    
    if not groups_with_remaining:
        flash('Нет групп с остаточными часами для генерации', 'info')
        return redirect(url_for('schedule.generate'))
    
    # Статистика массовой генерации
    total_generated = 0
    total_errors = 0
    total_warnings = 0
    generation_results = []
    
    flash(f'🚀 Начинаем массовую генерацию для {len(groups_with_remaining)} групп...', 'info')
    
    for item in groups_with_remaining:
        group = item['group']
        semesters = item['semesters']
        
        # Генерируем для каждого семестра группы
        for semester in semesters:
            try:
                generator = ScheduleGenerator(group.id, semester, current_year.id, generation_mode)
                success = generator.generate()
                result = generator.get_result()
                
                generation_results.append({
                    'group': group,
                    'semester': semester, 
                    'success': success,
                    'result': result
                })
                
                if result['created_count'] > 0:
                    total_generated += result['created_count']
                
                total_errors += len(result.get('errors', []))
                total_warnings += len(result.get('warnings', []))
                
                # Обновляем hours_completed
                workloads = Workload.query.filter_by(
                    group_id=group.id,
                    semester=semester,
                    academic_year_id=current_year.id
                ).all()
                
                for wl in workloads:
                    update_hours_completed(wl.id)
                    
            except Exception as e:
                flash(f'❌ Ошибка генерации для {group.name} семестр {semester}: {str(e)}', 'error')
                total_errors += 1
    
    # Сводный отчет
    flash(f'🎯 Массовая генерация завершена:', 'success')
    flash(f'📊 Создано пар: {total_generated} ({total_generated * 2}ч)', 'success')
    
    if total_warnings > 0:
        flash(f'⚠️ Предупреждений: {total_warnings}', 'warning')
    
    if total_errors > 0:
        flash(f'❌ Ошибок: {total_errors}', 'error')
    
    # Детальная статистика по группам
    successful_groups = len([r for r in generation_results if r['result']['created_count'] > 0])
    if successful_groups > 0:
        flash(f'✅ Успешно обработано групп: {successful_groups} из {len(groups_with_remaining)}', 'success')
    
    # Показать проблемные дисциплины
    problematic_disciplines = []
    for result in generation_results:
        for error in result['result'].get('errors', []):
            if 'НЕ РАЗМЕЩЕНО' in error:
                problematic_disciplines.append(f"{result['group'].name}: {error}")
    
    if problematic_disciplines and len(problematic_disciplines) <= 10:
        for disc_error in problematic_disciplines[:5]:
            flash(disc_error, 'warning') 
        if len(problematic_disciplines) > 5:
            flash(f'... и еще {len(problematic_disciplines) - 5} проблемных дисциплин', 'warning')
    elif len(problematic_disciplines) > 10:
        flash(f'⚠️ Обнаружено {len(problematic_disciplines)} проблемных дисциплин. Проверьте настройки нагрузки.', 'warning')
    
    # Отправка полного расписания в Google Sheets после массовой генерации
    if current_app.config.get('GOOGLE_SHEETS_UPDATE_ON_GENERATION') and total_generated > 0:
        try:
            from app.services.google_sheets_webhook import send_full_schedule_to_sheets
            webhook_result = send_full_schedule_to_sheets()
            
            if webhook_result.get('success'):
                safe_print(f"DEBUG: Full schedule sent to Google Sheets. Records: {webhook_result.get('records_sent', 0)}")
                flash('📊 Данные отправлены в Google Sheets', 'info')
            else:
                safe_print(f"WARNING: Google Sheets error: {webhook_result.get('error')}")

        except Exception as e:
            safe_print(f"WARNING: Failed to send to Google Sheets: {e}")
    
    return redirect(url_for('schedule.generate'))


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """Edit schedule entry"""
    schedule = Schedule.query.get_or_404(id)

    if request.method == 'POST':
        # Check if period is closed
        if is_period_closed(schedule.date):
            flash('Нельзя редактировать расписание в закрытом периоде. Откройте период в разделе "Периоды" для внесения изменений.', 'error')
            return redirect(url_for('schedule.index', group_id=schedule.workload.group_id))

        schedule.room_id = request.form.get('room_id', type=int)
        schedule.pair_number = request.form.get('pair_number', type=int)
        schedule.status = request.form.get('status')
        schedule.notes = request.form.get('notes')

        sub_teacher_id = request.form.get('substitute_teacher_id', type=int)
        schedule.substitute_teacher_id = sub_teacher_id if sub_teacher_id else None

        db.session.commit()

        # Update hours completed
        update_hours_completed(schedule.workload_id)

        flash('Запись обновлена', 'success')
        return redirect(url_for('schedule.index', group_id=schedule.workload.group_id))

    rooms = Room.query.order_by(Room.number).all()
    teachers = Teacher.query.order_by(Teacher.full_name).all()

    return render_template('schedule/edit.html',
                           schedule=schedule,
                           rooms=rooms,
                           teachers=teachers,
                           pair_times=Config.PAIR_TIMES,
                           statuses=Config.SCHEDULE_STATUS)


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """Delete schedule entry"""
    schedule = Schedule.query.get_or_404(id)
    
    # Check if period is closed
    if is_period_closed(schedule.date):
        flash('Нельзя удалять расписание в закрытом периоде. Откройте период в разделе "Периоды" для внесения изменений.', 'error')
        return redirect(url_for('schedule.index', group_id=schedule.workload.group_id))
    
    group_id = schedule.workload.group_id
    db.session.delete(schedule)
    db.session.commit()
    flash('Запись удалена', 'success')
    return redirect(url_for('schedule.index', group_id=group_id))


@bp.route('/progress/<task_id>')
def generation_progress_status(task_id):
    """API endpoint для отслеживания прогресса генерации"""
    progress = generation_progress.get(task_id, {
        'current': 0,
        'total': 0,
        'status': 'not_found',
        'message': 'Задача не найдена'
    })
    return jsonify(progress)


@bp.route('/generate_with_progress', methods=['POST'])
def generate_with_progress():
    """Запуск массовой генерации с отслеживанием прогресса"""
    task_id = str(uuid.uuid4())
    
    # Инициализируем прогресс
    generation_progress[task_id] = {
        'current': 0,
        'total': 0,
        'status': 'starting',
        'message': 'Подготовка к генерации...'
    }
    
    # Запускаем генерацию в отдельном потоке
    from flask import current_app
    thread = threading.Thread(
        target=run_generation_with_progress,
        args=(current_app._get_current_object(), task_id, request.form.get('generation_mode', 'remaining'))
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'task_id': task_id, 'status': 'started'})


@bp.route('/generate_single_with_progress', methods=['POST'])
def generate_single_with_progress():
    """Запуск генерации одной группы с отслеживанием прогресса"""
    task_id = str(uuid.uuid4())
    
    group_id = request.form.get('group_id', type=int)
    semester = request.form.get('semester', type=int)
    generation_mode = request.form.get('generation_mode', 'remaining')
    
    if not group_id or not semester:
        return jsonify({'status': 'error', 'message': 'Не выбрана группа или семестр'})
    
    # Инициализируем прогресс
    generation_progress[task_id] = {
        'current': 0,
        'total': 1,
        'status': 'starting',
        'message': 'Подготовка к генерации...'
    }
    
    # Запускаем генерацию в отдельном потоке
    from flask import current_app
    thread = threading.Thread(
        target=run_single_generation_with_progress,
        args=(current_app._get_current_object(), task_id, group_id, semester, generation_mode)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'task_id': task_id, 'status': 'started'})


def run_generation_with_progress(app, task_id, generation_mode):
    """Выполняет генерацию с обновлением прогресса"""
    with app.app_context():
        try:
            # Инициализируем прогресс если он еще не существует
            if task_id not in generation_progress:
                generation_progress[task_id] = {
                    'current': 0, 'total': 0, 'status': 'starting',
                    'message': 'Подготовка к генерации...'
                }
            
            # Получаем все группы с остатками
            current_year = AcademicYear.query.filter_by(is_current=True).first()
            if not current_year:
                generation_progress[task_id] = {
                    'current': 0, 'total': 0, 'status': 'error',
                    'message': 'Не установлен текущий учебный год'
                }
                return

            groups_with_remaining = []
            all_groups = db.session.query(Group).join(Workload).distinct().all()
            
            # Подсчитываем общее количество работы
            generation_progress[task_id]['message'] = 'Анализ групп с остатками...'
            
            for group in all_groups:
                workloads = Workload.query.filter_by(group_id=group.id, academic_year_id=current_year.id).all()
                
                remaining_hours = 0
                for wl in workloads:
                    completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                        Schedule.status.in_(['done', 'completed', 'substitution'])
                    ).count()
                    actual_completed_hours = completed_pairs * 2
                    wl_remaining = max(0, wl.total_hours - actual_completed_hours)
                    remaining_hours += wl_remaining
                
                if remaining_hours > 0:
                    groups_with_remaining.append({
                        'group': group,
                        'remaining_hours': remaining_hours
                    })

            if not groups_with_remaining:
                generation_progress[task_id] = {
                    'current': 0, 'total': 0, 'status': 'completed',
                    'message': 'Нет групп с остаточными часами для генерации'
                }
                return

            total_groups = len(groups_with_remaining)
            generation_progress[task_id]['total'] = total_groups
            generation_progress[task_id]['status'] = 'running'
            
            # Генерируем для каждой группы
            total_generated = 0
            for i, item in enumerate(groups_with_remaining):
                group = item['group']
                
                generation_progress[task_id].update({
                    'current': i + 1,
                    'message': f'Генерация для группы {group.name}...'
                })
                
                # Получаем все доступные семестры для этой группы
                workloads = Workload.query.filter_by(group_id=group.id, academic_year_id=current_year.id).all()
                available_semesters = sorted(set(wl.semester for wl in workloads))
                
                group_generated = 0
                for semester in available_semesters:
                    try:
                        generator = ScheduleGenerator(group.id, semester, current_year.id, generation_mode)
                        success = generator.generate()
                        result = generator.get_result()
                        group_generated += result.get('created_count', 0)
                        
                    except Exception as e:
                        generation_progress[task_id].update({
                            'message': f'Ошибка при генерации для группы {group.name}, семестр {semester}: {str(e)}'
                        })
                        continue
                
                total_generated += group_generated
                
                # Небольшая задержка для демонстрации прогресса
                time.sleep(0.5)
            
            # Завершение - подробная статистика
            generation_progress[task_id] = {
                'current': total_groups,
                'total': total_groups,
                'status': 'completed',
                'message': f'Массовая генерация завершена!\n• Обработано групп: {total_groups}\n• Всего создано занятий: {total_generated}'
            }
            
        except Exception as e:
            generation_progress[task_id] = {
                'current': 0, 'total': 0, 'status': 'error',
                'message': f'Ошибка: {str(e)}'
            }


def run_single_generation_with_progress(app, task_id, group_id, semester, generation_mode):
    """Выполняет генерацию для одной группы с обновлением прогресса"""
    with app.app_context():
        try:
            # Получаем текущий учебный год
            current_year = AcademicYear.query.filter_by(is_current=True).first()
            if not current_year:
                generation_progress[task_id] = {
                    'current': 0, 'total': 1, 'status': 'error',
                    'message': 'Не установлен текущий учебный год'
                }
                return

            # Получаем группу
            group = Group.query.get(group_id)
            if not group:
                generation_progress[task_id] = {
                    'current': 0, 'total': 1, 'status': 'error',
                    'message': 'Группа не найдена'
                }
                return

            # Обновляем статус
            generation_progress[task_id].update({
                'current': 0,
                'total': 1,
                'status': 'running',
                'message': f'Генерация расписания для группы {group.name}, семестр {semester}...'
            })

            # Выполняем генерацию
            generator = ScheduleGenerator(group_id, semester, current_year.id, generation_mode)
            success = generator.generate()
            result = generator.get_result()
            
            # Формируем подробное сообщение о результатах
            created = result.get("created_count", 0)
            deleted = result.get("deleted_count", 0)
            errors = result.get("errors", [])
            warnings = result.get("warnings", [])
            
            message_parts = []
            message_parts.append(f'Создано: {created} занятий')
            if deleted > 0:
                message_parts.append(f'Удалено: {deleted} занятий')
            if errors:
                message_parts.append(f'Ошибок: {len(errors)}')
            if warnings:
                message_parts.append(f'Предупреждений: {len(warnings)}')
            
            detailed_message = f'Генерация завершена для группы {group.name}, семестр {semester}!\n• ' + '\n• '.join(message_parts)
            
            # Завершение
            generation_progress[task_id] = {
                'current': 1,
                'total': 1,
                'status': 'completed',
                'message': detailed_message,
                'result': result
            }
            
        except Exception as e:
            generation_progress[task_id] = {
                'current': 0, 'total': 1, 'status': 'error',
                'message': f'Ошибка: {str(e)}'
            }


@bp.route('/mark-week-done', methods=['POST'])
def mark_week_done():
    """Mark all schedule entries for a week as done"""
    group_id = request.form.get('group_id', type=int)
    week_start = datetime.strptime(request.form.get('week_start'), '%Y-%m-%d').date()
    week_end = week_start + timedelta(days=4)

    # Check period protection for this week
    if is_period_closed(week_start):
        flash('Невозможно изменить расписание в закрытом периоде', 'error')
        return redirect(url_for('schedule.index', group_id=group_id))

    schedules = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date >= week_start,
        Schedule.date <= week_end,
        Schedule.status == 'planned'
    ).all()

    for s in schedules:
        s.status = 'done'
        update_hours_completed(s.workload_id)

    db.session.commit()
    flash(f'Отмечено проведёнными: {len(schedules)} пар', 'success')
    return redirect(url_for('schedule.index', group_id=group_id))


@bp.route('/mark-week-planned', methods=['POST'])
def mark_week_planned():
    """Mark all schedule entries for a week as planned (reverse of done)"""
    group_id = request.form.get('group_id', type=int)
    week_start = datetime.strptime(request.form.get('week_start'), '%Y-%m-%d').date()
    week_end = week_start + timedelta(days=4)

    # Check period protection for this week
    if is_period_closed(week_start):
        flash('Невозможно изменить расписание в закрытом периоде', 'error')
        return redirect(url_for('schedule.index', group_id=group_id))

    schedules = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date >= week_start,
        Schedule.date <= week_end,
        Schedule.status == 'done'
    ).all()

    for s in schedules:
        s.status = 'planned'
        update_hours_completed(s.workload_id)

    db.session.commit()
    flash(f'Возвращено в запланированные: {len(schedules)} пар', 'success')
    return redirect(url_for('schedule.index', group_id=group_id))


@bp.route('/mark-month-done', methods=['POST'])
def mark_month_done():
    """Mark ALL schedule entries for the entire month as done (all groups, all teachers)"""
    import calendar

    month = request.form.get('month', type=int)
    year = request.form.get('year', type=int)

    if not month or not year:
        flash('Не указан месяц или год', 'error')
        return redirect(url_for('schedule.index'))

    # Get first and last day of month
    _, last_day = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)

    # Find all planned schedules for the month (across ALL groups and teachers)
    schedules = Schedule.query.filter(
        Schedule.date >= month_start,
        Schedule.date <= month_end,
        Schedule.status == 'planned'
    ).all()

    # Mark all as done
    updated_workloads = set()
    for s in schedules:
        s.status = 'done'
        updated_workloads.add(s.workload_id)

    # Update hours_completed for all affected workloads
    for wl_id in updated_workloads:
        update_hours_completed(wl_id)

    db.session.commit()

    months_ru = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }

    flash(f'Отмечено проведёнными: {len(schedules)} пар за {months_ru[month]} {year}', 'success')
    return redirect(request.referrer or url_for('schedule.index'))


@bp.route('/api/available-rooms')
def api_available_rooms():
    """API: Get available rooms for a time slot"""
    date_str = request.args.get('date')
    pair_number = request.args.get('pair', type=int)

    if not date_str or not pair_number:
        return jsonify([])

    date = datetime.strptime(date_str, '%Y-%m-%d').date()
    rooms = get_available_rooms(date, pair_number)

    return jsonify([{'id': r.id, 'number': r.number} for r in rooms])


@bp.route('/api/group-schedule-conflicts')
def api_group_schedule_conflicts():
    """API: Check if group has conflicts for a specific date and time"""
    group_id = request.args.get('group_id', type=int)
    date_str = request.args.get('date')
    pair_number = request.args.get('pair_number', type=int)
    exclude_workload_id = request.args.get('exclude_workload_id', type=int)  # Для редактирования

    if not all([group_id, date_str, pair_number]):
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    # Проверяем занятость группы
    query = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date == date,
        Schedule.pair_number == pair_number
    )
    
    # Исключаем конкретную нагрузку (для редактирования существующей записи)
    if exclude_workload_id:
        query = query.filter(Schedule.workload_id != exclude_workload_id)
    
    existing_schedule = query.first()
    
    if existing_schedule:
        return jsonify({
            'has_conflict': True,
            'conflict_info': {
                'discipline': existing_schedule.workload.discipline,
                'teacher': existing_schedule.workload.teacher.full_name if existing_schedule.workload.teacher else 'Не указан',
                'room': existing_schedule.room.number if existing_schedule.room else 'Не указана',
                'status': existing_schedule.status
            }
        })
    else:
        return jsonify({'has_conflict': False})


@bp.route('/api/teacher-schedule-conflicts')
def api_teacher_schedule_conflicts():
    """API: Check if teacher has conflicts for a specific date and time"""
    teacher_id = request.args.get('teacher_id', type=int)
    date_str = request.args.get('date')
    pair_number = request.args.get('pair_number', type=int)
    exclude_schedule_id = request.args.get('exclude_schedule_id', type=int)

    if not all([teacher_id, date_str, pair_number]):
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    # Проверяем занятость преподавателя
    query = Schedule.query.join(Workload).filter(
        Workload.teacher_id == teacher_id,
        Schedule.date == date,
        Schedule.pair_number == pair_number
    )
    
    if exclude_schedule_id:
        query = query.filter(Schedule.id != exclude_schedule_id)
    
    existing_schedule = query.first()
    
    if existing_schedule:
        return jsonify({
            'has_conflict': True,
            'conflict_info': {
                'discipline': existing_schedule.workload.discipline,
                'group': existing_schedule.workload.group.name,
                'room': existing_schedule.room.number if existing_schedule.room else 'Не указана',
                'status': existing_schedule.status
            }
        })
    else:
        return jsonify({'has_conflict': False})


@bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create schedule entry from workload (manual)"""
    if request.method == 'POST':
        workload_id = request.form.get('workload_id', type=int)
        date_str = request.form.get('date')
        pair_number = request.form.get('pair_number', type=int)
        room_id = request.form.get('room_id', type=int)
        status = request.form.get('status', 'planned')

        if not all([workload_id, date_str, pair_number]):
            flash('Заполните все обязательные поля', 'error')
            return redirect(url_for('schedule.create'))

        workload = Workload.query.get(workload_id)
        if not workload:
            flash('Нагрузка не найдена', 'error')
            return redirect(url_for('schedule.create'))

        schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Check if period is closed
        if is_period_closed(schedule_date):
            flash('Нельзя создавать расписание в закрытом периоде. Откройте период в разделе "Периоды" для внесения изменений.', 'error')
            return redirect(url_for('schedule.create', workload_id=workload_id))

        # Check conflicts
        from app.services.scheduler import check_teacher_conflict, check_room_conflict, check_group_conflict

        if check_teacher_conflict(workload.teacher_id, schedule_date, pair_number):
            flash(f'Конфликт: преподаватель {workload.teacher.full_name} уже занят на этой паре', 'error')
            return redirect(url_for('schedule.create', workload_id=workload_id))

        if check_group_conflict(workload.group_id, schedule_date, pair_number):
            flash(f'Конфликт: группа {workload.group.name} уже занята на этой паре', 'error')
            return redirect(url_for('schedule.create', workload_id=workload_id))

        if room_id and check_room_conflict(room_id, schedule_date, pair_number):
            flash('Конфликт: аудитория уже занята на этой паре', 'error')
            return redirect(url_for('schedule.create', workload_id=workload_id))

        schedule = Schedule(
            workload_id=workload_id,
            room_id=room_id,
            date=schedule_date,
            pair_number=pair_number,
            status=status
        )
        db.session.add(schedule)
        db.session.commit()

        # Update hours if status is done
        if status in ['done', 'completed']:
            update_hours_completed(workload_id)

        flash('Пара добавлена в расписание', 'success')
        return redirect(url_for('schedule.index', group_id=workload.group_id))

    # GET - show form
    workload_id = request.args.get('workload_id', type=int)
    group_id = request.args.get('group_id', type=int)

    # Get workloads with remaining hours
    query = Workload.query

    if workload_id:
        selected_workload = Workload.query.get(workload_id)
    else:
        selected_workload = None

    if group_id:
        query = query.filter_by(group_id=group_id)

    # Only show workloads with remaining hours
    workloads = query.all()
    workloads_with_remaining = [
        {
            'workload': wl,
            'remaining': wl.total_hours - wl.hours_completed,
            'remaining_pairs': (wl.total_hours - wl.hours_completed) // 2
        }
        for wl in workloads if wl.total_hours > wl.hours_completed
    ]

    groups = Group.query.order_by(Group.name).all()
    rooms = Room.query.order_by(Room.number).all()

    return render_template('schedule/create.html',
                           workloads=workloads_with_remaining,
                           selected_workload=selected_workload,
                           groups=groups,
                           rooms=rooms,
                           selected_group=group_id,
                           pair_times=Config.PAIR_TIMES,
                           statuses=Config.SCHEDULE_STATUS)


@bp.route('/api/workloads')
def api_workloads():
    """API: Get workloads for a group with remaining hours"""
    group_id = request.args.get('group_id', type=int)

    if not group_id:
        return jsonify([])

    workloads = Workload.query.filter_by(group_id=group_id).all()

    result = []
    for wl in workloads:
        remaining = wl.total_hours - wl.hours_completed
        if remaining > 0:
            result.append({
                'id': wl.id,
                'discipline': wl.discipline[:50],
                'teacher': wl.teacher.full_name if wl.teacher else '-',
                'teacher_id': wl.teacher_id,
                'total_hours': wl.total_hours,
                'completed': wl.hours_completed,
                'remaining': remaining,
                'remaining_pairs': remaining // 2
            })

    return jsonify(result)


# МАРШРУТЫ ДЛЯ УПРАВЛЕНИЯ ИЗМЕНЕНИЯМИ В РАСПИСАНИИ

@bp.route('/substitute', methods=['POST'])
def create_substitution():
    """Создать замену преподавателя"""
    try:
        data = request.get_json()
        safe_print(f"DEBUG: create_substitution called with data: {data}")
        
        # Check period protection
        schedule = Schedule.query.get(data['schedule_id'])
        if schedule and is_period_closed(schedule.date):
            return jsonify({'success': False, 'error': 'Невозможно изменить расписание в закрытом периоде'}), 403
        
        result = ScheduleChangeService.create_substitution(
            schedule_id=data['schedule_id'],
            substitute_teacher_id=data['substitute_teacher_id'],
            reason=data['reason'],
            changed_by=data.get('changed_by', 'Пользователь'),
            notes=data.get('notes')
        )
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(f"Ошибка: {result['error']}", 'error')
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@bp.route('/reschedule', methods=['POST'])
def reschedule_class():
    """Перенести занятие"""
    try:
        data = request.get_json()
        
        # Check period protection for original schedule
        schedule = Schedule.query.get(data['schedule_id'])
        if schedule and is_period_closed(schedule.date):
            return jsonify({'success': False, 'error': 'Невозможно изменить расписание в закрытом периоде'}), 403
        
        # Парсим новую дату
        try:
            new_date = datetime.strptime(data['new_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'error': 'Неверный формат даты'}), 400
        
        # Check period protection for new date
        if is_period_closed(new_date):
            return jsonify({'success': False, 'error': 'Невозможно перенести в закрытый период'}), 403
        
        result = ScheduleChangeService.reschedule_class(
            schedule_id=data['schedule_id'],
            new_date=new_date,
            new_pair_number=data['new_pair_number'],
            new_room_id=data.get('new_room_id'),
            reason=data['reason'],
            changed_by=data.get('changed_by', 'Пользователь'),
            notes=data.get('notes')
        )
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(f"Ошибка: {result['error']}", 'error')
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@bp.route('/cancel', methods=['POST'])
def cancel_class():
    """Отменить занятие"""
    try:
        data = request.get_json()
        
        # Check period protection
        schedule = Schedule.query.get(data['schedule_id'])
        if schedule and is_period_closed(schedule.date):
            return jsonify({'success': False, 'error': 'Невозможно отменить занятие в закрытом периоде'}), 403
        
        result = ScheduleChangeService.cancel_class(
            schedule_id=data['schedule_id'],
            reason=data['reason'],
            changed_by=data.get('changed_by', 'Пользователь'),
            return_to_workload=data.get('return_to_workload', True),
            notes=data.get('notes'),
            free_slot=data.get('free_slot') == 'true'
        )
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(f"Ошибка: {result['error']}", 'error')
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@bp.route('/restore', methods=['POST'])
def restore_class():
    """Восстановить занятие"""
    try:
        data = request.get_json()
        
        # Check period protection
        schedule = Schedule.query.get(data['schedule_id'])
        if schedule and is_period_closed(schedule.date):
            return jsonify({'success': False, 'error': 'Невозможно восстановить занятие в закрытом периоде'}), 403
        
        result = ScheduleChangeService.restore_class(
            schedule_id=data['schedule_id'],
            changed_by=data.get('changed_by', 'Пользователь'),
            notes=data.get('notes')
        )
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(f"Ошибка: {result['error']}", 'error')
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@bp.route('/delete_single', methods=['POST'])
def delete_single():
    """Удалить одну пару (API)"""
    try:
        data = request.get_json()
        schedule_id = data.get('schedule_id')

        schedule = Schedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'success': False, 'error': 'Запись не найдена'}), 404

        # Check period protection
        if is_period_closed(schedule.date):
            return jsonify({'success': False, 'error': 'Невозможно удалить занятие в закрытом периоде'}), 403

        # Store info for response
        discipline = schedule.workload.discipline if schedule.workload else 'N/A'
        date_str = schedule.date.strftime('%d.%m.%Y')
        pair_num = schedule.pair_number

        # Удаляем связанные записи schedule_changes
        ScheduleChange.query.filter_by(schedule_id=schedule.id).delete()
        ScheduleChange.query.filter_by(related_schedule_id=schedule.id).delete()

        # Очищаем ссылки в других записях расписания
        Schedule.query.filter_by(original_schedule_id=schedule.id).update({'original_schedule_id': None})
        Schedule.query.filter_by(rescheduled_to_id=schedule.id).update({'rescheduled_to_id': None})

        # Удаляем связанные vacant_hours
        from app.models import VacantHours
        VacantHours.query.filter_by(schedule_id=schedule.id).delete()

        db.session.delete(schedule)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Пара "{discipline}" ({date_str}, пара {pair_num}) удалена'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@bp.route('/history/<int:schedule_id>')
def schedule_history(schedule_id):
    """Получить историю изменений занятия"""
    changes = ScheduleChangeService.get_change_history(schedule_id)
    
    history = []
    for change in changes:
        history.append({
            'id': change.id,
            'change_type': change.change_type_name,
            'reason': change.reason,
            'changed_by': change.changed_by,
            'changed_at': change.changed_at.strftime('%d.%m.%Y %H:%M'),
            'old_teacher': change.old_teacher.full_name if change.old_teacher else None,
            'new_teacher': change.new_teacher.full_name if change.new_teacher else None,
            'notes': change.notes
        })
    
    return jsonify(history)


@bp.route('/teacher/<int:teacher_id>/substitutions')
def teacher_substitutions(teacher_id):
    """Получить замены преподавателя"""
    teacher = Teacher.query.get_or_404(teacher_id)
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    substitutions = ScheduleChangeService.get_teacher_substitutions(
        teacher_id, start_date, end_date
    )
    
    result = []
    for sub in substitutions:
        result.append({
            'id': sub.id,
            'date': sub.date.strftime('%d.%m.%Y'),
            'pair_number': sub.pair_number,
            'time': f"{sub.time_start} - {sub.time_end}",
            'group': sub.workload.group.name,
            'discipline': sub.workload.discipline,
            'original_teacher': sub.workload.teacher.full_name,
            'room': sub.room.number if sub.room else '-',
            'reason': sub.change_reason,
            'hours': 2
        })
    
    return jsonify({
        'teacher': teacher.full_name,
        'total_hours': len(result) * 2,
        'substitutions': result
    })


@bp.route('/teacher/<int:teacher_id>/vacant')
def teacher_vacant_hours(teacher_id):
    """Получить вакантные часы преподавателя"""
    teacher = Teacher.query.get_or_404(teacher_id)
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    vacant_schedules = ScheduleChangeService.get_teacher_vacant_hours(
        teacher_id, start_date, end_date
    )
    
    result = []
    for schedule in vacant_schedules:
        result.append({
            'id': schedule.id,
            'date': schedule.date.strftime('%d.%m.%Y'),
            'pair_number': schedule.pair_number,
            'time': f"{schedule.time_start} - {schedule.time_end}",
            'group': schedule.workload.group.name,
            'discipline': schedule.workload.discipline,
            'substitute_teacher': schedule.substitute_teacher.full_name,
            'room': schedule.room.number if schedule.room else '-',
            'reason': schedule.change_reason,
            'hours': 2
        })
    
    return jsonify({
        'teacher': teacher.full_name,
        'total_vacant_hours': len(result) * 2,
        'vacant_schedules': result
    })


@bp.route('/changes/<int:schedule_id>/modal')
def schedule_change_modal(schedule_id):
    """Модальное окно для изменений расписания"""
    schedule = Schedule.query.get_or_404(schedule_id)
    
    # Получаем всех преподавателей кроме основного
    all_teachers = Teacher.query.filter(Teacher.id != schedule.workload.teacher_id).order_by(Teacher.full_name).all()
    
    # Фильтруем преподавателей - оставляем только свободных в это время
    available_teachers = []
    for teacher in all_teachers:
        # Проверяем конфликты с заменителем
        conflict = Schedule.query.filter(
            and_(
                Schedule.date == schedule.date,
                Schedule.pair_number == schedule.pair_number,
                Schedule.workload.has(teacher_id=teacher.id),
                Schedule.status.in_(['planned', 'done', 'substitution'])
            )
        ).first()
        
        # Если конфликта нет, добавляем преподавателя в список доступных
        if not conflict:
            available_teachers.append(teacher)
    
    # Получаем доступные аудитории (также проверяем свободные)
    all_rooms = Room.query.order_by(Room.number).all()
    available_rooms = []
    for room in all_rooms:
        room_conflict = Schedule.query.filter(
            and_(
                Schedule.date == schedule.date,
                Schedule.pair_number == schedule.pair_number,
                Schedule.room_id == room.id,
                Schedule.status.in_(['planned', 'done', 'substitution']),
                Schedule.id != schedule_id  # исключаем текущее занятие
            )
        ).first()
        
        if not room_conflict:
            available_rooms.append(room)
    
    return render_template('schedule/change_modal.html', 
                         schedule=schedule,
                         available_teachers=available_teachers,
                         available_rooms=available_rooms,
                         pair_times=Config.PAIR_TIMES)


@bp.route('/complete', methods=['POST'])
def complete():
    """Complete a class (mark as last class)"""
    try:
        data = request.get_json()
        schedule_id = data.get('schedule_id')
        notes = data.get('notes', '')
        
        if not schedule_id:
            return jsonify({'error': 'Не указан ID занятия'}), 400
        
        # Check period protection
        schedule = Schedule.query.get(schedule_id)
        if schedule and is_period_closed(schedule.date):
            return jsonify({'error': 'Невозможно завершить занятие в закрытом периоде'}), 403
            
        service = ScheduleChangeService()
        success = service.complete_schedule(schedule_id, notes)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Ошибка при завершении занятия'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error completing schedule: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/group-disciplines/<int:group_id>')
def api_group_disciplines(group_id):
    """API endpoint to get detailed discipline information for a group"""
    try:
        # Check if we need all disciplines (for delete modal) or just those with remaining hours
        include_all = request.args.get('all', 'false').lower() == 'true'

        # Get ALL workloads for the group
        workloads = Workload.query.filter_by(
            group_id=group_id
        ).order_by(Workload.discipline).all()

        disciplines_data = []
        for wl in workloads:
            # Count completed pairs from schedule
            completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status.in_(['done', 'completed', 'substitution'])
            ).count()
            actual_completed_hours = completed_pairs * 2

            # Count planned pairs
            planned_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status == 'planned'
            ).count()
            planned_hours = planned_pairs * 2

            # Total scheduled pairs
            total_scheduled_pairs = completed_pairs + planned_pairs

            remaining_hours = max(0, wl.total_hours - actual_completed_hours)

            # Include discipline based on mode
            # - For delete modal (all=true): include if has any scheduled pairs
            # - For generation (all=false): include only if has remaining hours
            should_include = (include_all and total_scheduled_pairs > 0) or (not include_all and remaining_hours > 0)

            if should_include:
                disciplines_data.append({
                    'id': wl.id,
                    'workload_id': wl.id,  # Alias for compatibility
                    'discipline': wl.discipline,
                    'teacher_name': wl.teacher.full_name if wl.teacher else 'Нет преподавателя',
                    'lesson_type': 'Теория' if wl.lesson_type == 'theory' else 'Практика',
                    'total_hours': wl.total_hours,
                    'hours_completed': actual_completed_hours,
                    'hours_planned': planned_hours,
                    'scheduled_pairs': total_scheduled_pairs,  # Total pairs in schedule
                    'hours_per_week': wl.hours_per_week or 2,
                    'semester': wl.semester,
                    'remaining_hours': remaining_hours
                })

        return jsonify({
            'success': True,
            'disciplines': disciplines_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting group disciplines: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/group-overview/<int:group_id>')
def api_group_overview(group_id):
    """API endpoint to get schedule overview for a group"""
    try:
        from sqlalchemy import func
        
        group = Group.query.get_or_404(group_id)
        
        # Получаем все расписание группы
        schedules = Schedule.query.join(Workload).filter(
            Workload.group_id == group_id
        ).all()
        
        if not schedules:
            return jsonify({
                'success': False,
                'error': 'Нет расписания для этой группы'
            })
        
        # Статистика по статусам
        total_pairs = len(schedules)
        done_pairs = len([s for s in schedules if s.status in ['done', 'completed', 'substitution']])
        planned_pairs = len([s for s in schedules if s.status == 'planned'])
        
        # Статистика по дисциплинам
        workloads = Workload.query.filter_by(group_id=group_id).all()
        disciplines_stats = []
        remaining_hours_total = 0
        
        for wl in workloads:
            done_schedules = [s for s in schedules if s.workload_id == wl.id and s.status in ['done', 'completed', 'substitution']]
            planned_schedules = [s for s in schedules if s.workload_id == wl.id and s.status == 'planned']
            
            done_hours = len(done_schedules) * 2
            planned_hours = len(planned_schedules) * 2
            remaining_hours = max(0, wl.total_hours - done_hours)
            remaining_hours_total += remaining_hours
            
            if done_hours > 0 or planned_hours > 0 or remaining_hours > 0:
                disciplines_stats.append({
                    'discipline': wl.discipline,
                    'total_hours': wl.total_hours,
                    'done_hours': done_hours,
                    'planned_hours': planned_hours,
                    'remaining_hours': remaining_hours
                })
        
        # Статистика по неделям
        weeks_stats = []
        if schedules:
            dates = [s.date for s in schedules]
            start_date = min(dates)
            end_date = max(dates)
            
            # Группируем по неделям
            from collections import defaultdict
            weeks_data = defaultdict(lambda: {'done': 0, 'planned': 0, 'total': 0})
            
            for s in schedules:
                week_number = s.date.isocalendar()[1]  # ISO week number
                weeks_data[week_number]['total'] += 1
                if s.status in ['done', 'completed', 'substitution']:
                    weeks_data[week_number]['done'] += 1
                elif s.status == 'planned':
                    weeks_data[week_number]['planned'] += 1
            
            for week_num in sorted(weeks_data.keys()):
                data = weeks_data[week_num]
                weeks_stats.append({
                    'week_number': week_num,
                    'done_count': data['done'],
                    'planned_count': data['planned'],
                    'total_count': data['total']
                })
        
        # Определяем семестр (из первой нагрузки)
        semester = workloads[0].semester if workloads else "?"
        
        # Диапазон дат
        date_range = f"{start_date.strftime('%d.%m')} — {end_date.strftime('%d.%m.%Y')}" if schedules else "нет данных"
        
        return jsonify({
            'success': True,
            'group_name': group.name,
            'group_course': group.course,
            'semester': semester,
            'date_range': date_range,
            'total_pairs': total_pairs,
            'done_pairs': done_pairs,
            'planned_pairs': planned_pairs,
            'remaining_hours': remaining_hours_total,
            'disciplines': disciplines_stats,
            'weeks': weeks_stats
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting group overview: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/errors/<int:group_id>/<int:semester>')
def detailed_errors(group_id, semester):
    """Детальный отчет об ошибках генерации с рекомендациями"""
    try:
        group = Group.query.get_or_404(group_id)
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        
        if not current_year:
            flash('Не установлен текущий учебный год', 'error')
            return redirect(url_for('schedule.generate'))
        
        # Получаем все нагрузки для группы и семестра
        workloads = Workload.query.filter_by(
            group_id=group_id,
            semester=semester,
            academic_year_id=current_year.id
        ).all()
        
        if not workloads:
            flash('Нет нагрузок для анализа', 'warning')
            return redirect(url_for('schedule.generate'))
        
        detailed_errors = []
        total_unplaced_hours = 0
        placement_summary = {
            'total_disciplines': len(workloads),
            'fully_placed': 0,
            'partially_placed': 0,
            'not_placed': 0,
            'total_hours': 0,
            'placed_hours': 0,
            'remaining_hours': 0
        }
        
        for wl in workloads:
            # Подсчет фактически выполненных и запланированных часов
            completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status.in_(['done', 'completed', 'substitution'])
            ).count()
            actual_completed_hours = completed_pairs * 2
            
            planned_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status == 'planned'
            ).count()
            planned_hours = planned_pairs * 2
            
            total_scheduled_hours = actual_completed_hours + planned_hours
            remaining_hours = max(0, wl.total_hours - total_scheduled_hours)
            
            placement_summary['total_hours'] += wl.total_hours
            placement_summary['placed_hours'] += total_scheduled_hours
            placement_summary['remaining_hours'] += remaining_hours
            
            if remaining_hours == 0:
                placement_summary['fully_placed'] += 1
                placement_status = 'full'
            elif total_scheduled_hours > 0:
                placement_summary['partially_placed'] += 1
                placement_status = 'partial'
            else:
                placement_summary['not_placed'] += 1
                placement_status = 'none'
            
            if remaining_hours > 0:
                total_unplaced_hours += remaining_hours
                
                # Анализ причин неразмещения и рекомендаций
                teacher_name = wl.teacher.full_name if wl.teacher else "Нет преподавателя"
                
                # Анализ возможных проблем
                problems = []
                recommendations = []
                
                # Проблема 1: Нет преподавателя
                if not wl.teacher:
                    problems.append({
                        'type': 'no_teacher',
                        'title': 'Отсутствует преподаватель',
                        'description': 'Невозможно создать расписание без назначенного преподавателя',
                        'severity': 'critical'
                    })
                    recommendations.append({
                        'type': 'assign_teacher',
                        'title': 'Назначьте преподавателя',
                        'description': 'Перейдите в раздел "Нагрузки" и назначьте преподавателя для этой дисциплины',
                        'action_url': url_for('workload.edit', id=wl.id),
                        'priority': 'high'
                    })
                
                # Проблема 2: Слишком мало пар в неделю
                hours_per_week = wl.hours_per_week or 2
                if hours_per_week < 4 and remaining_hours > 50:
                    problems.append({
                        'type': 'low_weekly_hours',
                        'title': 'Недостаточно пар в неделю',
                        'description': f'Текущая настройка: {hours_per_week}ч/неделю. При таком темпе потребуется {remaining_hours // hours_per_week} недель для завершения',
                        'severity': 'warning'
                    })
                    recommendations.append({
                        'type': 'increase_weekly_hours',
                        'title': 'Увеличьте количество пар в неделю',
                        'description': f'Рекомендуется увеличить до 4-6 часов в неделю для более равномерного распределения',
                        'action_url': url_for('workload.edit', id=wl.id),
                        'priority': 'medium'
                    })
                
                # Проблема 3: Занятость преподавателя
                if wl.teacher:
                    today = date.today()
                    next_month = today + timedelta(days=30)
                    
                    teacher_schedules = Schedule.query.join(Workload).filter(
                        Workload.teacher_id == wl.teacher_id,
                        Schedule.date >= today,
                        Schedule.date <= next_month
                    ).count()
                    
                    if teacher_schedules > 40:
                        problems.append({
                            'type': 'teacher_overload',
                            'title': 'Преподаватель перегружен',
                            'description': f'У преподавателя уже {teacher_schedules} занятий в ближайший месяц',
                            'severity': 'warning'
                        })
                        recommendations.append({
                            'type': 'redistribute_load',
                            'title': 'Перераспределите нагрузку',
                            'description': 'Рассмотрите возможность назначения дополнительного преподавателя или перенос части нагрузки',
                            'action_url': url_for('workload.index'),
                            'priority': 'medium'
                        })
                
                # Проблема 4: Недостаток учебных недель
                available_weeks = GUP.query.filter_by(
                    group_id=group_id,
                    academic_year_id=current_year.id
                ).filter(GUP.activity_code.in_(['', None, 'УП', 'ОТ', 'ӨО'])).count()
                
                required_weeks = remaining_hours / hours_per_week if hours_per_week > 0 else 0
                if available_weeks < required_weeks:
                    problems.append({
                        'type': 'insufficient_weeks',
                        'title': 'Недостаток учебных недель',
                        'description': f'Доступно {available_weeks} недель, требуется {int(required_weeks)}',
                        'severity': 'error'
                    })
                    recommendations.append({
                        'type': 'add_study_weeks',
                        'title': 'Добавьте учебные недели в ГУП',
                        'description': 'Перейдите в настройки ГУП и добавьте дополнительные учебные недели',
                        'action_url': url_for('gup.index', group_id=group_id),
                        'priority': 'high'
                    })
                
                # Проблема 5: Конфликты в расписании
                if wl.teacher:
                    conflicts_count = 0
                    # Примерная оценка конфликтов (упрощенная)
                    if teacher_schedules > 20:
                        conflicts_count = teacher_schedules // 10
                    
                    if conflicts_count > 0:
                        problems.append({
                            'type': 'schedule_conflicts',
                            'title': 'Конфликты в расписании',
                            'description': f'Обнаружено примерно {conflicts_count} временных конфликтов с другими занятиями',
                            'severity': 'warning'
                        })
                        recommendations.append({
                            'type': 'resolve_conflicts',
                            'title': 'Перенесите конфликтующие занятия',
                            'description': 'Используйте режим "Полное перепланирование" для автоматического разрешения конфликтов',
                            'action_url': url_for('schedule.generate'),
                            'priority': 'medium'
                        })
                
                # Проблема 6: Анализ недель и времени
                if not problems and wl.teacher:
                    # Более глубокий анализ для понимания причин
                    today = date.today()
                    future_gup_weeks = GUP.query.filter_by(
                        group_id=group_id,
                        academic_year_id=current_year.id
                    ).filter(
                        GUP.activity_code.in_(['', None, 'УП', 'ОТ', 'ӨО']),
                        GUP.start_date >= today
                    ).count()
                    
                    if future_gup_weeks == 0:
                        problems.append({
                            'type': 'no_future_weeks',
                            'title': 'Нет будущих учебных недель',
                            'description': 'В ГУП отсутствуют учебные недели на будущие даты для размещения расписания',
                            'severity': 'critical'
                        })
                        recommendations.append({
                            'type': 'add_future_weeks',
                            'title': 'Добавьте будущие учебные недели',
                            'description': 'Перейдите в ГУП и добавьте учебные недели на предстоящий период',
                            'action_url': url_for('gup.index', group_id=group_id),
                            'priority': 'high'
                        })
                    elif remaining_hours > (future_gup_weeks * hours_per_week):
                        problems.append({
                            'type': 'impossible_completion',
                            'title': 'Невозможно завершить в срок',
                            'description': f'Для завершения {remaining_hours}ч при {hours_per_week}ч/нед требуется {remaining_hours // hours_per_week} недель, а доступно только {future_gup_weeks} недель',
                            'severity': 'error'
                        })
                        optimal_hours = remaining_hours / future_gup_weeks if future_gup_weeks > 0 else remaining_hours
                        recommendations.append({
                            'type': 'adjust_weekly_hours',
                            'title': f'Увеличьте до {int(optimal_hours)} часов в неделю',
                            'description': f'Для завершения в срок необходимо увеличить нагрузку до {int(optimal_hours)} часов в неделю',
                            'action_url': url_for('workload.edit', id=wl.id),
                            'priority': 'high'
                        })
                    else:
                        # Глубокая диагностика причин проблемы размещения
                        diagnostic_results = perform_detailed_placement_diagnostic(
                            group_id, semester, wl, remaining_hours, hours_per_week, future_gup_weeks, current_year.id
                        )
                        
                        problems.extend(diagnostic_results['problems'])
                        recommendations.extend(diagnostic_results['recommendations'])
                
                if not problems:
                    # Последний резерв - если совсем ничего не найдено
                    problems.append({
                        'type': 'complex_issue',
                        'title': 'Комплексная проблема размещения',
                        'description': 'Причина не размещения может быть связана с комбинацией факторов: занятость преподавателя, недостаток аудиторий, конфликты времени',
                        'severity': 'info'
                    })
                    recommendations.extend([
                        {
                            'type': 'check_teacher_load',
                            'title': 'Проверьте нагрузку преподавателя',
                            'description': 'Убедитесь, что у преподавателя есть свободное время для дополнительных занятий',
                            'action_url': url_for('main.index'),
                            'priority': 'medium'
                        },
                        {
                            'type': 'review_gup_settings',
                            'title': 'Проверьте настройки ГУП',
                            'description': 'Убедитесь, что в ГУП корректно настроены учебные недели и периоды',
                            'action_url': url_for('gup.index', group_id=group_id),
                            'priority': 'medium'
                        }
                    ])
                
                detailed_errors.append({
                    'workload_id': wl.id,
                    'discipline': wl.discipline,
                    'teacher_name': teacher_name,
                    'total_hours': wl.total_hours,
                    'completed_hours': actual_completed_hours,
                    'planned_hours': planned_hours,
                    'remaining_hours': remaining_hours,
                    'percentage_unplaced': round(remaining_hours / wl.total_hours * 100, 1),
                    'hours_per_week': hours_per_week,
                    'placement_status': placement_status,
                    'problems': problems,
                    'recommendations': recommendations
                })
        
        # Рассчитываем общую статистику
        placement_summary['placement_percentage'] = round(
            (placement_summary['placed_hours'] / placement_summary['total_hours'] * 100) 
            if placement_summary['total_hours'] > 0 else 100, 1
        )
        
        return render_template('schedule/detailed_errors.html',
                               group=group,
                               semester=semester,
                               detailed_errors=detailed_errors,
                               placement_summary=placement_summary,
                               total_unplaced_hours=total_unplaced_hours)
    
    except Exception as e:
        flash(f'Ошибка при формировании отчета: {str(e)}', 'error')
        return redirect(url_for('schedule.generate'))


@bp.route('/api/generation-errors/<int:group_id>/<int:semester>')
def api_generation_errors(group_id, semester):
    """API для получения ошибок генерации в JSON формате"""
    try:
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            return jsonify({'success': False, 'error': 'Не установлен текущий учебный год'})
        
        # Создаем временный генератор для анализа ошибок
        generator = ScheduleGenerator(group_id, semester, current_year.id, 'remaining')
        
        # Выполняем анализ без фактической генерации
        generator.workloads = Workload.query.filter_by(
            group_id=group_id,
            semester=semester,
            academic_year_id=current_year.id
        ).all()
        
        if generator.workloads:
            generator._analyze_final_placement()
        
        result = generator.get_result()
        
        return jsonify({
            'success': True,
            'errors': result.get('errors', []),
            'warnings': result.get('warnings', []),
            'total_errors': len(result.get('errors', [])),
            'total_warnings': len(result.get('warnings', []))
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/delete_group_schedule/<int:group_id>/<int:semester>', methods=['POST'])
def delete_group_schedule(group_id, semester):
    """Удалить все расписание для группы и семестра"""
    try:
        from app.models import Group, AcademicYear, Workload, Schedule
        
        # Получаем группу
        group = Group.query.get_or_404(group_id)
        
        # Получаем текущий учебный год
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            return jsonify({'success': False, 'error': 'Текущий учебный год не найден'})
        
        # Получаем все нагрузки для группы и семестра
        workloads = Workload.query.filter(
            Workload.group_id == group_id,
            Workload.semester == semester,
            Workload.academic_year_id == current_year.id
        ).all()
        
        if not workloads:
            return jsonify({'success': False, 'error': f'Нагрузки для группы {group.name} семестр {semester} не найдены'})
        
        workload_ids = [wl.id for wl in workloads]
        
        # Находим все расписание для этих нагрузок
        schedules_to_delete = Schedule.query.filter(
            Schedule.workload_id.in_(workload_ids)
        ).all()
        
        if not schedules_to_delete:
            return jsonify({'success': False, 'error': f'Расписание для группы {group.name} семестр {semester} не найдено'})
        
        # Упрощаем: удаляем без проверки закрытых периодов
        
        # Удаляем все расписание
        deleted_count = len(schedules_to_delete)
        
        for schedule in schedules_to_delete:
            db.session.delete(schedule)
        
        db.session.commit()
        
        # Упрощаем: не обновляем completed_hours
        
        return jsonify({
            'success': True,
            'message': f'Удалено {deleted_count} пар для группы {group.name} семестр {semester}',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Ошибка удаления: {str(e)}'})


@bp.route('/delete_workload_schedule/<int:workload_id>', methods=['POST'])
def delete_workload_schedule(workload_id):
    """Удалить расписание только для одной дисциплины (нагрузки)"""
    try:
        from app.models import Workload, Schedule

        # Получаем нагрузку
        workload = Workload.query.get_or_404(workload_id)
        discipline_name = workload.discipline
        group_name = workload.group.name if workload.group else 'N/A'

        # Находим все расписание для этой нагрузки
        schedules_to_delete = Schedule.query.filter(
            Schedule.workload_id == workload_id
        ).all()

        if not schedules_to_delete:
            return jsonify({
                'success': False,
                'error': f'Расписание для "{discipline_name}" не найдено'
            })

        # Подсчитываем статистику
        deleted_count = len(schedules_to_delete)
        planned_count = sum(1 for s in schedules_to_delete if s.status == 'planned')
        done_count = sum(1 for s in schedules_to_delete if s.status in ['done', 'completed'])

        # Удаляем все расписание для этой нагрузки
        for schedule in schedules_to_delete:
            db.session.delete(schedule)

        # Сбрасываем счетчик выполненных часов
        workload.hours_completed = 0

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Удалено {deleted_count} пар для "{discipline_name}" ({group_name})',
            'deleted_count': deleted_count,
            'planned_deleted': planned_count,
            'done_deleted': done_count,
            'discipline': discipline_name,
            'group': group_name
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Ошибка удаления: {str(e)}'})


@bp.route('/delete_future_schedule/<int:group_id>/<int:semester>', methods=['POST'])
def delete_future_schedule(group_id, semester):
    """Удаление будущего расписания группы (кроме проведенных пар)"""
    try:
        # Получаем группу
        group = Group.query.get_or_404(group_id)
        
        # Получаем текущий учебный год
        current_academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_academic_year:
            return jsonify({'success': False, 'error': 'Не найден текущий учебный год'})
        
        # Получаем все нагрузки группы для указанного семестра
        workloads = Workload.query.filter_by(
            group_id=group_id,
            semester=semester,
            academic_year_id=current_academic_year.id
        ).all()
        
        if not workloads:
            return jsonify({'success': False, 'error': 'Нет нагрузок для указанной группы и семестра'})
        
        workload_ids = [wl.id for wl in workloads]
        
        # Находим расписание, которое можно удалить:
        # - статус 'planned' (запланированные, но не проведенные)
        # - статус 'cancelled' (отмененные)
        # Исключаем: 'done', 'completed', 'substitution' (уже проведенные)
        schedules_to_delete = Schedule.query.filter(
            Schedule.workload_id.in_(workload_ids),
            Schedule.status.in_(['planned', 'cancelled'])  # Только незавершенные
        ).all()
        
        if not schedules_to_delete:
            return jsonify({
                'success': True, 
                'message': 'Нет будущих пар для удаления (все пары уже проведены или отсутствуют)',
                'deleted_count': 0
            })
        
        # Подсчитываем статистику перед удалением
        deleted_count = len(schedules_to_delete)
        planned_count = len([s for s in schedules_to_delete if s.status == 'planned'])
        cancelled_count = len([s for s in schedules_to_delete if s.status == 'cancelled'])
        
        # Удаляем найденные пары
        for schedule in schedules_to_delete:
            db.session.delete(schedule)
        
        db.session.commit()
        
        # Формируем детальное сообщение
        details = []
        if planned_count > 0:
            details.append(f"запланированных: {planned_count}")
        if cancelled_count > 0:
            details.append(f"отмененных: {cancelled_count}")
        
        message = f'Удалено {deleted_count} будущих пар для группы {group.name} семестр {semester}'
        if details:
            message += f' ({", ".join(details)})'
        
        return jsonify({
            'success': True,
            'message': message,
            'deleted_count': deleted_count,
            'planned_deleted': planned_count,
            'cancelled_deleted': cancelled_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Ошибка удаления: {str(e)}'})


@bp.route('/delete_completed_schedule/<int:group_id>/<int:semester>', methods=['POST'])
def delete_completed_schedule(group_id, semester):
    """Удаление проведенных пар группы (только завершенные занятия)"""
    try:
        # Получаем группу
        group = Group.query.get_or_404(group_id)
        
        # Получаем текущий учебный год
        current_academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_academic_year:
            return jsonify({'success': False, 'error': 'Не найден текущий учебный год'})
        
        # Получаем все нагрузки группы для указанного семестра
        workloads = Workload.query.filter_by(
            group_id=group_id,
            semester=semester,
            academic_year_id=current_academic_year.id
        ).all()
        
        if not workloads:
            return jsonify({'success': False, 'error': 'Нет нагрузок для указанной группы и семестра'})
        
        workload_ids = [wl.id for wl in workloads]
        
        # Находим только проведенные пары:
        # - статус 'done' (проведенные)
        # - статус 'completed' (завершенные)  
        # - статус 'substitution' (замещения)
        # Исключаем: 'planned', 'cancelled' (еще не проведенные)
        schedules_to_delete = Schedule.query.filter(
            Schedule.workload_id.in_(workload_ids),
            Schedule.status.in_(['done', 'completed', 'substitution'])  # Только проведенные
        ).all()
        
        if not schedules_to_delete:
            return jsonify({
                'success': True, 
                'message': 'Нет проведенных пар для удаления (все пары еще не проведены или отсутствуют)',
                'deleted_count': 0
            })
        
        # Подсчитываем статистику перед удалением
        deleted_count = len(schedules_to_delete)
        done_count = len([s for s in schedules_to_delete if s.status == 'done'])
        completed_count = len([s for s in schedules_to_delete if s.status == 'completed'])
        substitution_count = len([s for s in schedules_to_delete if s.status == 'substitution'])
        
        # ВАЖНО: Удаление проведенных пар может повлиять на:
        # - РУП (учебные планы)
        # - Табели успеваемости
        # - Отчеты по нагрузке преподавателей
        # - Статистику посещаемости
        # Поэтому делаем с осторожностью
        
        # Удаляем найденные пары
        for schedule in schedules_to_delete:
            db.session.delete(schedule)
        
        db.session.commit()
        
        # Формируем детальное сообщение
        details = []
        if done_count > 0:
            details.append(f"проведенных: {done_count}")
        if completed_count > 0:
            details.append(f"завершенных: {completed_count}")
        if substitution_count > 0:
            details.append(f"замещений: {substitution_count}")
        
        message = f'Удалено {deleted_count} проведенных пар для группы {group.name} семестр {semester}'
        if details:
            message += f' ({", ".join(details)})'
        
        # Добавляем предупреждение о влиянии на связанные данные
        warning = 'ВНИМАНИЕ: Удаление проведенных пар может повлиять на РУП, табели, отчеты преподавателей и статистику.'
        
        return jsonify({
            'success': True,
            'message': message,
            'warning': warning,
            'deleted_count': deleted_count,
            'done_deleted': done_count,
            'completed_deleted': completed_count,
            'substitution_deleted': substitution_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Ошибка удаления проведенных пар: {str(e)}'})






