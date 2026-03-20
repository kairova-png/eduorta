import json
import os
from datetime import datetime, timedelta
from app import db
from app.models import AcademicYear, Department, Specialty, Group, Teacher, Room, GUP


def import_college_from_file(data):
    """Import college data from parsed JSON dict"""
    # Import departments
    dept_map = {}
    for dept_data in data.get('departments', []):
        dept = Department.query.filter_by(name_ru=dept_data['name_ru']).first()
        if not dept:
            dept = Department(
                name_ru=dept_data['name_ru'],
                name_kz=dept_data.get('name_kz')
            )
            db.session.add(dept)
            db.session.flush()
        dept_map[dept_data['name_ru']] = dept.id

    # Import specialties
    spec_map = {}
    for spec_data in data.get('specialties', []):
        spec = Specialty.query.filter_by(code=spec_data['code']).first()
        if not spec:
            dept_id = dept_map.get(spec_data.get('department'))
            spec = Specialty(
                code=spec_data['code'],
                name_ru=spec_data['name_ru'],
                name_kz=spec_data.get('name_kz'),
                department_id=dept_id
            )
            db.session.add(spec)
            db.session.flush()
        spec_map[spec_data['code']] = spec.id

    # Import groups
    for group_data in data.get('groups', []):
        group = Group.query.filter_by(name=group_data['name']).first()
        if not group:
            spec_id = spec_map.get(group_data.get('specialty_code'))
            group = Group(
                name=group_data['name'],
                specialty_id=spec_id,
                group_number=group_data.get('group_number'),
                enrollment_year=group_data.get('enrollment_year')
            )
            db.session.add(group)

    # Import teachers
    for teacher_data in data.get('teachers', []):
        teacher = Teacher.query.filter_by(full_name=teacher_data['full_name']).first()
        if not teacher:
            teacher = Teacher(full_name=teacher_data['full_name'])
            db.session.add(teacher)

    # Import rooms
    for room_data in data.get('rooms', []):
        room = Room.query.filter_by(number=room_data['number']).first()
        if not room:
            room = Room(
                number=room_data['number'],
                room_type=room_data.get('type', 'учебная')
            )
            db.session.add(room)

    db.session.commit()

    return {
        'departments': len(data.get('departments', [])),
        'specialties': len(data.get('specialties', [])),
        'groups': len(data.get('groups', [])),
        'teachers': len(data.get('teachers', [])),
        'rooms': len(data.get('rooms', []))
    }


def import_gup_from_file(data, academic_year_id=None):
    """Import GUP from parsed JSON dict"""
    # Create academic year if not exists
    if not academic_year_id:
        year_name = data.get('academic_year', '2025-2026')
        start_str = data.get('academic_year_start', '2025-09-01')
        end_str = data.get('academic_year_end', '2026-08-31')

        year = AcademicYear.query.filter_by(name=year_name).first()
        if not year:
            year = AcademicYear(
                name=year_name,
                start_date=datetime.strptime(start_str, '%Y-%m-%d').date(),
                end_date=datetime.strptime(end_str, '%Y-%m-%d').date(),
                is_current=True
            )
            db.session.add(year)
            db.session.flush()
        academic_year_id = year.id

    # Get all groups from DB
    db_groups = {g.name: g.id for g in Group.query.all()}

    # Get weeks info
    weeks_info = data.get('weeks', {})

    imported_count = 0

    # Process each group's schedule
    for group_data in data.get('groups', []):
        group_name = group_data.get('group_name')
        group_id = db_groups.get(group_name)

        if not group_id:
            continue

        schedule = group_data.get('schedule', {})

        for week_num_str, week_activity in schedule.items():
            week_num = int(week_num_str)

            # Get week dates from weeks_info
            week_info = weeks_info.get(week_num_str, {})
            start_date = None
            end_date = None

            if week_info.get('start_date'):
                start_date = datetime.strptime(week_info['start_date'], '%Y-%m-%d').date()
            if week_info.get('end_date'):
                end_date = datetime.strptime(week_info['end_date'], '%Y-%m-%d').date()

            # Check if GUP entry already exists
            existing = GUP.query.filter_by(
                group_id=group_id,
                academic_year_id=academic_year_id,
                week_number=week_num
            ).first()

            if not existing:
                activity_code = week_activity.get('code_ru') or ""
                activity_name = week_activity.get('activity_ru') or get_activity_name(activity_code)

                gup = GUP(
                    group_id=group_id,
                    academic_year_id=academic_year_id,
                    week_number=week_num,
                    start_date=start_date,
                    end_date=end_date,
                    activity_code=activity_code,
                    activity_name=activity_name
                )
                db.session.add(gup)
                imported_count += 1

    db.session.commit()
    return imported_count


def import_college_data(data_dir):
    """Import college data from JSON file"""
    filepath = os.path.join(data_dir, 'college_data.json')

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Import departments
    dept_map = {}
    for dept_data in data.get('departments', []):
        dept = Department.query.filter_by(name_ru=dept_data['name_ru']).first()
        if not dept:
            dept = Department(
                name_ru=dept_data['name_ru'],
                name_kz=dept_data.get('name_kz')
            )
            db.session.add(dept)
            db.session.flush()
        dept_map[dept_data['name_ru']] = dept.id

    # Import specialties
    spec_map = {}
    for spec_data in data.get('specialties', []):
        spec = Specialty.query.filter_by(code=spec_data['code']).first()
        if not spec:
            dept_id = dept_map.get(spec_data.get('department'))
            spec = Specialty(
                code=spec_data['code'],
                name_ru=spec_data['name_ru'],
                name_kz=spec_data.get('name_kz'),
                department_id=dept_id
            )
            db.session.add(spec)
            db.session.flush()
        spec_map[spec_data['code']] = spec.id

    # Import groups
    for group_data in data.get('groups', []):
        group = Group.query.filter_by(name=group_data['name']).first()
        if not group:
            spec_id = spec_map.get(group_data.get('specialty_code'))
            group = Group(
                name=group_data['name'],
                specialty_id=spec_id,
                group_number=group_data.get('group_number'),
                enrollment_year=group_data.get('enrollment_year')
            )
            db.session.add(group)

    # Import teachers
    for teacher_data in data.get('teachers', []):
        teacher = Teacher.query.filter_by(full_name=teacher_data['full_name']).first()
        if not teacher:
            teacher = Teacher(full_name=teacher_data['full_name'])
            db.session.add(teacher)

    # Import rooms
    for room_data in data.get('rooms', []):
        room = Room.query.filter_by(number=room_data['number']).first()
        if not room:
            room = Room(
                number=room_data['number'],
                room_type=room_data.get('type', 'учебная')
            )
            db.session.add(room)

    db.session.commit()

    return {
        'departments': len(data.get('departments', [])),
        'specialties': len(data.get('specialties', [])),
        'groups': len(data.get('groups', [])),
        'teachers': len(data.get('teachers', [])),
        'rooms': len(data.get('rooms', []))
    }


def import_gup(data_dir, academic_year_id=None):
    """Import GUP (academic calendar) from JSON file"""
    filepath = os.path.join(data_dir, 'gup_2025_2026.json')

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Create academic year if not exists
    if not academic_year_id:
        year_name = data.get('academic_year', '2025-2026')
        start_str = data.get('academic_year_start', '2025-09-01')
        end_str = data.get('academic_year_end', '2026-08-31')

        year = AcademicYear.query.filter_by(name=year_name).first()
        if not year:
            year = AcademicYear(
                name=year_name,
                start_date=datetime.strptime(start_str, '%Y-%m-%d').date(),
                end_date=datetime.strptime(end_str, '%Y-%m-%d').date(),
                is_current=True
            )
            db.session.add(year)
            db.session.flush()
        academic_year_id = year.id

    # Get all groups from DB
    db_groups = {g.name: g.id for g in Group.query.all()}

    # Get weeks info
    weeks_info = data.get('weeks', {})

    imported_count = 0

    # Process each group's schedule
    for group_data in data.get('groups', []):
        group_name = group_data.get('group_name')
        group_id = db_groups.get(group_name)

        if not group_id:
            continue

        schedule = group_data.get('schedule', {})

        for week_num_str, week_activity in schedule.items():
            week_num = int(week_num_str)

            # Get week dates from weeks_info
            week_info = weeks_info.get(week_num_str, {})
            start_date = None
            end_date = None

            if week_info.get('start_date'):
                start_date = datetime.strptime(week_info['start_date'], '%Y-%m-%d').date()
            if week_info.get('end_date'):
                end_date = datetime.strptime(week_info['end_date'], '%Y-%m-%d').date()

            # Check if GUP entry already exists
            existing = GUP.query.filter_by(
                group_id=group_id,
                academic_year_id=academic_year_id,
                week_number=week_num
            ).first()

            if not existing:
                activity_code = week_activity.get('code_ru') or ""
                activity_name = week_activity.get('activity_ru') or get_activity_name(activity_code)

                gup = GUP(
                    group_id=group_id,
                    academic_year_id=academic_year_id,
                    week_number=week_num,
                    start_date=start_date,
                    end_date=end_date,
                    activity_code=activity_code,
                    activity_name=activity_name
                )
                db.session.add(gup)
                imported_count += 1

    db.session.commit()
    return imported_count


def get_activity_name(code):
    """Get activity name by code"""
    names = {
        '': 'Теоретическое обучение',
        'К': 'Каникулы',
        '::': 'Промежуточная аттестация',
        'П': 'Производственная практика',
        'КП': 'Производственная практика',
        'УП': 'Учебная практика',
        'ОТ': 'Учебная практика',
        'ӨО': 'Производственное обучение',
        'ВС': 'Ознакомительная практика',
        'ТТ': 'Ознакомительная практика',
        'ПС': 'Полевые сборы',
        'ДЖ': 'Полевые сборы',
        'И': 'Итоговая аттестация',
        'ҚА': 'Итоговая аттестация',
        '*': 'Праздничные дни'
    }
    return names.get(code, 'Теоретическое обучение')
