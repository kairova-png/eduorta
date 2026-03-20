from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import GUP, Group, AcademicYear, Specialty
from datetime import date, datetime, timedelta

bp = Blueprint('gup', __name__, url_prefix='/gup')

# Activity codes and their colors/names (from GUP legend)
ACTIVITY_TYPES = {
    '': {
        'name': '',
        'name_kz': '',
        'full_name': 'Теоретическое обучение',
        'full_name_kz': 'Теориялық оқыту',
        'color': '#FFFFFF',
        'text': '#000'
    },
    '::': {
        'name': '::',
        'name_kz': '::',
        'full_name': 'Промежуточная аттестация',
        'full_name_kz': 'Аралық аттестация',
        'color': '#FFE4B5',
        'text': '#000'
    },
    'К': {
        'name': 'К',
        'name_kz': 'К',
        'full_name': 'Каникулы',
        'full_name_kz': 'Каникулдар',
        'color': '#90EE90',
        'text': '#000'
    },
    'ПС': {
        'name': 'ПС',
        'name_kz': 'ДЖ',
        'full_name': 'Полевые сборы',
        'full_name_kz': 'Дала жиыны',
        'color': '#D2B48C',
        'text': '#000'
    },
    'ДЖ': {
        'name': 'ПС',
        'name_kz': 'ДЖ',
        'full_name': 'Полевые сборы',
        'full_name_kz': 'Дала жиыны',
        'color': '#D2B48C',
        'text': '#000'
    },
    'ВС': {
        'name': 'ВС',
        'name_kz': 'ТТ',
        'full_name': 'Ознакомительная практика (введение в специальность)',
        'full_name_kz': 'Таныстыру тәжірибесі',
        'color': '#E6E6FA',
        'text': '#000'
    },
    'ТТ': {
        'name': 'ВС',
        'name_kz': 'ТТ',
        'full_name': 'Ознакомительная практика (введение в специальность)',
        'full_name_kz': 'Таныстыру тәжірибесі',
        'color': '#E6E6FA',
        'text': '#000'
    },
    'ӨО': {
        'name': 'ӨО',
        'name_kz': 'ӨО',
        'full_name': 'Производственное обучение',
        'full_name_kz': 'Өндірістік оқыту',
        'color': '#F0E68C',
        'text': '#000'
    },
    'П': {
        'name': 'П',
        'name_kz': 'КП',
        'full_name': 'Производственная практика',
        'full_name_kz': 'Кәсіби практика',
        'color': '#87CEEB',
        'text': '#000'
    },
    'КП': {
        'name': 'П',
        'name_kz': 'КП',
        'full_name': 'Производственная практика',
        'full_name_kz': 'Кәсіби практика',
        'color': '#87CEEB',
        'text': '#000'
    },
    'И': {
        'name': 'И',
        'name_kz': 'ҚА',
        'full_name': 'Итоговая аттестация',
        'full_name_kz': 'Қорытынды аттестация',
        'color': '#FFB6C1',
        'text': '#000'
    },
    'ҚА': {
        'name': 'И',
        'name_kz': 'ҚА',
        'full_name': 'Итоговая аттестация',
        'full_name_kz': 'Қорытынды аттестация',
        'color': '#FFB6C1',
        'text': '#000'
    },
    '*': {
        'name': '*',
        'name_kz': '*',
        'full_name': 'Праздничные дни',
        'full_name_kz': 'Мерекелік күндер',
        'color': '#FF6347',
        'text': '#FFF'
    },
    'УП': {
        'name': 'УП',
        'name_kz': 'ОТ',
        'full_name': 'Учебная практика по модулю',
        'full_name_kz': 'Оқу тәжірибесі модуль бойынша',
        'color': '#DDA0DD',
        'text': '#000'
    },
    'ОТ': {
        'name': 'УП',
        'name_kz': 'ОТ',
        'full_name': 'Учебная практика по модулю',
        'full_name_kz': 'Оқу тәжірибесі модуль бойынша',
        'color': '#DDA0DD',
        'text': '#000'
    },
}


@bp.route('/')
def index():
    """GUP main page - show all groups with their GUP"""
    # Get current academic year
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    academic_years = AcademicYear.query.order_by(AcademicYear.name.desc()).all()

    year_id = request.args.get('year_id', type=int)
    if not year_id and current_year:
        year_id = current_year.id

    selected_year = AcademicYear.query.get(year_id) if year_id else None

    # Filters
    specialty_id = request.args.get('specialty_id', type=int)
    course = request.args.get('course', type=int)

    # Get specialties for filter
    specialties = Specialty.query.order_by(Specialty.code).all()

    # Get groups with GUP data
    groups_query = Group.query
    if specialty_id:
        groups_query = groups_query.filter_by(specialty_id=specialty_id)

    groups = groups_query.order_by(Group.name).all()

    # Filter by course if specified
    if course:
        groups = [g for g in groups if g.course == course]

    # Build GUP data structure
    # {group_id: {week_number: activity_code}}
    gup_data = {}
    weeks_info = {}

    if selected_year:
        # Get all GUP entries for selected year
        gup_entries = GUP.query.filter_by(academic_year_id=selected_year.id).all()

        for entry in gup_entries:
            if entry.group_id not in gup_data:
                gup_data[entry.group_id] = {}
            gup_data[entry.group_id][entry.week_number] = entry.activity_code or ''

            # Store week info (dates)
            if entry.week_number not in weeks_info:
                weeks_info[entry.week_number] = {
                    'start': entry.start_date,
                    'end': entry.end_date
                }

    # Generate week numbers (1-52)
    weeks = list(range(1, 53))

    # Semester breaks (approximate)
    semester_1_weeks = list(range(1, 18))  # Sep - Dec
    semester_2_weeks = list(range(18, 53))  # Jan - Aug

    return render_template('gup/index.html',
                           groups=groups,
                           gup_data=gup_data,
                           weeks=weeks,
                           weeks_info=weeks_info,
                           semester_1_weeks=semester_1_weeks,
                           semester_2_weeks=semester_2_weeks,
                           activity_types=ACTIVITY_TYPES,
                           academic_years=academic_years,
                           selected_year=selected_year,
                           specialties=specialties,
                           selected_specialty=specialty_id,
                           selected_course=course)


@bp.route('/group/<int:group_id>')
def group_detail(group_id):
    """Show detailed GUP for a specific group"""
    group = Group.query.get_or_404(group_id)

    # Get current academic year
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    year_id = request.args.get('year_id', type=int)
    if not year_id and current_year:
        year_id = current_year.id

    selected_year = AcademicYear.query.get(year_id) if year_id else None
    academic_years = AcademicYear.query.order_by(AcademicYear.name.desc()).all()

    # Get GUP entries for this group
    gup_entries = []
    if selected_year:
        gup_entries = GUP.query.filter_by(
            group_id=group_id,
            academic_year_id=selected_year.id
        ).order_by(GUP.week_number).all()

    return render_template('gup/group_detail.html',
                           group=group,
                           gup_entries=gup_entries,
                           activity_types=ACTIVITY_TYPES,
                           academic_years=academic_years,
                           selected_year=selected_year)


@bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create GUP for a group"""
    if request.method == 'POST':
        group_id = request.form.get('group_id', type=int)
        academic_year_id = request.form.get('academic_year_id', type=int)
        
        if not group_id or not academic_year_id:
            flash('Необходимо выбрать группу и учебный год', 'error')
            return redirect(url_for('gup.create'))
        
        # Check if GUP already exists
        existing_gup = GUP.query.filter_by(
            group_id=group_id,
            academic_year_id=academic_year_id
        ).first()
        
        if existing_gup:
            flash('ГУП для этой группы уже существует', 'warning')
            return redirect(url_for('gup.edit', group_id=group_id, year_id=academic_year_id))
        
        # Generate default GUP (52 weeks of theoretical education)
        year = AcademicYear.query.get(academic_year_id)
        start_date = year.start_date if year else date(2024, 9, 1)
        
        for week_num in range(1, 53):
            week_start = start_date + timedelta(weeks=week_num-1)
            week_end = week_start + timedelta(days=6)
            
            gup_entry = GUP(
                group_id=group_id,
                academic_year_id=academic_year_id,
                week_number=week_num,
                start_date=week_start,
                end_date=week_end,
                activity_code='',  # Default: theoretical education
                activity_name='Теоретическое обучение'
            )
            db.session.add(gup_entry)
        
        db.session.commit()
        flash('ГУП создан успешно', 'success')
        return redirect(url_for('gup.edit', group_id=group_id, year_id=academic_year_id))
    
    # GET request - show form
    groups = Group.query.order_by(Group.name).all()
    academic_years = AcademicYear.query.order_by(AcademicYear.name.desc()).all()
    
    # Pre-select from URL parameters
    selected_group_id = request.args.get('group_id', type=int)
    selected_year_id = request.args.get('year_id', type=int)
    
    return render_template('gup/create.html',
                          groups=groups,
                          academic_years=academic_years,
                          selected_group_id=selected_group_id,
                          selected_year_id=selected_year_id)


@bp.route('/edit/<int:group_id>')
def edit(group_id):
    """Edit GUP for a group"""
    group = Group.query.get_or_404(group_id)
    
    # Get academic year
    year_id = request.args.get('year_id', type=int)
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    
    if not year_id and current_year:
        year_id = current_year.id
    
    if not year_id:
        flash('Необходимо указать учебный год', 'error')
        return redirect(url_for('gup.index'))
    
    selected_year = AcademicYear.query.get(year_id)
    academic_years = AcademicYear.query.order_by(AcademicYear.name.desc()).all()
    
    # Get existing GUP entries
    gup_entries = GUP.query.filter_by(
        group_id=group_id,
        academic_year_id=year_id
    ).order_by(GUP.week_number).all()
    
    # If no GUP exists, create default one
    if not gup_entries:
        flash('ГУП не найден. Создайте новый ГУП.', 'warning')
        return redirect(url_for('gup.create'))
    
    return render_template('gup/edit.html',
                          group=group,
                          gup_entries=gup_entries,
                          activity_types=ACTIVITY_TYPES,
                          academic_years=academic_years,
                          selected_year=selected_year)


@bp.route('/update', methods=['POST'])
def update():
    """Update GUP entries via AJAX"""
    group_id = request.form.get('group_id', type=int)
    year_id = request.form.get('year_id', type=int)
    week_number = request.form.get('week_number', type=int)
    activity_code = request.form.get('activity_code', '')
    
    if not all([group_id, year_id, week_number is not None]):
        return jsonify({'success': False, 'error': 'Недостаточно данных'})
    
    # Find and update GUP entry
    gup_entry = GUP.query.filter_by(
        group_id=group_id,
        academic_year_id=year_id,
        week_number=week_number
    ).first()
    
    if not gup_entry:
        return jsonify({'success': False, 'error': 'Запись ГУП не найдена'})
    
    # Update activity
    gup_entry.activity_code = activity_code
    gup_entry.activity_name = ACTIVITY_TYPES.get(activity_code, {}).get('full_name', '')
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'activity_name': gup_entry.activity_name,
        'activity_code': activity_code
    })


@bp.route('/bulk-update', methods=['POST'])
def bulk_update():
    """Bulk update multiple weeks"""
    group_id = request.form.get('group_id', type=int)
    year_id = request.form.get('year_id', type=int)
    start_week = request.form.get('start_week', type=int)
    end_week = request.form.get('end_week', type=int)
    activity_code = request.form.get('activity_code', '')
    
    if not all([group_id, year_id, start_week, end_week]):
        return jsonify({'success': False, 'error': 'Недостаточно данных'})
    
    if start_week > end_week:
        return jsonify({'success': False, 'error': 'Начальная неделя больше конечной'})
    
    # Update range of weeks
    updated_count = 0
    for week_num in range(start_week, end_week + 1):
        gup_entry = GUP.query.filter_by(
            group_id=group_id,
            academic_year_id=year_id,
            week_number=week_num
        ).first()
        
        if gup_entry:
            gup_entry.activity_code = activity_code
            gup_entry.activity_name = ACTIVITY_TYPES.get(activity_code, {}).get('full_name', '')
            updated_count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'updated_count': updated_count,
        'message': f'Обновлено {updated_count} недель'
    })


@bp.route('/delete/<int:group_id>')
def delete(group_id):
    """Delete GUP for a group"""
    year_id = request.args.get('year_id', type=int)
    
    if not year_id:
        flash('Необходимо указать учебный год', 'error')
        return redirect(url_for('gup.index'))
    
    # Delete all GUP entries for this group and year
    deleted_count = GUP.query.filter_by(
        group_id=group_id,
        academic_year_id=year_id
    ).delete()
    
    db.session.commit()
    
    flash(f'ГУП удален ({deleted_count} записей)', 'success')
    return redirect(url_for('gup.index'))
