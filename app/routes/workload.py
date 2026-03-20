from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import Workload, Group, Teacher, AcademicYear, GUP, Schedule
from datetime import date, timedelta

bp = Blueprint('workload', __name__, url_prefix='/workload')


@bp.route('/')
def index():
    """List workloads with filters"""
    group_id = request.args.get('group_id', type=int)
    teacher_id = request.args.get('teacher_id', type=int)
    semester = request.args.get('semester', type=int)

    query = Workload.query

    if group_id:
        query = query.filter_by(group_id=group_id)
    if teacher_id:
        query = query.filter_by(teacher_id=teacher_id)
    if semester:
        query = query.filter_by(semester=semester)

    workloads = query.order_by(Workload.group_id, Workload.discipline).all()

    # All groups and teachers for filters
    all_groups = Group.query.order_by(Group.name).all()
    all_teachers = Teacher.query.order_by(Teacher.full_name).all()

    return render_template('workload/index.html',
                           workloads=workloads,
                           groups=all_groups,
                           teachers=all_teachers,
                           selected_group=group_id,
                           selected_teacher=teacher_id,
                           selected_semester=semester)


@bp.route('/rup')
def rup_select():
    """Select group to view RUP"""
    groups = Group.query.order_by(Group.name).all()

    # Group by specialty
    groups_by_specialty = {}
    for g in groups:
        spec_name = g.specialty.name_ru if g.specialty else 'Без специальности'
        if spec_name not in groups_by_specialty:
            groups_by_specialty[spec_name] = []
        groups_by_specialty[spec_name].append(g)

    return render_template('workload/rup_select.html',
                           groups=groups,
                           groups_by_specialty=groups_by_specialty)


@bp.route('/rup/<int:group_id>')
def rup(group_id):
    """View RUP (curriculum) for a group"""
    group = Group.query.get_or_404(group_id)
    year_id = request.args.get('year_id', type=int)
    semester = request.args.get('semester', type=int)

    academic_years = AcademicYear.query.order_by(AcademicYear.start_date.desc()).all()

    # Default to current academic year
    if not year_id:
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if current_year:
            year_id = current_year.id

    selected_year = AcademicYear.query.get(year_id) if year_id else None

    workloads = []
    semesters_data = {}
    total_hours = 0
    total_theory = 0
    total_practice = 0
    total_per_week = 0
    total_completed = 0

    if selected_year:
        query = Workload.query.filter_by(group_id=group_id, academic_year_id=year_id)
        if semester:
            query = query.filter_by(semester=semester)

        workloads = query.order_by(Workload.semester, Workload.discipline).all()

        # Group by semester
        for wl in workloads:
            sem = wl.semester
            if sem not in semesters_data:
                semesters_data[sem] = {
                    'workloads': [],
                    'total_hours': 0,
                    'theory_hours': 0,
                    'practice_hours': 0,
                    'hours_per_week': 0,
                    'completed': 0
                }

            semesters_data[sem]['workloads'].append(wl)
            semesters_data[sem]['total_hours'] += wl.total_hours
            semesters_data[sem]['hours_per_week'] += wl.hours_per_week or 0
            semesters_data[sem]['completed'] += wl.hours_completed

            if wl.lesson_type == 'theory':
                semesters_data[sem]['theory_hours'] += wl.total_hours
            elif wl.lesson_type == 'practice':
                semesters_data[sem]['practice_hours'] += wl.total_hours
            # consultation and exam hours counted in total but not separately displayed

        # Calculate grand totals
        total_hours = sum(w.total_hours for w in workloads)
        total_theory = sum(w.total_hours for w in workloads if w.lesson_type == 'theory')
        total_practice = sum(w.total_hours for w in workloads if w.lesson_type == 'practice')
        total_consultation = sum(w.total_hours for w in workloads if w.lesson_type == 'consultation')
        total_exam = sum(w.total_hours for w in workloads if w.lesson_type == 'exam')
        total_per_week = sum(w.hours_per_week or 0 for w in workloads)
        total_completed = sum(w.hours_completed for w in workloads)

    return render_template('workload/rup.html',
                           group=group,
                           academic_years=academic_years,
                           selected_year=selected_year,
                           workloads=workloads,
                           semesters_data=semesters_data,
                           selected_semester=semester,
                           total_hours=total_hours,
                           total_theory=total_theory,
                           total_practice=total_practice,
                           total_consultation=total_consultation,
                           total_exam=total_exam,
                           total_per_week=total_per_week,
                           total_completed=total_completed)


@bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create new workload entry"""
    if request.method == 'POST':
        # Get current academic year
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            flash('Не установлен текущий учебный год', 'error')
            return redirect(url_for('workload.create'))

        workload = Workload(
            teacher_id=request.form.get('teacher_id', type=int),
            group_id=request.form.get('group_id', type=int),
            academic_year_id=current_year.id,
            discipline=request.form.get('discipline'),
            lesson_type=request.form.get('lesson_type', 'theory'),
            semester=request.form.get('semester', type=int),
            total_hours=request.form.get('total_hours', type=int),
            hours_per_week=request.form.get('hours_per_week', type=int)
        )
        db.session.add(workload)
        db.session.commit()
        flash('Нагрузка добавлена', 'success')
        return redirect(url_for('workload.index'))

    groups = Group.query.order_by(Group.name).all()
    teachers = Teacher.query.order_by(Teacher.full_name).all()

    return render_template('workload/form.html',
                           workload=None,
                           groups=groups,
                           teachers=teachers)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """Edit workload"""
    workload = Workload.query.get_or_404(id)

    if request.method == 'POST':
        workload.teacher_id = request.form.get('teacher_id', type=int)
        workload.group_id = request.form.get('group_id', type=int)
        workload.discipline = request.form.get('discipline')
        workload.lesson_type = request.form.get('lesson_type', 'theory')
        workload.semester = request.form.get('semester', type=int)
        workload.total_hours = request.form.get('total_hours', type=int)
        workload.hours_per_week = request.form.get('hours_per_week', type=int)

        db.session.commit()
        flash('Нагрузка обновлена', 'success')
        return redirect(url_for('workload.index'))

    groups = Group.query.order_by(Group.name).all()
    teachers = Teacher.query.order_by(Teacher.full_name).all()

    return render_template('workload/form.html',
                           workload=workload,
                           groups=groups,
                           teachers=teachers)


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """Delete workload with all related records"""
    workload = Workload.query.get_or_404(id)
    # Save filter params to redirect back to same view
    redirect_params = {}
    referer = request.referrer or ''
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(referer)
    for key in ('group_id', 'teacher_id', 'semester'):
        vals = parse_qs(parsed.query).get(key, [])
        if vals and vals[0]:
            redirect_params[key] = vals[0]
    
    # Import all related models
    from app.models import WorkloadTemplate, Schedule, ScheduleChange, VacantHours
    
    # Get all schedules for this workload
    schedules = Schedule.query.filter_by(workload_id=id).all()
    schedule_ids = [s.id for s in schedules]
    
    deleted_counts = {
        'templates': 0,
        'schedule_changes': 0, 
        'schedules': 0,
        'vacant_hours': 0
    }
    
    # 1. Delete schedule changes that reference the schedule records
    if schedule_ids:
        schedule_changes = ScheduleChange.query.filter(ScheduleChange.schedule_id.in_(schedule_ids)).all()
        for change in schedule_changes:
            db.session.delete(change)
        deleted_counts['schedule_changes'] = len(schedule_changes)
        
        # Also delete schedule changes with related_schedule_id references
        related_changes = ScheduleChange.query.filter(ScheduleChange.related_schedule_id.in_(schedule_ids)).all()
        for change in related_changes:
            db.session.delete(change)
        deleted_counts['schedule_changes'] += len(related_changes)
    
    # 2. Delete workload templates
    templates = WorkloadTemplate.query.filter_by(workload_id=id).all()
    for template in templates:
        db.session.delete(template)
    deleted_counts['templates'] = len(templates)
    
    # 3. Delete vacant hours records
    vacant_hours = VacantHours.query.filter_by(workload_id=id).all()
    for vh in vacant_hours:
        db.session.delete(vh)
    deleted_counts['vacant_hours'] = len(vacant_hours)
    
    # 4. Delete schedules
    for schedule in schedules:
        db.session.delete(schedule)
    deleted_counts['schedules'] = len(schedules)
    
    # 5. Finally delete the workload itself
    db.session.delete(workload)
    db.session.commit()
    
    # Create informative message
    total_related = sum(deleted_counts.values())
    if total_related > 0:
        details = []
        if deleted_counts['schedules']:
            details.append(f"{deleted_counts['schedules']} расписаний")
        if deleted_counts['schedule_changes']:
            details.append(f"{deleted_counts['schedule_changes']} изменений расписания")
        if deleted_counts['templates']:
            details.append(f"{deleted_counts['templates']} шаблонов")
        if deleted_counts['vacant_hours']:
            details.append(f"{deleted_counts['vacant_hours']} записей свободных часов")
        
        detail_text = ", ".join(details)
        flash(f'Нагрузка и связанные записи удалены: {detail_text}', 'success')
    else:
        flash('Нагрузка удалена', 'success')
    
    return redirect(url_for('workload.index', **redirect_params))


@bp.route('/api/calculate-optimal-hours/<int:group_id>/<int:semester>')
def calculate_optimal_hours(group_id, semester):
    """API для расчета оптимальных часов в неделю"""
    try:
        total_hours = request.args.get('total_hours', type=int)
        workload_id = request.args.get('workload_id', type=int)  # Для редактирования существующей нагрузки
        
        if not total_hours or total_hours <= 0:
            return jsonify({
                'success': False,
                'error': 'Укажите корректное количество часов'
            })
        
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            return jsonify({
                'success': False,
                'error': 'Не установлен текущий учебный год'
            })
        
        group = Group.query.get_or_404(group_id)
        
        # Получаем уже выполненные часы для этой нагрузки (если редактируем)
        completed_hours = 0
        if workload_id:
            existing_workload = Workload.query.get(workload_id)
            if existing_workload:
                completed_pairs = Schedule.query.filter_by(workload_id=workload_id).filter(
                    Schedule.status.in_(['done', 'completed', 'substitution'])
                ).count()
                completed_hours = completed_pairs * 2
        
        remaining_hours = max(0, total_hours - completed_hours)
        
        # Получаем доступные учебные недели для группы и семестра
        today = date.today()
        
        # Фильтруем ГУП недели по семестру
        if semester in [1, 3, 5, 7]:
            # Нечетный семестр (сентябрь-январь)
            if today.month >= 9:
                # Если сейчас сентябрь-декабрь, то это текущий учебный год
                semester_start = date(today.year, 9, 1)
                semester_end = date(today.year + 1, 1, 31)
            else:
                # Если сейчас январь-август, то это завершение предыдущего учебного года
                semester_start = date(today.year - 1, 9, 1)
                semester_end = date(today.year, 1, 31)
        else:
            # Четный семестр (февраль-июнь)
            if today.month >= 2 and today.month <= 6:
                # Если сейчас февраль-июнь, это текущий семестр
                semester_start = date(today.year, 2, 1)
                semester_end = date(today.year, 6, 30)
            elif today.month >= 9:
                # Если сейчас сентябрь-декабрь, то следующий четный семестр будет в следующем году
                semester_start = date(today.year + 1, 2, 1)
                semester_end = date(today.year + 1, 6, 30)
            else:
                # Если январь, то это еще предыдущий четный семестр или готовимся к новому
                semester_start = date(today.year, 2, 1)
                semester_end = date(today.year, 6, 30)
        
        # Получаем учебные недели в период семестра
        gup_weeks = GUP.query.filter_by(
            group_id=group_id,
            academic_year_id=current_year.id
        ).filter(
            GUP.activity_code.in_(['', None, 'УП', 'ОТ', 'ӨО']),
            GUP.start_date >= semester_start,
            GUP.end_date <= semester_end,
            GUP.end_date >= today  # Только будущие недели
        ).order_by(GUP.week_number).all()
        
        available_weeks = len(gup_weeks)
        
        if available_weeks == 0:
            return jsonify({
                'success': False,
                'error': f'Нет доступных учебных недель для {semester} семестра',
                'recommendations': [
                    'Добавьте учебные недели в ГУП',
                    'Проверьте настройки семестра'
                ]
            })
        
        # Рассчитываем различные варианты распределения
        calculations = []
        
        # Вариант 1: Равномерное распределение
        if remaining_hours > 0:
            optimal_per_week = remaining_hours / available_weeks
            optimal_pairs = optimal_per_week / 2
            
            calculations.append({
                'type': 'optimal',
                'title': 'Оптимальное распределение',
                'hours_per_week': round(optimal_per_week),
                'pairs_per_week': round(optimal_pairs, 1),
                'total_weeks': available_weeks,
                'completion_date': (gup_weeks[-1].end_date if gup_weeks else today).strftime('%d.%m.%Y'),
                'description': f'Равномерное распределение по {available_weeks} неделям',
                'efficiency': 100,
                'color': 'success'
            })
        
        # Вариант 2: Интенсивное (4-6 часов в неделю)
        for intensive_hours in [4, 6, 8]:
            if intensive_hours <= remaining_hours:
                weeks_needed = remaining_hours / intensive_hours
                weeks_needed_ceil = int(weeks_needed) + (1 if weeks_needed % 1 > 0 else 0)
                
                if weeks_needed_ceil <= available_weeks:
                    completion_week_index = min(weeks_needed_ceil - 1, len(gup_weeks) - 1)
                    completion_date = gup_weeks[completion_week_index].end_date if gup_weeks else today
                    
                    calculations.append({
                        'type': 'intensive',
                        'title': f'Интенсивный режим ({intensive_hours}ч/неделю)',
                        'hours_per_week': intensive_hours,
                        'pairs_per_week': intensive_hours / 2,
                        'total_weeks': weeks_needed_ceil,
                        'completion_date': completion_date.strftime('%d.%m.%Y'),
                        'description': f'Завершение через {weeks_needed_ceil} недель',
                        'efficiency': min(100, int(100 * available_weeks / weeks_needed_ceil)),
                        'color': 'warning' if intensive_hours > 6 else 'info'
                    })
        
        # Вариант 3: Минимальный (2 часа в неделю)
        min_hours = 2
        min_weeks_needed = remaining_hours / min_hours
        min_weeks_ceil = int(min_weeks_needed) + (1 if min_weeks_needed % 1 > 0 else 0)
        
        calculations.append({
            'type': 'minimal',
            'title': 'Минимальный режим (2ч/неделю)',
            'hours_per_week': min_hours,
            'pairs_per_week': 1,
            'total_weeks': min_weeks_ceil,
            'completion_date': 'Может превысить семестр' if min_weeks_ceil > available_weeks else 
                               (gup_weeks[min(min_weeks_ceil - 1, len(gup_weeks) - 1)].end_date.strftime('%d.%m.%Y') if gup_weeks else today.strftime('%d.%m.%Y')),
            'description': f'Потребуется {min_weeks_ceil} недель',
            'efficiency': min(100, int(100 * available_weeks / min_weeks_ceil)) if min_weeks_ceil > 0 else 0,
            'color': 'danger' if min_weeks_ceil > available_weeks else 'secondary'
        })
        
        # Сортируем по эффективности
        calculations.sort(key=lambda x: x['efficiency'], reverse=True)
        
        # Определяем рекомендуемый вариант
        recommended = calculations[0] if calculations else None
        
        # Дополнительные рекомендации
        recommendations = []
        if remaining_hours > available_weeks * 8:
            recommendations.append('Рассмотрите разделение дисциплины на части')
        if available_weeks < 10:
            recommendations.append('Увеличьте количество учебных недель в ГУП')
        if completed_hours > 0:
            recommendations.append(f'Учтено уже проведенных часов: {completed_hours}')
        
        return jsonify({
            'success': True,
            'total_hours': total_hours,
            'remaining_hours': remaining_hours,
            'completed_hours': completed_hours,
            'available_weeks': available_weeks,
            'semester_period': f"{semester_start.strftime('%d.%m')} — {semester_end.strftime('%d.%m.%Y')}",
            'calculations': calculations,
            'recommended': recommended,
            'recommendations': recommendations
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
