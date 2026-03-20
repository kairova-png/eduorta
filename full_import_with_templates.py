#!/usr/bin/env python
"""
Full import from Excel with:
1. Split groups for English (group + group-б)
2. Alternating weeks pattern (left/right)
3. Auto-create workload templates
"""

import pandas as pd
import sys
import os
import re
import json
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import (
    Group, Teacher, Workload, Schedule, Room, AcademicYear,
    GUP, WorkloadTemplate, Specialty
)

app = create_app()

# Excel file path
EXCEL_PATH = r"C:\Users\tkulz\Downloads\college_schedule_backup_20251212\Копия 1 курс Расписание 2 семестр.xlsx"

# Week 20 starts on Monday 2026-01-12
WEEK_20_MONDAY = date(2026, 1, 12)

# Hours per discipline
DISCIPLINE_HOURS = {
    'Казахская литература': 72,
    'Казахский литература': 72,
    'Русский язык и литература': 48,
    'Английский язык': 196,
    'Всемирная история': 24,
    'Всемирная История': 24,
    'Математика': 88,
    'Информатика': 72,
    'Физика': 64,
    'Химия': 60,
    'География': 24,
    'Начальная военная и технологическая подготовка': 64,
    'Физическая культура': 56,
    'Глобальные компетенции': 24,
}

# Group columns mapping
GROUP_COLUMNS = {
    'БНГС 1-25': (3, 4),
    'ТДНГ 1-25': (5, 6),
    'ЭНГМ 1-25': (7, 8),
    'ЭС 1-25': (9, 10),
    'ЭС 2-25': (11, 12),
    'ЭС 3-25': (13, 14),
    'ХТП 1-25': (15, 16),
    'ХТП 2-25': (17, 18),
    'ХТП 3-25': (19, 20),
    'АиУ 1-25': (21, 22),
    'АиУ 2-25': (23, 24),
    'АиУ 3-25': (25, 26),
    'АиУ 4-25': (27, 28),
    'АиУ 5-25': (29, 30),
    'ПО 1-25': (31, 32),
    'ПО 2-25': (33, 34),
}

# Days and their row ranges (subject_row, teacher_row)
DAYS = {
    'ПОНЕДЕЛЬНИК': [(5, 6), (7, 8), (9, 10), (11, 12)],
    'ВТОРНИК': [(18, 19), (20, 21), (22, 23), (24, 25)],
    'СРЕДА': [(31, 32), (33, 34), (35, 36), (37, 38)],
    'ЧЕТВЕРГ': [(44, 45), (46, 47), (48, 49), (50, 51)],
    'ПЯТНИЦА': [(57, 58), (59, 60), (61, 62), (63, 64)],
    'СУББОТА': [(70, 71), (72, 73), (74, 75), (76, 77)],
}


def clean(text):
    """Clean text value"""
    if pd.isna(text) or text is None:
        return ''
    return str(text).strip().replace('\n', '')


def get_week_type(week_number):
    """Get week type: left (even) or right (odd)"""
    return 'left' if week_number % 2 == 0 else 'right'


def parse_cell(subject_text, teacher_text, room_text):
    """
    Parse Excel cell and return structured data about the schedule entry.

    Returns dict with:
    - pattern: 'simple', 'split_english', 'alternating', 'alternating_with_split', 'left_only', 'right_only'
    - subjects: list of subjects
    - teachers: list of teachers
    - rooms: list of rooms
    - left_week_data: data for left weeks (if alternating)
    - right_week_data: data for right weeks (if alternating)
    """
    subject = clean(subject_text)
    teacher = clean(teacher_text)
    room = clean(room_text)

    if not subject:
        return None

    result = {
        'raw_subject': subject,
        'raw_teacher': teacher,
        'raw_room': room,
        'pattern': 'simple',
        'subjects': [],
        'teachers': [],
        'rooms': [],
        'left_week_data': None,
        'right_week_data': None,
    }

    # Parse subjects (split by /)
    subjects = [s.strip() for s in subject.split('/') if s.strip()]

    # Parse teachers (split by /)
    teachers = [t.strip() for t in teacher.split('/') if t.strip()]

    # Parse rooms (split by /)
    rooms = [r.strip() for r in room.split('/') if r.strip()]

    result['subjects'] = subjects
    result['teachers'] = teachers
    result['rooms'] = rooms

    # Detect patterns

    # Pattern 1: Starts with "/" - left week only
    if subject.startswith('/'):
        result['pattern'] = 'left_only'
        result['left_week_data'] = {
            'subject': subjects[0] if subjects else None,
            'teachers': teachers,
            'rooms': rooms
        }
        return result

    # Pattern 2: Ends with "/" - right week only
    if subject.endswith('/'):
        result['pattern'] = 'right_only'
        result['right_week_data'] = {
            'subject': subjects[0] if subjects else None,
            'teachers': teachers,
            'rooms': rooms
        }
        return result

    # Pattern 3: Two subjects with 3 teachers (alternating with split)
    if len(subjects) == 2 and len(teachers) == 3:
        result['pattern'] = 'alternating_with_split'
        # Left weeks: first subject split between first 2 teachers
        # Right weeks: second subject with 3rd teacher
        result['left_week_data'] = {
            'subject': subjects[0],
            'teachers': teachers[:2],  # First 2 teachers (split)
            'rooms': rooms[:2] if len(rooms) >= 2 else rooms
        }
        result['right_week_data'] = {
            'subject': subjects[1],
            'teachers': [teachers[2]],  # 3rd teacher
            'rooms': [rooms[2]] if len(rooms) >= 3 else rooms[-1:] if rooms else []
        }
        return result

    # Pattern 4: Two different subjects (alternating)
    if len(subjects) == 2 and subjects[0] != subjects[1]:
        result['pattern'] = 'alternating'
        # Distribute teachers between subjects
        if len(teachers) >= 2:
            result['left_week_data'] = {
                'subject': subjects[0],
                'teachers': [teachers[0]],
                'rooms': [rooms[0]] if rooms else []
            }
            result['right_week_data'] = {
                'subject': subjects[1],
                'teachers': [teachers[1]],
                'rooms': [rooms[1]] if len(rooms) >= 2 else rooms
            }
        else:
            result['left_week_data'] = {
                'subject': subjects[0],
                'teachers': teachers,
                'rooms': rooms
            }
            result['right_week_data'] = {
                'subject': subjects[1],
                'teachers': teachers,
                'rooms': rooms
            }
        return result

    # Pattern 5: Single subject with 2 teachers (split English)
    if len(subjects) == 1 and len(teachers) == 2:
        if 'Английский' in subjects[0] or 'язык' in subjects[0].lower():
            result['pattern'] = 'split_english'
            result['left_week_data'] = {
                'subject': subjects[0],
                'teachers': teachers,
                'rooms': rooms
            }
        return result

    # Pattern 6: Same subject listed twice with 2 teachers (split)
    if len(subjects) == 2 and subjects[0] == subjects[1] and len(teachers) == 2:
        result['pattern'] = 'split_english'
        result['left_week_data'] = {
            'subject': subjects[0],
            'teachers': teachers,
            'rooms': rooms
        }
        return result

    # Simple pattern - single subject, single teacher
    return result


def get_or_create_group(name, academic_year_id):
    """Get or create a group (including subgroups like АиУ 1-25б)"""
    group = Group.query.filter_by(name=name).first()

    if not group:
        # Find parent group for subgroups
        base_name = name.rstrip('б')
        parent = Group.query.filter_by(name=base_name).first()

        if parent:
            # Create subgroup based on parent
            group = Group(
                name=name,
                enrollment_year=parent.enrollment_year,
                specialty_id=parent.specialty_id,
                shift=parent.shift,
                subgroup_of_id=parent.id
            )
        else:
            # Create new group
            group = Group(
                name=name,
                enrollment_year=2025,
                shift=1
            )

        db.session.add(group)
        db.session.flush()
        print(f"  Created group: {name}")

    return group


def get_or_create_teacher(name):
    """Get or create teacher"""
    if not name or name in ['Вакант', 'Вакант.', '']:
        return None

    name = name.strip()
    teacher = Teacher.query.filter(Teacher.full_name.ilike(f'%{name}%')).first()

    if not teacher:
        teacher = Teacher(full_name=name)
        db.session.add(teacher)
        db.session.flush()
        print(f"  Created teacher: {name}")

    return teacher


def get_or_create_room(number):
    """Get or create room"""
    if not number:
        return None

    number = str(number).strip()
    if not number or number in ['', 'nan']:
        return None

    room = Room.query.filter_by(number=number).first()
    if not room:
        room = Room(number=number)
        db.session.add(room)
        db.session.flush()

    return room


def get_or_create_workload(teacher, group, discipline, academic_year, hours=None):
    """Get or create workload"""
    if not teacher or not group or not discipline:
        return None

    workload = Workload.query.filter_by(
        teacher_id=teacher.id,
        group_id=group.id,
        discipline=discipline,
        academic_year_id=academic_year.id
    ).first()

    if not workload:
        # Get hours for discipline
        total_hours = hours or DISCIPLINE_HOURS.get(discipline, 72)

        workload = Workload(
            teacher_id=teacher.id,
            group_id=group.id,
            discipline=discipline,
            academic_year_id=academic_year.id,
            semester=2,
            total_hours=total_hours,
            hours_per_week=max(2, total_hours // 22 * 2),
            lesson_type='theory'
        )
        db.session.add(workload)
        db.session.flush()
        print(f"  Created workload: {discipline} - {group.name} - {teacher.full_name}")

    return workload


def create_template_for_workload(workload, week_type, academic_year):
    """
    Create workload template based on week type.

    week_type: 'all', 'left', 'right'
    """
    if not workload:
        return None

    # Get GUP weeks for this group
    gup_weeks = GUP.query.filter_by(
        group_id=workload.group_id,
        academic_year_id=academic_year.id
    ).filter(GUP.week_number >= 20).order_by(GUP.week_number).all()

    if not gup_weeks:
        print(f"    No GUP data for template")
        return None

    # Filter weeks based on type
    target_weeks = []
    for gup in gup_weeks:
        if not gup.needs_schedule:
            continue

        gup_week_type = get_week_type(gup.week_number)

        if week_type == 'all':
            target_weeks.append(gup)
        elif week_type == 'left' and gup_week_type == 'left':
            target_weeks.append(gup)
        elif week_type == 'right' and gup_week_type == 'right':
            target_weeks.append(gup)

    if not target_weeks:
        return None

    # Calculate pairs per week based on total hours
    total_hours = workload.total_hours
    total_pairs = total_hours // 2
    pairs_per_week = max(1, total_pairs // len(target_weeks))
    extra_pairs = total_pairs % len(target_weeks)

    # Build weeks data for template
    weeks_data = []
    for i, gup in enumerate(target_weeks):
        pairs_this_week = pairs_per_week + (1 if i < extra_pairs else 0)

        if pairs_this_week <= 0:
            continue

        # Distribute pairs across weekdays (Mon-Fri = days 0-4)
        preferences = {}
        pairs_assigned = 0

        for day in range(5):  # Mon-Fri
            if pairs_assigned >= pairs_this_week:
                break

            preferences[str(day)] = {}
            pairs_today = min(2, pairs_this_week - pairs_assigned)  # Max 2 pairs per day

            for pair in range(1, pairs_today + 1):
                preferences[str(day)][str(pair)] = 'selected'
                pairs_assigned += 1

        weeks_data.append({
            'week': gup.week_number,
            'preferences': preferences
        })

    # Check if template already exists
    existing = WorkloadTemplate.query.filter_by(
        workload_id=workload.id,
        group_id=workload.group_id,
        semester=2
    ).first()

    template_name = f"{workload.discipline} - {workload.group.name}"
    if week_type == 'left':
        template_name += " (Левые недели)"
    elif week_type == 'right':
        template_name += " (Правые недели)"

    if existing:
        existing.name = template_name
        existing.distribution_json = json.dumps(weeks_data)
        existing.updated_at = datetime.utcnow()
        print(f"    Updated template: {template_name}")
        return existing
    else:
        template = WorkloadTemplate(
            name=template_name,
            workload_id=workload.id,
            group_id=workload.group_id,
            academic_year_id=academic_year.id,
            semester=2,
            total_hours=workload.total_hours,
            distribution_json=json.dumps(weeks_data),
            created_by='import_script'
        )
        db.session.add(template)
        db.session.flush()
        print(f"    Created template: {template_name}")
        return template


def full_import():
    """Main import function"""
    with app.app_context():
        print("=" * 100)
        print("FULL IMPORT WITH PATTERNS AND TEMPLATES")
        print("=" * 100)

        # Get academic year
        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not academic_year:
            academic_year = AcademicYear.query.first()
        print(f"\nAcademic year: {academic_year.name}")

        # Read Excel
        print(f"\nReading Excel: {EXCEL_PATH}")
        df = pd.read_excel(EXCEL_PATH, sheet_name=0, header=None)
        print(f"Shape: {df.shape}")

        # Delete existing data for 1st course
        print("\n" + "=" * 100)
        print("DELETING EXISTING DATA")
        print("=" * 100)

        first_course_groups = Group.query.filter(Group.enrollment_year == 2025).all()
        group_ids = [g.id for g in first_course_groups]

        # Delete templates
        if group_ids:
            WorkloadTemplate.query.filter(WorkloadTemplate.group_id.in_(group_ids)).delete(synchronize_session='fetch')

            # Delete schedules
            workload_ids = [w.id for w in Workload.query.filter(Workload.group_id.in_(group_ids)).all()]
            if workload_ids:
                Schedule.query.filter(Schedule.workload_id.in_(workload_ids)).delete(synchronize_session='fetch')

            # Delete workloads
            Workload.query.filter(Workload.group_id.in_(group_ids)).delete(synchronize_session='fetch')

        db.session.commit()
        print("Deleted existing data")

        # Process Excel data
        print("\n" + "=" * 100)
        print("ANALYZING AND IMPORTING DATA")
        print("=" * 100)

        # Track created items
        created_workloads = {}
        schedule_entries = []
        templates_created = 0

        # Process each group and each day/pair
        for group_name, (subj_col, room_col) in GROUP_COLUMNS.items():
            print(f"\n--- Processing {group_name} ---")

            group = Group.query.filter_by(name=group_name).first()
            if not group:
                print(f"  Group not found: {group_name}")
                continue

            # Track unique entries for this group
            group_entries = []

            for day_name, pairs in DAYS.items():
                day_index = list(DAYS.keys()).index(day_name)

                for pair_idx, (subj_row, teacher_row) in enumerate(pairs, 1):
                    subject_text = df.iloc[subj_row, subj_col]
                    teacher_text = df.iloc[teacher_row, subj_col]
                    room_text = df.iloc[teacher_row, room_col]

                    parsed = parse_cell(subject_text, teacher_text, room_text)
                    if not parsed:
                        continue

                    pattern = parsed['pattern']

                    if pattern == 'simple':
                        # Simple - one subject, one teacher, all weeks
                        subject = parsed['subjects'][0] if parsed['subjects'] else None
                        teacher_name = parsed['teachers'][0] if parsed['teachers'] else None
                        room_num = parsed['rooms'][0] if parsed['rooms'] else None

                        if subject and teacher_name:
                            group_entries.append({
                                'subject': subject,
                                'teacher': teacher_name,
                                'room': room_num,
                                'week_type': 'all',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name,
                                'is_subgroup': False
                            })

                    elif pattern == 'split_english':
                        # Split English - create 2 workloads (group + group-б)
                        data = parsed['left_week_data']
                        subject = data['subject']
                        teachers = data['teachers']
                        rooms = data['rooms']

                        if len(teachers) >= 2:
                            # Main group - first teacher
                            group_entries.append({
                                'subject': subject,
                                'teacher': teachers[0],
                                'room': rooms[0] if rooms else None,
                                'week_type': 'all',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name,
                                'is_subgroup': False
                            })

                            # Subgroup (б) - second teacher
                            group_entries.append({
                                'subject': subject,
                                'teacher': teachers[1],
                                'room': rooms[1] if len(rooms) >= 2 else None,
                                'week_type': 'all',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name + 'б',
                                'is_subgroup': True
                            })

                    elif pattern == 'alternating':
                        # Alternating - left weeks one subject, right weeks another
                        left_data = parsed['left_week_data']
                        right_data = parsed['right_week_data']

                        if left_data and left_data['subject'] and left_data['teachers']:
                            group_entries.append({
                                'subject': left_data['subject'],
                                'teacher': left_data['teachers'][0],
                                'room': left_data['rooms'][0] if left_data['rooms'] else None,
                                'week_type': 'left',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name,
                                'is_subgroup': False
                            })

                        if right_data and right_data['subject'] and right_data['teachers']:
                            group_entries.append({
                                'subject': right_data['subject'],
                                'teacher': right_data['teachers'][0],
                                'room': right_data['rooms'][0] if right_data['rooms'] else None,
                                'week_type': 'right',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name,
                                'is_subgroup': False
                            })

                    elif pattern == 'alternating_with_split':
                        # Alternating with split English
                        left_data = parsed['left_week_data']
                        right_data = parsed['right_week_data']

                        # Left weeks - split English
                        if left_data and left_data['subject'] and len(left_data['teachers']) >= 2:
                            # Main group
                            group_entries.append({
                                'subject': left_data['subject'],
                                'teacher': left_data['teachers'][0],
                                'room': left_data['rooms'][0] if left_data['rooms'] else None,
                                'week_type': 'left',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name,
                                'is_subgroup': False
                            })

                            # Subgroup
                            group_entries.append({
                                'subject': left_data['subject'],
                                'teacher': left_data['teachers'][1],
                                'room': left_data['rooms'][1] if len(left_data['rooms']) >= 2 else None,
                                'week_type': 'left',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name + 'б',
                                'is_subgroup': True
                            })

                        # Right weeks - single subject/teacher
                        if right_data and right_data['subject'] and right_data['teachers']:
                            group_entries.append({
                                'subject': right_data['subject'],
                                'teacher': right_data['teachers'][0],
                                'room': right_data['rooms'][0] if right_data['rooms'] else None,
                                'week_type': 'right',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name,
                                'is_subgroup': False
                            })

                    elif pattern == 'left_only':
                        data = parsed['left_week_data']
                        if data and data['subject'] and data['teachers']:
                            group_entries.append({
                                'subject': data['subject'],
                                'teacher': data['teachers'][0],
                                'room': data['rooms'][0] if data['rooms'] else None,
                                'week_type': 'left',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name,
                                'is_subgroup': False
                            })

                    elif pattern == 'right_only':
                        data = parsed['right_week_data']
                        if data and data['subject'] and data['teachers']:
                            group_entries.append({
                                'subject': data['subject'],
                                'teacher': data['teachers'][0],
                                'room': data['rooms'][0] if data['rooms'] else None,
                                'week_type': 'right',
                                'day': day_index,
                                'pair': pair_idx,
                                'group': group_name,
                                'is_subgroup': False
                            })

            # Create workloads for this group
            print(f"  Found {len(group_entries)} schedule entries")

            # Deduplicate and create workloads
            workload_keys = set()
            for entry in group_entries:
                key = (entry['group'], entry['subject'], entry['teacher'], entry['week_type'])
                if key not in workload_keys:
                    workload_keys.add(key)

                    # Get or create group (including subgroups)
                    entry_group = get_or_create_group(entry['group'], academic_year.id)

                    # Get or create teacher
                    teacher = get_or_create_teacher(entry['teacher'])
                    if not teacher:
                        continue

                    # Get hours (for split English, divide by 2 if subgroup)
                    hours = DISCIPLINE_HOURS.get(entry['subject'], 72)

                    # Create workload
                    workload = get_or_create_workload(
                        teacher, entry_group, entry['subject'], academic_year, hours
                    )

                    if workload:
                        created_workloads[(entry['group'], entry['subject'], entry['teacher'])] = workload

                        # Create template
                        template = create_template_for_workload(
                            workload, entry['week_type'], academic_year
                        )
                        if template:
                            templates_created += 1

            # Store schedule entries
            schedule_entries.extend(group_entries)

        db.session.commit()

        # Create schedule entries for week 20
        print("\n" + "=" * 100)
        print("CREATING SCHEDULE FOR WEEK 20")
        print("=" * 100)

        schedules_created = 0
        for entry in schedule_entries:
            # Check if this entry applies to week 20
            week_20_type = get_week_type(20)  # 'left'

            if entry['week_type'] != 'all' and entry['week_type'] != week_20_type:
                continue  # Skip if wrong week type

            key = (entry['group'], entry['subject'], entry['teacher'])
            workload = created_workloads.get(key)

            if not workload:
                continue

            # Calculate date
            schedule_date = WEEK_20_MONDAY + timedelta(days=entry['day'])

            # Get room
            room = get_or_create_room(entry['room'])

            # Check if schedule already exists
            existing = Schedule.query.filter_by(
                workload_id=workload.id,
                date=schedule_date,
                pair_number=entry['pair']
            ).first()

            if not existing:
                schedule = Schedule(
                    workload_id=workload.id,
                    room_id=room.id if room else None,
                    date=schedule_date,
                    pair_number=entry['pair'],
                    status='planned'
                )
                db.session.add(schedule)
                schedules_created += 1

        db.session.commit()

        # Summary
        print("\n" + "=" * 100)
        print("IMPORT COMPLETE")
        print("=" * 100)
        print(f"Created workloads: {len(created_workloads)}")
        print(f"Created templates: {templates_created}")
        print(f"Created schedule entries: {schedules_created}")

        # Count by group
        print("\n--- Workloads by group ---")
        for group_name in sorted(set(k[0] for k in created_workloads.keys())):
            count = len([k for k in created_workloads.keys() if k[0] == group_name])
            print(f"  {group_name}: {count} workloads")


if __name__ == "__main__":
    full_import()
