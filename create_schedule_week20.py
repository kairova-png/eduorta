#!/usr/bin/env python
"""Create schedule entries for week 20 based on Excel data"""

import pandas as pd
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Group, Teacher, Workload, Schedule, Room, AcademicYear

app = create_app()

EXCEL_PATH = r"C:\Users\tkulz\Downloads\college_schedule_backup_20251212\Копия 1 курс Расписание 2 семестр.xlsx"
WEEK_20_MONDAY = date(2026, 1, 12)

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
    if not subject:
        return False
    return 'Английский' in subject or 'английский' in subject


def parse_cell_for_schedule(subject_text, teacher_text, room_text, week_type='left'):
    """
    Parse cell and return entries that apply to the given week type.
    Week 20 is a LEFT week (even number).
    """
    subject = clean(subject_text)
    teacher = clean(teacher_text)
    room = clean(room_text)

    if not subject:
        return []

    subjects = [s.strip() for s in subject.split('/') if s.strip()]
    teachers = [t.strip() for t in teacher.split('/') if t.strip()]
    rooms = [r.strip() for r in room.split('/') if r.strip()]

    entries = []

    # Pattern: Starts with "/" like "/Subject" - RIGHT week only (subject in second position)
    if subject.startswith('/') and subjects:
        if week_type == 'right' and teachers:
            entries.append((subjects[0], teachers[0], rooms[0] if rooms else None, False))
        return entries

    # Pattern: Ends with "/" like "Subject/" - LEFT week only (subject in first position)
    if subject.endswith('/') and subjects:
        if week_type == 'left' and teachers:
            entries.append((subjects[0], teachers[0], rooms[0] if rooms else None, False))
        return entries

    # Pattern: 2 subjects with 3 teachers
    if len(subjects) == 2 and len(teachers) == 3:
        if is_english(subjects[0]):
            # English first: LEFT = English split, RIGHT = second subject
            if week_type == 'left':
                entries.append((subjects[0], teachers[0], rooms[0] if rooms else None, False))
                entries.append((subjects[0], teachers[1], rooms[1] if len(rooms) > 1 else None, True))
            else:  # right
                entries.append((subjects[1], teachers[2], rooms[2] if len(rooms) > 2 else None, False))
        else:
            # English second: LEFT = first subject, RIGHT = English split
            if week_type == 'left':
                entries.append((subjects[0], teachers[0], rooms[0] if rooms else None, False))
            else:  # right
                entries.append((subjects[1], teachers[1], rooms[1] if len(rooms) > 1 else None, False))
                entries.append((subjects[1], teachers[2], rooms[2] if len(rooms) > 2 else None, True))
        return entries

    # Pattern: 2 different subjects with 2 teachers (alternating)
    if len(subjects) == 2 and len(teachers) >= 2 and subjects[0] != subjects[1]:
        if week_type == 'left':
            entries.append((subjects[0], teachers[0], rooms[0] if rooms else None, False))
        else:
            entries.append((subjects[1], teachers[1], rooms[1] if len(rooms) > 1 else None, False))
        return entries

    # Pattern: Single subject with 2 teachers (split English) - applies to ALL weeks
    if len(subjects) == 1 and len(teachers) == 2 and is_english(subjects[0]):
        entries.append((subjects[0], teachers[0], rooms[0] if rooms else None, False))
        entries.append((subjects[0], teachers[1], rooms[1] if len(rooms) > 1 else None, True))
        return entries

    # Pattern: Same subject twice with 2 teachers
    if len(subjects) == 2 and subjects[0] == subjects[1] and len(teachers) == 2:
        entries.append((subjects[0], teachers[0], rooms[0] if rooms else None, False))
        entries.append((subjects[0], teachers[1], rooms[1] if len(rooms) > 1 else None, True))
        return entries

    # Simple pattern - applies to all weeks
    if subjects and teachers:
        entries.append((subjects[0], teachers[0], rooms[0] if rooms else None, False))

    return entries


def create_schedule():
    with app.app_context():
        print("=" * 80)
        print("CREATING SCHEDULE FOR WEEK 20")
        print("=" * 80)

        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        df = pd.read_excel(EXCEL_PATH, sheet_name=0, header=None)

        # Week 20 is LEFT week (even number)
        week_type = get_week_type(20)
        print(f"Week 20 type: {week_type}")

        created = 0
        errors = 0

        for group_name, (subj_col, room_col) in GROUP_COLUMNS.items():
            group = Group.query.filter_by(name=group_name).first()
            if not group:
                continue

            print(f"\n--- {group_name} ---")

            for day_name, pairs in DAYS.items():
                day_idx = list(DAYS.keys()).index(day_name)
                schedule_date = WEEK_20_MONDAY + timedelta(days=day_idx)

                for pair_idx, (subj_row, teacher_row) in enumerate(pairs, 1):
                    subject_text = df.iloc[subj_row, subj_col]
                    teacher_text = df.iloc[teacher_row, subj_col]
                    room_text = df.iloc[teacher_row, room_col]

                    entries = parse_cell_for_schedule(subject_text, teacher_text, room_text, week_type)

                    for subj, teacher_name, room_num, is_subgroup in entries:
                        if not subj or not teacher_name:
                            continue

                        # Get target group
                        target_group_name = group_name + 'б' if is_subgroup else group_name
                        target_group = Group.query.filter_by(name=target_group_name).first()

                        if not target_group:
                            continue

                        # Find teacher
                        teacher = Teacher.query.filter(Teacher.full_name.ilike(f'%{teacher_name}%')).first()
                        if not teacher:
                            continue

                        # Find workload
                        workload = Workload.query.filter_by(
                            teacher_id=teacher.id,
                            group_id=target_group.id,
                            discipline=subj,
                            academic_year_id=academic_year.id
                        ).first()

                        if not workload:
                            # Try without exact discipline match
                            workload = Workload.query.filter(
                                Workload.teacher_id == teacher.id,
                                Workload.group_id == target_group.id,
                                Workload.discipline.ilike(f'%{subj[:10]}%'),
                                Workload.academic_year_id == academic_year.id
                            ).first()

                        if not workload:
                            errors += 1
                            continue

                        # Get room
                        room = None
                        if room_num:
                            room = Room.query.filter_by(number=str(room_num).strip()).first()
                            if not room:
                                room = Room(number=str(room_num).strip())
                                db.session.add(room)
                                db.session.flush()

                        # Check if schedule exists
                        existing = Schedule.query.filter_by(
                            workload_id=workload.id,
                            date=schedule_date,
                            pair_number=pair_idx
                        ).first()

                        if not existing:
                            schedule = Schedule(
                                workload_id=workload.id,
                                room_id=room.id if room else None,
                                date=schedule_date,
                                pair_number=pair_idx,
                                status='planned'
                            )
                            db.session.add(schedule)
                            created += 1
                            print(f"  + {day_name[:2]} пара {pair_idx}: {subj[:20]} | {target_group_name} | {teacher_name}")

        db.session.commit()

        print("\n" + "=" * 80)
        print(f"Created schedule entries: {created}")
        print(f"Errors (workload not found): {errors}")

        # Verify
        total = Schedule.query.count()
        print(f"Total schedules in DB: {total}")


if __name__ == "__main__":
    create_schedule()
