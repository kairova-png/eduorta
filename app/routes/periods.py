from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from app import db
from app.models import SchedulePeriod, AcademicYear, GUP, Schedule, Workload, Group

bp = Blueprint('periods', __name__, url_prefix='/periods')


@bp.route('/')
def index():
    """List all schedule periods"""
    year_id = request.args.get('year_id', type=int)

    academic_years = AcademicYear.query.order_by(AcademicYear.start_date.desc()).all()

    # Default to current year
    if not year_id:
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if current_year:
            year_id = current_year.id

    selected_year = AcademicYear.query.get(year_id) if year_id else None

    periods = []
    gup_weeks = []

    if selected_year:
        # Get existing periods
        periods = SchedulePeriod.query.filter_by(
            academic_year_id=year_id
        ).order_by(SchedulePeriod.week_number).all()

        # Get all GUP weeks (unique by week_number)
        gup_weeks_query = db.session.query(
            GUP.week_number,
            GUP.start_date,
            GUP.end_date
        ).filter_by(academic_year_id=year_id).distinct(GUP.week_number).order_by(GUP.week_number).all()

        # Build weeks data with period info
        periods_dict = {p.week_number: p for p in periods}

        for week in gup_weeks_query:
            period = periods_dict.get(week.week_number)

            # Count schedule entries for this week
            schedule_count = 0
            if week.start_date and week.end_date:
                schedule_count = Schedule.query.filter(
                    Schedule.date >= week.start_date,
                    Schedule.date <= week.end_date
                ).count()

            gup_weeks.append({
                'week_number': week.week_number,
                'start_date': week.start_date,
                'end_date': week.end_date,
                'period': period,
                'schedule_count': schedule_count
            })

    return render_template('periods/index.html',
                           academic_years=academic_years,
                           selected_year=selected_year,
                           periods=periods,
                           gup_weeks=gup_weeks)


@bp.route('/close/<int:week_number>', methods=['POST'])
def close_week(week_number):
    """Close a week for editing"""
    year_id = request.form.get('year_id', type=int)

    if not year_id:
        flash('Учебный год не выбран', 'error')
        return redirect(url_for('periods.index'))

    # Get GUP data for this week
    gup = GUP.query.filter_by(
        academic_year_id=year_id,
        week_number=week_number
    ).first()

    if not gup or not gup.start_date:
        flash('Неделя не найдена в ГУП', 'error')
        return redirect(url_for('periods.index', year_id=year_id))

    # Check if period already exists
    period = SchedulePeriod.query.filter_by(
        academic_year_id=year_id,
        week_number=week_number
    ).first()

    if period:
        # Update existing
        period.status = 'closed'
        period.closed_at = datetime.utcnow()
        period.closed_by = 'admin'  # TODO: actual user
    else:
        # Create new
        period = SchedulePeriod(
            academic_year_id=year_id,
            week_number=week_number,
            start_date=gup.start_date,
            end_date=gup.end_date,
            status='closed',
            closed_at=datetime.utcnow(),
            closed_by='admin'
        )
        db.session.add(period)

    db.session.commit()
    flash(f'Неделя {week_number} закрыта для редактирования', 'success')
    return redirect(url_for('periods.index', year_id=year_id))


@bp.route('/open/<int:week_number>', methods=['POST'])
def open_week(week_number):
    """Reopen a week for editing"""
    year_id = request.form.get('year_id', type=int)

    if not year_id:
        flash('Учебный год не выбран', 'error')
        return redirect(url_for('periods.index'))

    period = SchedulePeriod.query.filter_by(
        academic_year_id=year_id,
        week_number=week_number
    ).first()

    if period:
        period.status = 'open'
        period.closed_at = None
        period.closed_by = None
        db.session.commit()
        flash(f'Неделя {week_number} открыта для редактирования', 'success')

    return redirect(url_for('periods.index', year_id=year_id))


@bp.route('/close-range', methods=['POST'])
def close_range():
    """Close multiple weeks at once"""
    year_id = request.form.get('year_id', type=int)
    week_from = request.form.get('week_from', type=int)
    week_to = request.form.get('week_to', type=int)

    if not year_id or not week_from or not week_to:
        flash('Укажите учебный год и диапазон недель', 'error')
        return redirect(url_for('periods.index', year_id=year_id))

    closed_count = 0
    for week_num in range(week_from, week_to + 1):
        # Get GUP data
        gup = GUP.query.filter_by(
            academic_year_id=year_id,
            week_number=week_num
        ).first()

        if not gup or not gup.start_date:
            continue

        period = SchedulePeriod.query.filter_by(
            academic_year_id=year_id,
            week_number=week_num
        ).first()

        if period:
            if period.status != 'closed':
                period.status = 'closed'
                period.closed_at = datetime.utcnow()
                period.closed_by = 'admin'
                closed_count += 1
        else:
            period = SchedulePeriod(
                academic_year_id=year_id,
                week_number=week_num,
                start_date=gup.start_date,
                end_date=gup.end_date,
                status='closed',
                closed_at=datetime.utcnow(),
                closed_by='admin'
            )
            db.session.add(period)
            closed_count += 1

    db.session.commit()
    flash(f'Закрыто недель: {closed_count}', 'success')
    return redirect(url_for('periods.index', year_id=year_id))


@bp.route('/<int:week_number>/details')
def week_details(week_number):
    """View details for a specific week"""
    year_id = request.args.get('year_id', type=int)

    if not year_id:
        flash('Учебный год не выбран', 'error')
        return redirect(url_for('periods.index'))

    selected_year = AcademicYear.query.get_or_404(year_id)

    # Get GUP data
    gup = GUP.query.filter_by(
        academic_year_id=year_id,
        week_number=week_number
    ).first()

    if not gup or not gup.start_date:
        flash('Неделя не найдена', 'error')
        return redirect(url_for('periods.index', year_id=year_id))

    # Get period info
    period = SchedulePeriod.query.filter_by(
        academic_year_id=year_id,
        week_number=week_number
    ).first()

    # Get schedules for this week grouped by teacher
    schedules = Schedule.query.join(Workload).filter(
        Schedule.date >= gup.start_date,
        Schedule.date <= gup.end_date
    ).order_by(Schedule.date, Schedule.pair_number).all()

    # Group by teacher
    teacher_schedules = {}
    for s in schedules:
        teacher = s.workload.teacher
        if teacher.id not in teacher_schedules:
            teacher_schedules[teacher.id] = {
                'teacher': teacher,
                'schedules': [],
                'total_pairs': 0,
                'done_pairs': 0
            }
        teacher_schedules[teacher.id]['schedules'].append(s)
        teacher_schedules[teacher.id]['total_pairs'] += 1
        if s.status in ['done', 'completed', 'substitution']:
            teacher_schedules[teacher.id]['done_pairs'] += 1

    return render_template('periods/week_details.html',
                           selected_year=selected_year,
                           week_number=week_number,
                           gup=gup,
                           period=period,
                           teacher_schedules=teacher_schedules)
