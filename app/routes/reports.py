from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from datetime import datetime
from app import db
from app.models import Workload, Schedule, Group, Teacher, AcademicYear, SchedulePeriod, GUP, ScheduleChange, VacantHours
from app.services.exporter import ExcelExporter
from config import Config

bp = Blueprint('reports', __name__, url_prefix='/reports')


@bp.route('/')
def index():
    """Reports main page"""
    return render_template('reports/index.html')


@bp.route('/hours')
def hours():
    """Hours tracking report"""
    group_id = request.args.get('group_id', type=int)
    semester = request.args.get('semester', type=int)

    groups = Group.query.order_by(Group.name).all()
    workloads = []
    group = None
    total_plan = 0
    total_fact = 0

    if group_id:
        group = Group.query.get(group_id)
        query = Workload.query.filter_by(group_id=group_id)

        if semester:
            query = query.filter_by(semester=semester)

        workloads = query.order_by(Workload.discipline).all()

        total_plan = sum(w.total_hours for w in workloads)
        total_fact = sum(w.hours_completed_actual for w in workloads)

    return render_template('reports/hours.html',
                           groups=groups,
                           group=group,
                           workloads=workloads,
                           selected_group=group_id,
                           selected_semester=semester,
                           total_plan=total_plan,
                           total_fact=total_fact)


@bp.route('/hours/export')
def hours_export():
    """Export hours report to Excel"""
    group_id = request.args.get('group_id', type=int)
    semester = request.args.get('semester', type=int)

    if not group_id:
        flash('Выберите группу', 'error')
        return redirect(url_for('reports.hours'))

    group = Group.query.get_or_404(group_id)
    query = Workload.query.filter_by(group_id=group_id)

    if semester:
        query = query.filter_by(semester=semester)

    workloads = query.order_by(Workload.discipline).all()

    exporter = ExcelExporter(Config.EXPORTS_DIR)
    filepath = exporter.export_hours_report(group, workloads, semester or 0)

    return send_file(filepath, as_attachment=True)


@bp.route('/teacher')
def teacher():
    """Teacher timesheet"""
    teacher_id = request.args.get('teacher_id', type=int)
    month = request.args.get('month', type=int) or datetime.now().month
    year = request.args.get('year', type=int) or datetime.now().year

    teachers = Teacher.query.order_by(Teacher.full_name).all()
    teacher = None
    workload_hours = {}
    total_main_hours = 0
    total_substitution_hours = 0

    if teacher_id:
        teacher = Teacher.query.get(teacher_id)

        # Get schedules for the month
        from calendar import monthrange
        from datetime import date
        _, last_day = monthrange(year, month)

        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day).date()

        # Get main schedules (where this teacher is the assigned teacher)
        # If status is done/completed, it means the lesson was conducted
        main_schedules = Schedule.query.join(Workload).filter(
            Workload.teacher_id == teacher_id,
            Schedule.date >= start_date,
            Schedule.date <= end_date,
            Schedule.status.in_(['done', 'completed'])
        ).all()

        # Get substitution schedules (where this teacher substituted for someone else)
        # Substitutions count immediately when assigned (hours are transferred to substitute teacher)
        sub_schedules = Schedule.query.filter(
            Schedule.substitute_teacher_id == teacher_id,
            Schedule.date >= start_date,
            Schedule.date <= end_date,
            Schedule.status == 'substitution'
        ).all()

        # Group main schedules by workload
        for s in main_schedules:
            wl_id = s.workload_id
            if wl_id not in workload_hours:
                workload_hours[wl_id] = {
                    'workload': s.workload,
                    'hours': 0,
                    'substitution_hours': 0
                }
            workload_hours[wl_id]['hours'] += 2

        # Group substitution schedules by the original workload
        for s in sub_schedules:
            # Create a unique key for substitution entries
            sub_key = f"sub_{s.workload_id}"
            if sub_key not in workload_hours:
                workload_hours[sub_key] = {
                    'workload': s.workload,
                    'hours': 0,
                    'substitution_hours': 0,
                    'is_substitution': True
                }
            workload_hours[sub_key]['substitution_hours'] += 2

        # Calculate totals
        total_main_hours = sum(wh['hours'] for wh in workload_hours.values())
        total_substitution_hours = sum(wh.get('substitution_hours', 0) for wh in workload_hours.values())

    months_ru = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }

    return render_template('reports/teacher.html',
                           teachers=teachers,
                           teacher=teacher,
                           selected_teacher=teacher_id,
                           month=month,
                           year=year,
                           months_ru=months_ru,
                           workload_hours=workload_hours,
                           total_main_hours=total_main_hours,
                           total_substitution_hours=total_substitution_hours,
                           total_hours=total_main_hours + total_substitution_hours)


@bp.route('/teacher/export')
def teacher_export():
    """Export teacher timesheet to Excel"""
    teacher_id = request.args.get('teacher_id', type=int)
    month = request.args.get('month', type=int) or datetime.now().month
    year = request.args.get('year', type=int) or datetime.now().year

    if not teacher_id:
        flash('Выберите преподавателя', 'error')
        return redirect(url_for('reports.teacher'))

    teacher = Teacher.query.get_or_404(teacher_id)

    from calendar import monthrange
    _, last_day = monthrange(year, month)
    start_date = datetime(year, month, 1).date()
    end_date = datetime(year, month, last_day).date()

    schedules = Schedule.query.join(Workload).filter(
        Workload.teacher_id == teacher_id,
        Schedule.date >= start_date,
        Schedule.date <= end_date
    ).all()

    exporter = ExcelExporter(Config.EXPORTS_DIR)
    filepath = exporter.export_teacher_timesheet_ministry(teacher, month, year)

    return send_file(filepath, as_attachment=True)


@bp.route('/period')
def period():
    """Timesheet report by week/period"""
    year_id = request.args.get('year_id', type=int)
    week_number = request.args.get('week', type=int)

    academic_years = AcademicYear.query.order_by(AcademicYear.start_date.desc()).all()

    # Default to current year
    if not year_id:
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if current_year:
            year_id = current_year.id

    selected_year = AcademicYear.query.get(year_id) if year_id else None

    weeks = []
    period = None
    teacher_data = []
    total_pairs = 0
    total_hours = 0

    if selected_year:
        # Get all periods for the academic year
        all_periods = SchedulePeriod.query.filter_by(
            academic_year_id=year_id
        ).order_by(SchedulePeriod.week_number).all()

        weeks = all_periods

        if week_number:
            period = SchedulePeriod.query.filter_by(
                academic_year_id=year_id,
                week_number=week_number
            ).first()

            if period:
                # Get all schedules for this period - only past dates
                from datetime import date
                today = date.today()
                schedules = Schedule.query.join(Workload).filter(
                    Schedule.date >= period.start_date,
                    Schedule.date <= period.end_date,
                    Schedule.date < today,  # Only past dates
                    Schedule.status.in_(['done', 'completed', 'substitution'])
                ).all()

                # Group by teacher
                teacher_hours = {}
                for s in schedules:
                    teacher = s.workload.teacher

                    # Check if it's a substitution
                    if s.status == 'substitution' and s.substitute_teacher_id:
                        teacher = Teacher.query.get(s.substitute_teacher_id)

                    if teacher.id not in teacher_hours:
                        teacher_hours[teacher.id] = {
                            'teacher': teacher,
                            'pairs': 0,
                            'disciplines': {}
                        }

                    teacher_hours[teacher.id]['pairs'] += 1
                    discipline = s.workload.discipline
                    if discipline not in teacher_hours[teacher.id]['disciplines']:
                        teacher_hours[teacher.id]['disciplines'][discipline] = 0
                    teacher_hours[teacher.id]['disciplines'][discipline] += 1

                teacher_data = sorted(teacher_hours.values(), key=lambda x: x['teacher'].full_name)
                total_pairs = sum(t['pairs'] for t in teacher_data)
                total_hours = total_pairs * 2

    return render_template('reports/period.html',
                           academic_years=academic_years,
                           selected_year=selected_year,
                           weeks=weeks,
                           selected_week=week_number,
                           period=period,
                           teacher_data=teacher_data,
                           total_pairs=total_pairs,
                           total_hours=total_hours)


@bp.route('/period/export')
def period_export():
    """Export period timesheet to Excel"""
    year_id = request.args.get('year_id', type=int)
    week_number = request.args.get('week', type=int)

    if not year_id or not week_number:
        flash('Выберите период', 'error')
        return redirect(url_for('reports.period'))

    period = SchedulePeriod.query.filter_by(
        academic_year_id=year_id,
        week_number=week_number
    ).first()

    if not period:
        flash('Период не найден', 'error')
        return redirect(url_for('reports.period', year_id=year_id))

    selected_year = AcademicYear.query.get(year_id)

    # Get all schedules for this period - only past dates
    from datetime import date
    today = date.today()
    schedules = Schedule.query.join(Workload).filter(
        Schedule.date >= period.start_date,
        Schedule.date <= period.end_date,
        Schedule.date < today,  # Only past dates
        Schedule.status.in_(['done', 'completed', 'substitution'])
    ).all()

    exporter = ExcelExporter(Config.EXPORTS_DIR)
    filepath = exporter.export_period_timesheet(period, schedules, selected_year)

    return send_file(filepath, as_attachment=True)


@bp.route('/substitutions')
def substitutions():
    """Отчет по заменам преподавателей"""
    teacher_id = request.args.get('teacher_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    
    # Парсим даты
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Получаем данные по заменам
    substitution_query = db.session.query(
        Schedule,
        Teacher.label('substitute_teacher'),
        Teacher.label('original_teacher')
    ).join(
        Teacher, Schedule.substitute_teacher_id == Teacher.id
    ).join(
        Workload, Schedule.workload_id == Workload.id
    ).join(
        Teacher.label('original_teacher'), Workload.teacher_id == Teacher.id
    ).filter(
        Schedule.status == 'substitution'
    )
    
    if teacher_id:
        # Показываем либо замены ДЛЯ преподавателя, либо замены преподавателя
        substitution_query = substitution_query.filter(
            db.or_(
                Schedule.substitute_teacher_id == teacher_id,
                Workload.teacher_id == teacher_id
            )
        )
    
    if start_date:
        substitution_query = substitution_query.filter(Schedule.date >= start_date)
    if end_date:
        substitution_query = substitution_query.filter(Schedule.date <= end_date)
    
    substitutions = substitution_query.order_by(
        Schedule.date.desc(), 
        Schedule.pair_number
    ).all()
    
    # Группируем по преподавателям
    teacher_stats = {}
    for schedule, substitute_teacher, original_teacher in substitutions:
        # Статистика для заменителя (сколько часов провел)
        if substitute_teacher.id not in teacher_stats:
            teacher_stats[substitute_teacher.id] = {
                'teacher': substitute_teacher,
                'substitution_hours': 0,
                'vacant_hours': 0
            }
        teacher_stats[substitute_teacher.id]['substitution_hours'] += 2
        
        # Статистика для замененного (сколько часов стало вакантными)
        if original_teacher.id not in teacher_stats:
            teacher_stats[original_teacher.id] = {
                'teacher': original_teacher,
                'substitution_hours': 0,
                'vacant_hours': 0
            }
        teacher_stats[original_teacher.id]['vacant_hours'] += 2
    
    return render_template('reports/substitutions.html',
                         teachers=teachers,
                         selected_teacher=teacher_id,
                         start_date=start_date.isoformat() if start_date else '',
                         end_date=end_date.isoformat() if end_date else '',
                         substitutions=substitutions,
                         teacher_stats=teacher_stats)


@bp.route('/schedule_changes')
def schedule_changes():
    """Отчет по всем изменениям в расписании"""
    change_type = request.args.get('change_type', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    teacher_id = request.args.get('teacher_id', type=int)
    
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    
    # Парсим даты
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Базовый запрос
    changes_query = ScheduleChange.query.join(Schedule)
    
    if change_type:
        changes_query = changes_query.filter(ScheduleChange.change_type == change_type)
        
    if start_date:
        changes_query = changes_query.filter(Schedule.date >= start_date)
    if end_date:
        changes_query = changes_query.filter(Schedule.date <= end_date)
        
    if teacher_id:
        changes_query = changes_query.join(Workload).filter(
            db.or_(
                Workload.teacher_id == teacher_id,
                ScheduleChange.new_teacher_id == teacher_id,
                ScheduleChange.old_teacher_id == teacher_id
            )
        )
    
    changes = changes_query.order_by(ScheduleChange.changed_at.desc()).all()
    
    # Статистика по типам изменений
    change_stats = db.session.query(
        ScheduleChange.change_type,
        db.func.count(ScheduleChange.id).label('count')
    ).group_by(ScheduleChange.change_type).all()
    
    return render_template('reports/schedule_changes.html',
                         teachers=teachers,
                         selected_teacher=teacher_id,
                         selected_change_type=change_type,
                         start_date=start_date.isoformat() if start_date else '',
                         end_date=end_date.isoformat() if end_date else '',
                         changes=changes,
                         change_stats=change_stats)


@bp.route('/teacher/<int:teacher_id>/summary')
def teacher_summary(teacher_id):
    """Сводка по часам преподавателя с учетом замен"""
    teacher = Teacher.query.get_or_404(teacher_id)
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Получаем сводку по часам
    summary = teacher.get_hours_summary(start_date, end_date)
    
    # Детализация по заменам
    substitutions = Schedule.query.filter(
        Schedule.substitute_teacher_id == teacher_id,
        Schedule.status == 'substitution'
    )
    
    # Детализация по вакантным часам
    vacant_schedules = Schedule.query.join(Workload).filter(
        Workload.teacher_id == teacher_id,
        Schedule.status == 'substitution',
        Schedule.substitute_teacher_id.isnot(None)
    )
    
    if start_date:
        substitutions = substitutions.filter(Schedule.date >= start_date)
        vacant_schedules = vacant_schedules.filter(Schedule.date >= start_date)
    if end_date:
        substitutions = substitutions.filter(Schedule.date <= end_date)
        vacant_schedules = vacant_schedules.filter(Schedule.date <= end_date)
        
    substitutions = substitutions.order_by(Schedule.date.desc()).all()
    vacant_schedules = vacant_schedules.order_by(Schedule.date.desc()).all()
    
    return render_template('reports/teacher_summary.html',
                         teacher=teacher,
                         summary=summary,
                         substitutions=substitutions,
                         vacant_schedules=vacant_schedules,
                         start_date=start_date.isoformat() if start_date else '',
                         end_date=end_date.isoformat() if end_date else '')


@bp.route('/vacant_hours')
def vacant_hours():
    """Отчет по вакантным часам"""
    teacher_id = request.args.get('teacher_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    
    # Парсим даты
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Получаем сводку по вакантным часам
    vacant_summary = None
    substitute_summary = None
    
    if teacher_id:
        teacher = Teacher.query.get(teacher_id)
        if teacher:
            # Вакантные часы (когда этого преподавателя заменяли)
            vacant_summary = VacantHours.get_teacher_vacant_summary(teacher_id, start_date, end_date)
            # Замены (когда этот преподаватель заменял других)
            substitute_summary = VacantHours.get_substitute_summary(teacher_id, start_date, end_date)
    
    # Общая статистика по всем вакантным часам в системе
    overall_query = VacantHours.query
    
    if start_date:
        overall_query = overall_query.filter(VacantHours.date >= start_date)
    if end_date:
        overall_query = overall_query.filter(VacantHours.date <= end_date)
    
    all_vacant_records = overall_query.all()
    
    # Группируем по преподавателям
    teacher_vacant_stats = {}
    teacher_substitute_stats = {}
    
    for record in all_vacant_records:
        # Статистика для тех, кого заменяли
        original_id = record.original_teacher_id
        if original_id not in teacher_vacant_stats:
            teacher_vacant_stats[original_id] = {
                'teacher': record.original_teacher,
                'total_hours': 0,
                'total_pairs': 0
            }
        teacher_vacant_stats[original_id]['total_hours'] += record.hours
        teacher_vacant_stats[original_id]['total_pairs'] += 1
        
        # Статистика для тех, кто заменял
        substitute_id = record.substitute_teacher_id
        if substitute_id not in teacher_substitute_stats:
            teacher_substitute_stats[substitute_id] = {
                'teacher': record.substitute_teacher,
                'total_hours': 0,
                'total_pairs': 0
            }
        teacher_substitute_stats[substitute_id]['total_hours'] += record.hours
        teacher_substitute_stats[substitute_id]['total_pairs'] += 1
    
    return render_template('reports/vacant_hours.html',
                         teachers=teachers,
                         selected_teacher=teacher_id,
                         start_date=start_date.isoformat() if start_date else '',
                         end_date=end_date.isoformat() if end_date else '',
                         vacant_summary=vacant_summary,
                         substitute_summary=substitute_summary,
                         teacher_vacant_stats=teacher_vacant_stats,
                         teacher_substitute_stats=teacher_substitute_stats,
                         all_vacant_records=all_vacant_records)


@bp.route('/analytics')
def analytics():
    """Analytics page with monthly schedule breakdown by group/teacher"""
    from app.models import Group, Teacher, Schedule, Workload
    from calendar import monthrange
    import calendar
    
    # Get filters from request
    group_id = request.args.get('group_id', type=int)
    teacher_id = request.args.get('teacher_id', type=int)
    month = request.args.get('month', type=int) or datetime.now().month
    year = request.args.get('year', type=int) or datetime.now().year
    
    # Get all groups and teachers for filters
    groups = Group.query.order_by(Group.name).all()
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    
    # Month names in Russian
    months_ru = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    
    # Get date range for the month
    _, last_day = monthrange(year, month)
    start_date = datetime(year, month, 1).date()
    end_date = datetime(year, month, last_day).date()
    
    # Initialize data structures
    analytics_data = []
    days_in_month = list(range(1, last_day + 1))
    
    if group_id:
        # Group-based analytics
        group = Group.query.get(group_id)
        if group:
            from datetime import date
            today = date.today()

            # Get all workloads for this group
            workloads = Workload.query.filter_by(group_id=group_id).all()

            for workload in workloads:
                # Get ALL schedules for display
                schedules = Schedule.query.filter(
                    Schedule.workload_id == workload.id,
                    Schedule.date >= start_date,
                    Schedule.date <= end_date
                ).all()

                daily_hours = {}  # For display
                daily_hours_counted = {}  # For totals

                for schedule in schedules:
                    day = schedule.date.day

                    # Initialize day data
                    if day not in daily_hours:
                        daily_hours[day] = {
                            'hours': 0,
                            'substituted': False,
                            'substitute_name': None,
                            'cancelled': False,
                            'rescheduled': False,
                            'details': []  # List of schedule details for tooltip
                        }

                    # Display all scheduled hours
                    daily_hours[day]['hours'] += 2

                    # Build detail info for tooltip
                    detail = {
                        'pair': schedule.pair_number,
                        'time': f"{schedule.time_start}-{schedule.time_end}",
                        'status': schedule.status,
                        'reason': schedule.change_reason or ''
                    }

                    # Mark by status
                    if schedule.status == 'cancelled':
                        daily_hours[day]['cancelled'] = True
                        detail['status_text'] = 'Отменено'
                    elif schedule.status == 'rescheduled':
                        daily_hours[day]['rescheduled'] = True
                        detail['status_text'] = 'Перенесено'
                    elif schedule.status == 'substitution' and schedule.substitute_teacher_id:
                        daily_hours[day]['substituted'] = True
                        if schedule.substitute_teacher:
                            daily_hours[day]['substitute_name'] = schedule.substitute_teacher.full_name
                            detail['substitute'] = schedule.substitute_teacher.full_name
                            detail['status_text'] = f"Замена: {schedule.substitute_teacher.full_name}"
                    else:
                        detail['status_text'] = 'Проведено' if schedule.status in ['done', 'completed'] else 'Запланировано'

                    daily_hours[day]['details'].append(detail)

                    # Count conducted pairs (past dates)
                    # done, completed, substitution, rescheduled = count for group
                    # cancelled = NOT count
                    if schedule.date < today and schedule.status in ['done', 'completed', 'substitution', 'rescheduled']:
                        if day not in daily_hours_counted:
                            daily_hours_counted[day] = 0
                        daily_hours_counted[day] += 2

                # Determine effective teacher (considering substitutions)
                effective_teacher = workload.teacher.full_name
                if schedules:
                    substitutions = [s for s in schedules if s.status == 'substitution' and s.substitute_teacher_id]
                    if substitutions:
                        substitute_names = list(set([s.substitute_teacher.full_name for s in substitutions if s.substitute_teacher]))
                        if substitute_names:
                            effective_teacher += f" (замены: {', '.join(substitute_names)})"

                # Only add if there are any schedules
                if daily_hours:
                    analytics_data.append({
                        'discipline': workload.discipline,
                        'teacher': effective_teacher,
                        'workload': workload,
                        'daily_hours': daily_hours,
                        'daily_hours_counted': daily_hours_counted,
                        'total_hours': sum(daily_hours_counted.values())
                    })
    
    elif teacher_id:
        # Teacher-based analytics
        teacher = Teacher.query.get(teacher_id)
        if teacher:
            from datetime import date
            today = date.today()

            # Get all workloads for this teacher
            workloads = Workload.query.filter_by(teacher_id=teacher_id).all()

            # Also get substitution schedules (where this teacher substituted for someone else) - only past dates count
            substitution_schedules = Schedule.query.filter(
                Schedule.substitute_teacher_id == teacher_id,
                Schedule.date >= start_date,
                Schedule.date <= end_date,
                Schedule.status == 'substitution'
            ).all()

            # Process regular workloads - show ALL schedules but count only conducted
            for workload in workloads:
                if workload.discipline.startswith('ЗАМЕНА:'):
                    continue  # Skip substitution workloads, we'll handle them separately

                # Get ALL schedules for display (including future)
                schedules = Schedule.query.filter(
                    Schedule.workload_id == workload.id,
                    Schedule.date >= start_date,
                    Schedule.date <= end_date
                ).all()

                daily_hours = {}  # For display - ALL schedules
                daily_hours_counted = {}  # For total - only conducted by this teacher
                substituted_days = {}  # Days where someone else taught

                for schedule in schedules:
                    day = schedule.date.day

                    # Initialize day data
                    if day not in daily_hours:
                        daily_hours[day] = {
                            'hours': 0,
                            'substituted': False,
                            'substitute_name': None,
                            'cancelled': False,
                            'rescheduled': False,
                            'details': []
                        }

                    # Display all scheduled hours
                    daily_hours[day]['hours'] += 2

                    # Build detail info for tooltip
                    detail = {
                        'pair': schedule.pair_number,
                        'time': f"{schedule.time_start}-{schedule.time_end}",
                        'status': schedule.status,
                        'reason': schedule.change_reason or ''
                    }

                    # Mark by status
                    if schedule.status == 'cancelled':
                        daily_hours[day]['cancelled'] = True
                        detail['status_text'] = 'Отменено'
                    elif schedule.status == 'rescheduled':
                        daily_hours[day]['rescheduled'] = True
                        detail['status_text'] = 'Перенесено'
                    elif schedule.status == 'substitution' and schedule.substitute_teacher_id:
                        daily_hours[day]['substituted'] = True
                        if schedule.substitute_teacher:
                            daily_hours[day]['substitute_name'] = schedule.substitute_teacher.full_name
                            detail['substitute'] = schedule.substitute_teacher.full_name
                            detail['status_text'] = f"Замена: {schedule.substitute_teacher.full_name}"
                    else:
                        detail['status_text'] = 'Проведено' if schedule.status in ['done', 'completed'] else 'Запланировано'

                    daily_hours[day]['details'].append(detail)

                    # Count only conducted hours by this teacher (past dates)
                    # done, completed, rescheduled = count
                    # substitution = NOT count (someone else conducted)
                    # cancelled = NOT count
                    if schedule.date < today and schedule.status in ['done', 'completed', 'rescheduled']:
                        if day not in daily_hours_counted:
                            daily_hours_counted[day] = 0
                        daily_hours_counted[day] += 2

                group_name = workload.group.name if workload.group else 'Без группы'

                # Only add if there are any schedules
                if daily_hours:
                    analytics_data.append({
                        'discipline': workload.discipline,
                        'teacher': group_name,
                        'workload': workload,
                        'daily_hours': daily_hours,  # For display (all)
                        'daily_hours_counted': daily_hours_counted,  # For totals (conducted only)
                        'total_hours': sum(daily_hours_counted.values())  # Only counted hours
                    })

            # Process substitutions (where this teacher substituted for others) - group by workload
            if substitution_schedules:
                # Group substitutions by workload
                sub_by_workload = {}
                for schedule in substitution_schedules:
                    wl_id = schedule.workload_id
                    if wl_id not in sub_by_workload:
                        sub_by_workload[wl_id] = {
                            'workload': schedule.workload,
                            'schedules': []
                        }
                    sub_by_workload[wl_id]['schedules'].append(schedule)

                # Create analytics entry for each substituted workload
                for wl_id, data in sub_by_workload.items():
                    workload = data['workload']
                    schedules = data['schedules']

                    daily_hours = {}
                    daily_hours_counted = {}

                    for schedule in schedules:
                        day = schedule.date.day

                        # Display all substitutions (marked as substitute conducting)
                        if day not in daily_hours:
                            daily_hours[day] = {
                                'hours': 0,
                                'substituted': False,
                                'is_substitute_conducting': True,
                                'details': []
                            }
                        daily_hours[day]['hours'] += 2

                        # Build detail info for tooltip
                        original_teacher = workload.teacher.full_name if workload.teacher else 'Неизвестно'
                        detail = {
                            'pair': schedule.pair_number,
                            'time': f"{schedule.time_start}-{schedule.time_end}",
                            'status': 'substitution',
                            'status_text': f"Замена за: {original_teacher}",
                            'original_teacher': original_teacher,
                            'reason': schedule.change_reason or ''
                        }
                        daily_hours[day]['details'].append(detail)

                        # Count substitutions immediately when assigned (hours transferred to substitute teacher)
                        if day not in daily_hours_counted:
                            daily_hours_counted[day] = 0
                        daily_hours_counted[day] += 2

                    group_name = workload.group.name if workload.group else 'Без группы'
                    original_teacher = workload.teacher.full_name if workload.teacher else 'Неизвестно'

                    analytics_data.append({
                        'discipline': f"[ЗАМЕНА] {workload.discipline}",
                        'teacher': f"{group_name} (за {original_teacher})",
                        'workload': workload,
                        'daily_hours': daily_hours,
                        'daily_hours_counted': daily_hours_counted,
                        'total_hours': sum(daily_hours_counted.values()),
                        'is_substitution_entry': True
                    })
    
    # Calculate daily totals for footer (use counted hours, not all displayed hours)
    daily_totals = {}
    for day in days_in_month:
        total = 0
        for data in analytics_data:
            # Use daily_hours_counted if available (new format), otherwise daily_hours
            if 'daily_hours_counted' in data:
                total += data['daily_hours_counted'].get(day, 0)
            else:
                day_data = data['daily_hours'].get(day, 0)
                if isinstance(day_data, dict):
                    total += day_data.get('hours', 0) if not day_data.get('substituted') else 0
                else:
                    total += day_data
        daily_totals[day] = total
    
    return render_template('reports/analytics.html',
                           groups=groups,
                           teachers=teachers,
                           selected_group=group_id,
                           selected_teacher=teacher_id,
                           month=month,
                           year=year,
                           months_ru=months_ru,
                           days_in_month=days_in_month,
                           analytics_data=analytics_data,
                           daily_totals=daily_totals,
                           start_date=start_date,
                           end_date=end_date)
