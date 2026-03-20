#!/usr/bin/env python
"""Add missing workloads based on Excel analysis"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Workload, Group, Teacher, AcademicYear

app = create_app()

# Hours per discipline
DISCIPLINE_HOURS = {
    'Казахская литература': 72,
    'Казахский литература': 72,
    'Русский язык и литература': 48,
    'Английский язык': 196,
    'Всемирная история': 24,
    'Математика': 88,
    'Информатика': 72,
    'Физика': 64,
    'Химия': 60,
    'География': 24,
    'Начальная военная и технологическая подготовка': 64,
    'Физическая культура': 56,
    'Глобальные компетенции': 24,
}

# Read Excel to get real subjects per group
excel_path = r"C:\Users\tkulz\Downloads\college_schedule_backup_20251212\Копия 1 курс Расписание 2 семестр.xlsx"
df = pd.read_excel(excel_path, sheet_name=0, header=None)

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

SUBJECT_ROWS = [
    5, 7, 9, 11,      # Monday
    18, 20, 22, 24,   # Tuesday
    31, 33, 35, 37,   # Wednesday
    44, 46, 48, 50,   # Thursday
    57, 59, 61, 63,   # Friday
    70, 72, 74, 76,   # Saturday
]

def clean_subject(text):
    if pd.isna(text) or text is None:
        return None
    text = str(text).strip().replace('\n', '').strip()
    if text in ['', 'nan', 'None']:
        return None
    return text

def get_subjects_from_excel():
    """Get all subjects per group from Excel"""
    subjects_by_group = {}

    for group_name, (subj_col, room_col) in GROUP_COLUMNS.items():
        subjects = set()
        for row in SUBJECT_ROWS:
            cell = df.iloc[row, subj_col]
            subject = clean_subject(cell)
            if subject:
                # Split if multiple subjects
                for part in subject.split('/'):
                    part = part.strip()
                    if part:
                        subjects.add(part)
        subjects_by_group[group_name] = subjects

    return subjects_by_group

with app.app_context():
    print("=" * 80)
    print("FIXING MISSING WORKLOADS")
    print("=" * 80)

    # Get academic year
    academic_year = AcademicYear.query.filter_by(is_current=True).first()
    if not academic_year:
        academic_year = AcademicYear.query.first()

    # Get subjects from Excel
    excel_subjects = get_subjects_from_excel()

    # Create a default "Вакант" teacher for missing assignments
    vacant_teacher = Teacher.query.filter_by(full_name='Вакант').first()
    if not vacant_teacher:
        vacant_teacher = Teacher(full_name='Вакант')
        db.session.add(vacant_teacher)
        db.session.flush()
        print("Created 'Вакант' teacher for unassigned workloads")

    added = 0

    for group_name, subjects in excel_subjects.items():
        group = Group.query.filter_by(name=group_name).first()
        if not group:
            print(f"Group not found: {group_name}")
            continue

        # Get existing workloads for this group
        existing = Workload.query.filter_by(group_id=group.id).all()
        existing_disciplines = set(w.discipline for w in existing)

        # Find missing subjects
        missing = subjects - existing_disciplines

        if missing:
            print(f"\n{group_name} - adding {len(missing)} missing workloads:")

            for discipline in missing:
                # Get hours for this discipline
                hours = DISCIPLINE_HOURS.get(discipline, 72)

                # Check if we have a similar discipline with different spelling
                # (e.g., "Казахский литература" vs "Казахская литература")
                for existing_disc in existing_disciplines:
                    if discipline.lower()[:10] == existing_disc.lower()[:10]:
                        print(f"  SKIP: {discipline} (similar to {existing_disc})")
                        break
                else:
                    # Create workload with vacant teacher
                    workload = Workload(
                        teacher_id=vacant_teacher.id,
                        group_id=group.id,
                        discipline=discipline,
                        academic_year_id=academic_year.id,
                        semester=2,
                        total_hours=hours,
                        hours_per_week=max(2, hours // 22 * 2),
                        lesson_type='theory'
                    )
                    db.session.add(workload)
                    print(f"  + {discipline} ({hours} hours)")
                    added += 1

    db.session.commit()

    print("\n" + "=" * 80)
    print(f"Added {added} missing workloads")
    print("=" * 80)

    # Verify
    print("\nVERIFICATION - Workloads per group:")
    for group_name in GROUP_COLUMNS.keys():
        group = Group.query.filter_by(name=group_name).first()
        if group:
            count = Workload.query.filter_by(group_id=group.id).count()
            print(f"  {group_name}: {count} workloads")
