from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.models import Group, Room, RoomPreference, Workload, Schedule, AcademicYear, db
from app.services.scheduler import ScheduleGenerator
from datetime import date
import json

bp = Blueprint('schedule_wizard', __name__, url_prefix='/schedule-wizard')

@bp.route('/')
def index():
    """Главная страница мастера генерации"""
    groups = Group.query.order_by(Group.name).all()
    current_academic_year = AcademicYear.query.filter_by(is_current=True).first()
    return render_template('schedule_wizard/index.html', 
                          groups=groups, 
                          current_academic_year=current_academic_year)

@bp.route('/setup/<int:group_id>')
def setup(group_id):
    """Мастер настройки генерации для группы"""
    group = Group.query.get_or_404(group_id)
    current_academic_year = AcademicYear.query.filter_by(is_current=True).first()
    
    # Получаем нагрузки группы для выбора семестра
    workloads = Workload.query.filter_by(
        group_id=group_id, 
        academic_year_id=current_academic_year.id if current_academic_year else None
    ).all()
    
    # Группируем по семестрам
    semesters = {}
    for wl in workloads:
        if wl.semester not in semesters:
            semesters[wl.semester] = []
        semesters[wl.semester].append(wl)
    
    # Получаем все аудитории
    rooms = Room.query.order_by(Room.number).all()
    
    # Получаем существующие предпочтения
    preferences = RoomPreference.query.filter_by(group_id=group_id).all()
    preferences_dict = {}
    for pref in preferences:
        key = f"{pref.discipline}_{pref.room_id}" if pref.discipline else f"_general_{pref.room_id}"
        preferences_dict[key] = {
            'priority': pref.priority,
            'reason': pref.reason
        }
    
    return render_template('schedule_wizard/setup.html', 
                          group=group,
                          semesters=semesters,
                          rooms=rooms,
                          preferences_dict=preferences_dict,
                          current_academic_year=current_academic_year)

@bp.route('/api/preview/<int:group_id>')
def api_preview(group_id):
    """API для предварительного просмотра генерации"""
    semester = request.args.get('semester', type=int)
    generation_mode = request.args.get('mode', 'remaining')
    
    if not semester:
        return jsonify({'error': 'Не указан семестр'}), 400
    
    current_academic_year = AcademicYear.query.filter_by(is_current=True).first()
    if not current_academic_year:
        return jsonify({'error': 'Не найден текущий учебный год'}), 400
    
    # Получаем нагрузки для предварительного анализа
    workloads = Workload.query.filter_by(
        group_id=group_id,
        semester=semester,
        academic_year_id=current_academic_year.id
    ).all()
    
    if not workloads:
        return jsonify({'error': 'Нет нагрузок для выбранного семестра'}), 400
    
    # Анализ текущего состояния
    preview_data = {
        'workloads': [],
        'total_hours_needed': 0,
        'total_hours_completed': 0,
        'total_hours_planned': 0
    }
    
    for wl in workloads:
        # Подсчет фактически выполненных часов
        completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
            Schedule.status.in_(['done', 'completed', 'substitution'])
        ).count()
        actual_completed_hours = completed_pairs * 2
        
        # Подсчет запланированных часов
        planned_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
            Schedule.status == 'planned'
        ).count()
        planned_hours = planned_pairs * 2
        
        remaining_hours = wl.total_hours - actual_completed_hours - planned_hours
        
        workload_info = {
            'discipline': wl.discipline,
            'teacher': wl.teacher.full_name if wl.teacher else 'Нет преподавателя',
            'total_hours': wl.total_hours,
            'completed_hours': actual_completed_hours,
            'planned_hours': planned_hours,
            'remaining_hours': remaining_hours,
            'pairs_per_week': wl.pairs_per_week or 1
        }
        
        preview_data['workloads'].append(workload_info)
        preview_data['total_hours_needed'] += wl.total_hours
        preview_data['total_hours_completed'] += actual_completed_hours
        preview_data['total_hours_planned'] += planned_hours
    
    preview_data['total_hours_remaining'] = (preview_data['total_hours_needed'] - 
                                           preview_data['total_hours_completed'] - 
                                           preview_data['total_hours_planned'])
    
    return jsonify(preview_data)

@bp.route('/api/room-preferences/<int:group_id>', methods=['POST'])
def save_room_preferences(group_id):
    """Сохранение предпочтений по аудиториям"""
    data = request.get_json()
    
    try:
        # Удаляем старые предпочтения
        RoomPreference.query.filter_by(group_id=group_id).delete()
        
        # Добавляем новые
        for pref_data in data.get('preferences', []):
            preference = RoomPreference(
                group_id=group_id,
                room_id=pref_data['room_id'],
                discipline=pref_data.get('discipline'),
                priority=pref_data.get('priority', 1),
                reason=pref_data.get('reason', '')
            )
            db.session.add(preference)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/generate', methods=['POST'])
def generate():
    """Генерация расписания с учетом настроек"""
    group_id = request.form.get('group_id', type=int)
    semester = request.form.get('semester', type=int)
    generation_mode = request.form.get('generation_mode', 'remaining')
    
    if not all([group_id, semester]):
        flash('Не указаны обязательные параметры', 'error')
        return redirect(url_for('schedule_wizard.index'))
    
    current_academic_year = AcademicYear.query.filter_by(is_current=True).first()
    if not current_academic_year:
        flash('Не найден текущий учебный год', 'error')
        return redirect(url_for('schedule_wizard.index'))
    
    try:
        # Создаем генератор с учетом предпочтений
        generator = ScheduleGenerator(group_id, semester, current_academic_year.id, generation_mode)
        
        # Устанавливаем предпочитаемые аудитории
        preferences = RoomPreference.query.filter_by(group_id=group_id).all()
        generator.set_room_preferences(preferences)
        
        # Генерируем
        success = generator.generate()
        result = generator.get_result()
        
        if success:
            flash(f'Расписание сгенерировано! Создано: {result["created_count"]} пар, удалено: {result["deleted_count"]}', 'success')
            
            # Показываем предупреждения
            for warning in result['warnings']:
                flash(warning, 'warning')
        else:
            flash('Ошибки при генерации:', 'error')
            for error in result['errors']:
                flash(error, 'error')
    
    except Exception as e:
        flash(f'Ошибка генерации: {str(e)}', 'error')
    
    return redirect(url_for('schedule_wizard.post_generation', 
                           group_id=group_id, semester=semester))

@bp.route('/post-generation/<int:group_id>/<int:semester>')
def post_generation(group_id, semester):
    """Страница после генерации с возможностями массового редактирования"""
    group = Group.query.get_or_404(group_id)
    current_academic_year = AcademicYear.query.filter_by(is_current=True).first()
    
    # Получаем сгенерированное расписание
    workloads = Workload.query.filter_by(
        group_id=group_id,
        semester=semester,
        academic_year_id=current_academic_year.id if current_academic_year else None
    ).all()
    
    schedules_by_workload = {}
    for wl in workloads:
        schedules = Schedule.query.filter_by(workload_id=wl.id).filter(
            Schedule.status == 'planned'
        ).order_by(Schedule.date, Schedule.pair_number).all()
        schedules_by_workload[wl.id] = schedules
    
    # Получаем все аудитории для выбора
    rooms = Room.query.order_by(Room.number).all()
    
    return render_template('schedule_wizard/post_generation.html',
                          group=group,
                          semester=semester,
                          workloads=workloads,
                          schedules_by_workload=schedules_by_workload,
                          rooms=rooms)

@bp.route('/api/bulk-change-rooms', methods=['POST'])
def bulk_change_rooms():
    """API для массового изменения аудиторий"""
    data = request.get_json()
    
    try:
        changes_count = 0
        
        for change in data.get('changes', []):
            schedule_ids = change.get('schedule_ids', [])
            new_room_id = change.get('new_room_id')
            
            if not schedule_ids or not new_room_id:
                continue
            
            # Проверяем доступность аудитории для каждого слота времени
            for schedule_id in schedule_ids:
                schedule = Schedule.query.get(schedule_id)
                if not schedule:
                    continue
                
                # Проверяем конфликт аудитории
                conflict = Schedule.query.filter(
                    Schedule.room_id == new_room_id,
                    Schedule.date == schedule.date,
                    Schedule.pair_number == schedule.pair_number,
                    Schedule.id != schedule_id
                ).first()
                
                if conflict:
                    return jsonify({
                        'error': f'Конфликт аудиторий: аудитория {new_room_id} занята на {schedule.date} в {schedule.pair_number} паре'
                    }), 400
                
                schedule.room_id = new_room_id
                changes_count += 1
        
        db.session.commit()
        return jsonify({'success': True, 'changes_count': changes_count})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500