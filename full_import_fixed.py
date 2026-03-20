#!/usr/bin/env python
"""
Fixed import - correctly handle alternating subjects with split English
"""

import pandas as pd
import sys
import os
import json
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import (
    Group, Teacher, Workload, Schedule, Room, AcademicYear,
    GUP, WorkloadTemplate
)

app = create_app()

EXCEL_PATH = r"C:\Users\tkulz\Downloads\college_schedule_backup_20251212\Копия 1 курс Расписание 2 семестр.xlsx"
WEEK_20_MONDAY = date(2026, 1, 12)

DISCIPLINE_HOURS = {
    'Казахская литература': 72, 'Казахский литература': 72,
    'Русский язык и литература': 48, 'Английский язык': 196,
    'Всемирная история': 24, 'Всемирная История': 24,
    'Математика': 88, 'Информатика': 72, 'Физика': 64, 'Химия': 60,
    'География': 24, 'Начальная военная и технологическая подготовка': 64,
    'Физическая культура': 56, 'Глобальные компетенции': 24,
}

GROUP_COLUMNS = {
    'БНГС 1-25': (3, 4), 'ТДНГ 1-25': (5, 6), 'ЭНГМ 1-25': (7, 8),
    'ЭС 1-25': (9, 10), 'ЭС 2-25': (11, 12), 'ЭС 3-25': (13, 14),
    'ХТП 1-25': (15, 16), 'ХТП 2-25': (17, 18), 'ХТП 3-25': (19, 20),
    'АиУ 1-25': (21, 22), 'АиУ 2-25': (23, 24), 'АиУ 3-25': (25, 26),
    'АиУ 4-25': (27, 28), 'АиУ 5-25': (29, 30),
    'ПО 1-25': (31, 32), 'ПО 2-25': (33, 34),
}

DAYS = {
    'ПОНЕДЕЛЬНИК': [(5, 6), (7, 8), (9, 10), (11, 12)],
    'ВТОРНИК': [(18, 19), (20, 21), (22, 23), (24, 25)],
    'СРЕДА': [(31, 32), (33, 34), (35, 36), (37, 38)],
    'ЧЕТВЕРГ': [(44, 45), (46, 47), (48, 49), (50, 51)],
    'ПЯТНИЦА': [(57, 58), (59, 60), (61, 62), (63, 64)],
    'СУББОТА': [(70, 71), (72, 73), (74, 75), (76, 77)],
}


def clean(text):
    if pd.isna(text) or text is None:
        return ''
    return str(text).strip().replace('\n', '')


def get_week_type(week_number):
    # Четные недели = правые (Жаз), нечетные = левые (Қыс)
    return 'right' if week_number % 2 == 0 else 'left'


def is_english(subject):
    """Check if subject is English"""
    if not subject:
        return False
    return 'Английский' in subject or 'английский' in subject


def parse_cell(subject_text, teacher_text, room_text):
    """
    Parse cell with FIXED logic for alternating subjects

    Key patterns:
    1. "Английский язык/Физика" + 3 teachers = LEFT: English split, RIGHT: Physics
    2. "Информатика/Английский язык" + 3 teachers = LEFT: Informatics, RIGHT: English split
    3. "Английский язык" + 2 teachers = English split (all weeks)
    """
    subject = clean(subject_text)
    teacher = clean(teacher_text)
    room = clean(room_text)

    if not subject:
        return None

    subjects = [s.strip() for s in subject.split('/') if s.strip()]
    teachers = [t.strip() for t in teacher.split('/') if t.strip()]
    rooms = [r.strip() for r in room.split('/') if r.strip()]

    result = {
        'pattern': 'simple',
        'entries': []  # List of (subject, teacher, room, week_type, is_subgroup)
    }

    # Pattern: Starts with "/" like "/Subject" - RIGHT week only (subject in second position)
    if subject.startswith('/') and subjects:
        if len(teachers) >= 1:
            result['pattern'] = 'right_only'
            result['entries'].append((subjects[0], teachers[0], rooms[0] if rooms else None, 'right', False))
        return result

    # Pattern: Ends with "/" like "Subject/" - LEFT week only (subject in first position)
    if subject.endswith('/') and subjects:
        if len(teachers) >= 1:
            result['pattern'] = 'left_only'
            result['entries'].append((subjects[0], teachers[0], rooms[0] if rooms else None, 'left', False))
        return result

    # Pattern: 2 subjects with 3 teachers (alternating with one split)
    if len(subjects) == 2 and len(teachers) == 3:
        result['pattern'] = 'alternating_with_split'

        subj1, subj2 = subjects[0], subjects[1]
        t1, t2, t3 = teachers[0], teachers[1], teachers[2]
        r1 = rooms[0] if len(rooms) > 0 else None
        r2 = rooms[1] if len(rooms) > 1 else None
        r3 = rooms[2] if len(rooms) > 2 else None

        if is_english(subj1):
            # English is FIRST: LEFT = English split, RIGHT = second subject
            result['entries'].append((subj1, t1, r1, 'left', False))  # English main
            result['entries'].append((subj1, t2, r2, 'left', True))   # English subgroup
            result['entries'].append((subj2, t3, r3, 'right', False)) # Second subject
        else:
            # English is SECOND: LEFT = first subject, RIGHT = English split
            result['entries'].append((subj1, t1, r1, 'left', False))  # First subject
            result['entries'].append((subj2, t2, r2, 'right', False)) # English main
            result['entries'].append((subj2, t3, r3, 'right', True))  # English subgroup

        return result

    # Pattern: 2 different subjects with 2 teachers (alternating)
    if len(subjects) == 2 and len(teachers) >= 2 and subjects[0] != subjects[1]:
        result['pattern'] = 'alternating'
        result['entries'].append((subjects[0], teachers[0], rooms[0] if rooms else None, 'left', False))
        result['entries'].append((subjects[1], teachers[1], rooms[1] if len(rooms) > 1 else None, 'right', False))
        return result

    # Pattern: Single subject with 2 teachers (split English)
    if len(subjects) == 1 and len(teachers) == 2 and is_english(subjects[0]):
        result['pattern'] = 'split_english'
        result['entries'].append((subjects[0], teachers[0], rooms[0] if rooms else None, 'all', False))
        result['entries'].append((subjects[0], teachers[1], rooms[1] if len(rooms) > 1 else None, 'all', True))
        return result

    # Pattern: Same subject twice with 2 teachers (split)
    if len(subjects) == 2 and subjects[0] == subjects[1] and len(teachers) == 2:
        result['pattern'] = 'split_english'
        result['entries'].append((subjects[0], teachers[0], rooms[0] if rooms else None, 'all', False))
        result['entries'].append((subjects[0], teachers[1], rooms[1] if len(rooms) > 1 else None, 'all', True))
        return result

    # Simple pattern
    if subjects and teachers:
        result['entries'].append((subjects[0], teachers[0], rooms[0] if rooms else None, 'all', False))

    return result


def get_or_create_group(name, academic_year_id):
    group = Group.query.filter_by(name=name).first()
    if not group:
        base_name = name.rstrip('б')
        parent = Group.query.filter_by(name=base_name).first()
        if parent:
            group = Group(name=name, enrollment_year=parent.enrollment_year,
                         specialty_id=parent.specialty_id, shift=parent.shift,
                         subgroup_of_id=parent.id)
        else:
            group = Group(name=name, enrollment_year=2025, shift=1)
        db.session.add(group)
        db.session.flush()
        print(f"  Created group: {name}")
    return group


def get_or_create_teacher(name):
    if not name or name.strip() == '':
        return None

    # Normalize "Вакант" variations
    clean_name = name.strip().rstrip('.')
    if clean_name.lower() in ['вакант', 'вакант.']:
        clean_name = 'Вакант'

    teacher = Teacher.query.filter(Teacher.full_name.ilike(f'%{clean_name}%')).first()
    if not teacher:
        teacher = Teacher(full_name=clean_name)
        db.session.add(teacher)
        db.session.flush()
    return teacher


def get_or_create_room(number):
    if not number or str(number).strip() in ['', 'nan']:
        return None
    room = Room.query.filter_by(number=str(number).strip()).first()
    if not room:
        room = Room(number=str(number).strip())
        db.session.add(room)
        db.session.flush()
    return room


def get_or_create_workload(teacher, group, discipline, academic_year, hours=None):
    if not teacher or not group or not discipline:
        return None
    workload = Workload.query.filter_by(
        teacher_id=teacher.id, group_id=group.id,
        discipline=discipline, academic_year_id=academic_year.id
    ).first()
    if not workload:
        total_hours = hours or DISCIPLINE_HOURS.get(discipline, 72)
        workload = Workload(
            teacher_id=teacher.id, group_id=group.id,
            discipline=discipline, academic_year_id=academic_year.id,
            semester=2, total_hours=total_hours,
            hours_per_week=max(2, total_hours // 22 * 2), lesson_type='theory'
        )
        db.session.add(workload)
        db.session.flush()
    return workload


def create_template(workload, week_type, academic_year):
    if not workload:
        return None
    gup_weeks = GUP.query.filter_by(
        group_id=workload.group_id, academic_year_id=academic_year.id
    ).filter(GUP.week_number >= 20).order_by(GUP.week_number).all()

    if not gup_weeks:
        return None

    target_weeks = []
    for gup in gup_weeks:
        if not gup.needs_schedule:
            continue
        gup_week_type = get_week_type(gup.week_number)
        if week_type == 'all' or week_type == gup_week_type:
            target_weeks.append(gup)

    if not target_weeks:
        return None

    total_pairs = workload.total_hours // 2
    pairs_per_week = max(1, total_pairs // len(target_weeks))
    extra = total_pairs % len(target_weeks)

    weeks_data = []
    for i, gup in enumerate(target_weeks):
        pairs = pairs_per_week + (1 if i < extra else 0)
        if pairs <= 0:
            continue
        prefs = {}
        assigned = 0
        for day in range(5):
            if assigned >= pairs:
                break
            prefs[str(day)] = {}
            today = min(2, pairs - assigned)
            for p in range(1, today + 1):
                prefs[str(day)][str(p)] = 'selected'
                assigned += 1
        weeks_data.append({'week': gup.week_number, 'preferences': prefs})

    name = f"{workload.discipline} - {workload.group.name}"
    if week_type == 'left':
        name += " (Левые)"
    elif week_type == 'right':
        name += " (Правые)"

    existing = WorkloadTemplate.query.filter_by(
        workload_id=workload.id, group_id=workload.group_id, semester=2
    ).first()

    if existing:
        existing.name = name
        existing.distribution_json = json.dumps(weeks_data)
        return existing

    template = WorkloadTemplate(
        name=name, workload_id=workload.id, group_id=workload.group_id,
        academic_year_id=academic_year.id, semester=2, total_hours=workload.total_hours,
        distribution_json=json.dumps(weeks_data), created_by='import'
    )
    db.session.add(template)
    return template


def full_import():
    with app.app_context():
        print("=" * 80)
        print("FIXED IMPORT - CORRECT ALTERNATING PATTERN")
        print("=" * 80)

        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not academic_year:
            academic_year = AcademicYear.query.first()

        df = pd.read_excel(EXCEL_PATH, sheet_name=0, header=None)
        print(f"Excel shape: {df.shape}")

        # Delete existing data
        print("\nDeleting existing data...")
        first_course = Group.query.filter(Group.enrollment_year == 2025).all()
        group_ids = [g.id for g in first_course]
        if group_ids:
            WorkloadTemplate.query.filter(WorkloadTemplate.group_id.in_(group_ids)).delete(synchronize_session='fetch')
            workload_ids = [w.id for w in Workload.query.filter(Workload.group_id.in_(group_ids)).all()]
            if workload_ids:
                Schedule.query.filter(Schedule.workload_id.in_(workload_ids)).delete(synchronize_session='fetch')
            Workload.query.filter(Workload.group_id.in_(group_ids)).delete(synchronize_session='fetch')
        db.session.commit()

        created_workloads = {}
        templates_created = 0

        for group_name, (subj_col, room_col) in GROUP_COLUMNS.items():
            print(f"\n--- {group_name} ---")
            group = Group.query.filter_by(name=group_name).first()
            if not group:
                continue

            for day_name, pairs in DAYS.items():
                day_idx = list(DAYS.keys()).index(day_name)
                for pair_idx, (subj_row, teacher_row) in enumerate(pairs, 1):
                    subject_text = df.iloc[subj_row, subj_col]
                    teacher_text = df.iloc[teacher_row, subj_col]
                    room_text = df.iloc[teacher_row, room_col]

                    parsed = parse_cell(subject_text, teacher_text, room_text)
                    if not parsed or not parsed['entries']:
                        continue

                    for subj, teacher_name, room_num, week_type, is_subgroup in parsed['entries']:
                        if not subj or not teacher_name:
                            continue

                        target_group_name = group_name + 'б' if is_subgroup else group_name
                        target_group = get_or_create_group(target_group_name, academic_year.id)
                        teacher = get_or_create_teacher(teacher_name)

                        if not teacher:
                            continue

                        key = (target_group_name, subj, teacher_name, week_type)
                        if key not in created_workloads:
                            workload = get_or_create_workload(teacher, target_group, subj, academic_year)
                            if workload:
                                created_workloads[key] = workload
                                template = create_template(workload, week_type, academic_year)
                                if template:
                                    templates_created += 1
                                    print(f"  + {subj} | {target_group_name} | {teacher_name} | {week_type}")

        db.session.commit()

        print("\n" + "=" * 80)
        print(f"Created workloads: {len(created_workloads)}")
        print(f"Created templates: {templates_created}")

        # Verify Аяпбергенова
        print("\n--- Verification: Аяпбергенова ---")
        teacher = Teacher.query.filter(Teacher.full_name.like('%Аяпбергенова%')).first()
        if teacher:
            workloads = Workload.query.filter_by(teacher_id=teacher.id).all()
            for w in workloads:
                print(f"  {w.discipline} | {w.group.name}")


if __name__ == "__main__":
    full_import()
