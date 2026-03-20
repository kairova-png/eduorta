#!/usr/bin/env python
"""Import schedule from Excel file for 1st course groups"""

import pandas as pd
import sys
import os
import re
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import (
    Group, Teacher, Workload, Schedule, Room, AcademicYear, GUP
)

app = create_app()

# Excel file path
EXCEL_PATH = r"C:\Users\tkulz\Downloads\college_schedule_backup_20251212\Копия 1 курс Расписание 2 семестр.xlsx"

# Week 20 Monday date (from GUP data)
WEEK_20_MONDAY = date(2026, 1, 12)

# Group columns mapping (group_name -> (subject_col, room_col))
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

# Day rows mapping (day_name -> start_row)
DAY_ROWS = {
    'ПОНЕДЕЛЬНИК': 5,
    'ВТОРНИК': 18,
    'СРЕДА': 31,
    'ЧЕТВЕРГ': 44,
    'ПЯТНИЦА': 57,
    'СУББОТА': 70,
}

# Pair times
PAIR_TIMES = {
    'I': 1,
    'II': 2,
    'III': 3,
    'IV': 4,
    'V': 5,
    'VI': 6,
}


def clean_text(text):
    """Clean and normalize text"""
    if pd.isna(text) or text is None:
        return None
    text = str(text).strip()
    if text in ['', 'nan', 'None']:
        return None
    # Remove newlines
    text = text.replace('\n', '').strip()
    return text


def parse_teacher_room(text):
    """Parse teacher names and room numbers from cell"""
    if not text:
        return [], []

    # Split by / for multiple teachers
    parts = text.split('/')
    teachers = []
    rooms = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check if it's a room number (digits or С/з or similar)
        if re.match(r'^[\d]+$', part) or part in ['С/з', 'С/З', 'с/з']:
            rooms.append(part)
        else:
            # It's a teacher name
            if part and part not in ['', 'Вакант', 'Вакант.']:
                teachers.append(part)

    return teachers, rooms


def parse_subject(text):
    """Parse subject name, handling split subjects"""
    if not text:
        return None

    text = clean_text(text)
    if not text:
        return None

    # Handle subjects like "Английский язык/Физика" - take first one
    if '/' in text:
        parts = [p.strip() for p in text.split('/') if p.strip()]
        if parts:
            return parts[0]

    return text


def get_or_create_teacher(name):
    """Get existing teacher or create new one"""
    if not name:
        return None

    name = name.strip()
    if not name or name in ['Вакант', 'Вакант.', '']:
        return None

    # Try to find existing teacher
    teacher = Teacher.query.filter(
        Teacher.full_name.ilike(f'%{name}%')
    ).first()

    if not teacher:
        # Create new teacher
        teacher = Teacher(full_name=name)
        db.session.add(teacher)
        db.session.flush()
        print(f"  Created teacher: {name}")

    return teacher


def get_or_create_room(number):
    """Get existing room or create new one"""
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
        print(f"  Created room: {number}")

    return room


def get_or_create_workload(teacher, group, discipline, academic_year):
    """Get existing workload or create new one"""
    if not teacher or not group or not discipline:
        return None

    workload = Workload.query.filter_by(
        teacher_id=teacher.id,
        group_id=group.id,
        discipline=discipline,
        academic_year_id=academic_year.id
    ).first()

    if not workload:
        workload = Workload(
            teacher_id=teacher.id,
            group_id=group.id,
            discipline=discipline,
            academic_year_id=academic_year.id,
            semester=2,  # 2nd semester
            total_hours=72,  # Default hours
            hours_per_week=4,  # Default 2 pairs per week
            lesson_type='theory'
        )
        db.session.add(workload)
        db.session.flush()
        print(f"  Created workload: {discipline} - {group.name} - {teacher.full_name}")

    return workload


def import_schedule():
    """Main import function"""
    with app.app_context():
        print("=" * 80)
        print("IMPORTING SCHEDULE FROM EXCEL")
        print("=" * 80)

        # Get academic year
        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not academic_year:
            academic_year = AcademicYear.query.first()
        print(f"\nAcademic year: {academic_year.name}")

        # Read Excel
        print(f"\nReading Excel: {EXCEL_PATH}")
        df = pd.read_excel(EXCEL_PATH, sheet_name=0, header=None)
        print(f"Shape: {df.shape}")

        # Delete existing workloads and schedules for 1st course groups
        print("\n" + "=" * 80)
        print("DELETING EXISTING DATA")
        print("=" * 80)

        first_course_groups = Group.query.filter(Group.enrollment_year == 2025).all()
        group_ids = [g.id for g in first_course_groups]
        print(f"Found {len(group_ids)} first course groups")

        # Get workload IDs for these groups
        workloads_to_delete = Workload.query.filter(
            Workload.group_id.in_(group_ids)
        ).all()
        workload_ids = [w.id for w in workloads_to_delete]
        print(f"Found {len(workload_ids)} workloads to delete")

        # Delete schedules first (due to foreign key)
        if workload_ids:
            deleted_schedules = Schedule.query.filter(
                Schedule.workload_id.in_(workload_ids)
            ).delete(synchronize_session='fetch')
            print(f"Deleted {deleted_schedules} schedule entries")

            # Delete workloads
            deleted_workloads = Workload.query.filter(
                Workload.id.in_(workload_ids)
            ).delete(synchronize_session='fetch')
            print(f"Deleted {deleted_workloads} workload entries")
        else:
            print("No existing workloads to delete")

        db.session.commit()

        # Parse and import schedule
        print("\n" + "=" * 80)
        print("IMPORTING NEW DATA")
        print("=" * 80)

        # Get groups from database
        groups = {}
        for group_name in GROUP_COLUMNS.keys():
            group = Group.query.filter_by(name=group_name).first()
            if group:
                groups[group_name] = group
                print(f"Found group: {group_name} (id={group.id})")
            else:
                print(f"WARNING: Group not found: {group_name}")

        # Track created items
        created_workloads = set()
        created_schedules = 0

        # Process each day
        for day_name, start_row in DAY_ROWS.items():
            day_offset = list(DAY_ROWS.keys()).index(day_name)
            schedule_date = WEEK_20_MONDAY
            from datetime import timedelta
            schedule_date = WEEK_20_MONDAY + timedelta(days=day_offset)

            print(f"\n--- {day_name} ({schedule_date}) ---")

            # Process each pair (4 pairs per day, 2 rows each)
            for pair_idx in range(4):
                pair_row = start_row + (pair_idx * 2)  # Subject row
                teacher_row = pair_row + 1  # Teacher/room row

                # Get pair number from column 2
                pair_num_str = clean_text(df.iloc[pair_row, 2])
                pair_number = PAIR_TIMES.get(pair_num_str, pair_idx + 1)

                # Process each group
                for group_name, (subj_col, room_col) in GROUP_COLUMNS.items():
                    if group_name not in groups:
                        continue

                    group = groups[group_name]

                    # Get subject
                    subject_raw = clean_text(df.iloc[pair_row, subj_col])
                    subject = parse_subject(subject_raw)

                    if not subject:
                        continue

                    # Get teacher and room info
                    teacher_room_raw = clean_text(df.iloc[teacher_row, subj_col])
                    room_raw = clean_text(df.iloc[teacher_row, room_col])

                    # Parse teachers
                    teachers, rooms_from_teacher = parse_teacher_room(teacher_room_raw)
                    _, rooms_from_col = parse_teacher_room(room_raw)

                    # Combine rooms
                    all_rooms = rooms_from_teacher + rooms_from_col

                    # Get first teacher and room
                    teacher_name = teachers[0] if teachers else None
                    room_number = all_rooms[0] if all_rooms else None

                    if not teacher_name:
                        print(f"  SKIP: No teacher for {group_name} pair {pair_number} - {subject}")
                        continue

                    # Get or create teacher
                    teacher = get_or_create_teacher(teacher_name)
                    if not teacher:
                        continue

                    # Get or create room
                    room = get_or_create_room(room_number)

                    # Get or create workload
                    workload = get_or_create_workload(teacher, group, subject, academic_year)
                    if not workload:
                        continue

                    workload_key = (teacher.id, group.id, subject)
                    created_workloads.add(workload_key)

                    # Check if schedule entry already exists
                    existing = Schedule.query.filter_by(
                        workload_id=workload.id,
                        date=schedule_date,
                        pair_number=pair_number
                    ).first()

                    if not existing:
                        schedule_entry = Schedule(
                            workload_id=workload.id,
                            room_id=room.id if room else None,
                            date=schedule_date,
                            pair_number=pair_number,
                            status='planned'
                        )
                        db.session.add(schedule_entry)
                        created_schedules += 1
                        print(f"  + {group_name} | Pair {pair_number} | {subject} | {teacher_name} | Room {room_number}")

        db.session.commit()

        # Summary
        print("\n" + "=" * 80)
        print("IMPORT COMPLETE")
        print("=" * 80)
        print(f"Created/found workloads: {len(created_workloads)}")
        print(f"Created schedule entries: {created_schedules}")
        print(f"Schedule date range: {WEEK_20_MONDAY} (Monday, Week 20)")


if __name__ == "__main__":
    import_schedule()
