#!/usr/bin/env python
"""Analyze Excel schedule patterns - split groups, alternating weeks"""

import pandas as pd
import re
from collections import defaultdict

excel_path = r"C:\Users\tkulz\Downloads\college_schedule_backup_20251212\Копия 1 курс Расписание 2 семестр.xlsx"
df = pd.read_excel(excel_path, sheet_name=0, header=None)

print("=" * 100)
print("DETAILED ANALYSIS OF EXCEL PATTERNS")
print("=" * 100)

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

# Days and their row ranges
DAYS = {
    'ПОНЕДЕЛЬНИК': [(5, 6), (7, 8), (9, 10), (11, 12)],  # 4 pairs: (subject_row, teacher_row)
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

def analyze_cell(subject_text, teacher_text, room_text):
    """Analyze a cell and return structured data about patterns"""
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
        'split_english': False,
        'alternating': False,
        'left_week': None,
        'right_week': None,
    }

    # Parse subjects
    subjects = [s.strip() for s in subject.split('/') if s.strip()]

    # Parse teachers
    teachers = [t.strip() for t in teacher.split('/') if t.strip()]

    # Parse rooms
    rooms = [r.strip() for r in room.split('/') if r.strip()]

    result['subjects'] = subjects
    result['teachers'] = teachers
    result['rooms'] = rooms

    # Detect patterns

    # Pattern 1: Starts with "/" - left week subject
    if subject.startswith('/'):
        result['pattern'] = 'left_week_only'
        result['alternating'] = True
        result['left_week'] = subjects[0] if subjects else None

    # Pattern 2: Ends with "/" - right week subject
    elif subject.endswith('/'):
        result['pattern'] = 'right_week_only'
        result['alternating'] = True
        result['right_week'] = subjects[0] if subjects else None

    # Pattern 3: Two subjects with slash (alternating weeks)
    elif len(subjects) == 2:
        result['pattern'] = 'alternating_subjects'
        result['alternating'] = True
        result['left_week'] = subjects[0]
        result['right_week'] = subjects[1]

        # Check if it's split English (same subject, 2 teachers)
        if subjects[0] == subjects[1] == 'Английский язык':
            result['pattern'] = 'split_english'
            result['split_english'] = True
            result['alternating'] = False

        # Check for 3 teachers with 2 subjects pattern
        elif len(teachers) == 3:
            result['pattern'] = 'alternating_with_split'
            # Left week: first subject split between first 2 teachers
            # Right week: second subject with 3rd teacher

    # Pattern 4: Single subject but 2 teachers (split group)
    elif len(subjects) == 1 and len(teachers) == 2:
        if 'Английский' in subjects[0] or 'язык' in subjects[0].lower():
            result['pattern'] = 'split_english'
            result['split_english'] = True

    return result

# Collect all patterns
all_patterns = []

print("\n" + "=" * 100)
print("ALL CELLS WITH PATTERNS")
print("=" * 100)

for day_name, pairs in DAYS.items():
    for pair_idx, (subj_row, teacher_row) in enumerate(pairs, 1):
        for group_name, (subj_col, room_col) in GROUP_COLUMNS.items():
            subject_text = df.iloc[subj_row, subj_col]
            teacher_text = df.iloc[teacher_row, subj_col]
            room_text = df.iloc[teacher_row, room_col]

            analysis = analyze_cell(subject_text, teacher_text, room_text)

            if analysis and analysis['pattern'] != 'simple':
                all_patterns.append({
                    'day': day_name,
                    'pair': pair_idx,
                    'group': group_name,
                    **analysis
                })

# Print patterns by type
pattern_types = defaultdict(list)
for p in all_patterns:
    pattern_types[p['pattern']].append(p)

for pattern_type, items in sorted(pattern_types.items()):
    print(f"\n{'='*100}")
    print(f"PATTERN: {pattern_type} ({len(items)} occurrences)")
    print("=" * 100)

    for item in items[:20]:  # Show first 20 of each type
        print(f"\n  {item['day']} | Пара {item['pair']} | {item['group']}")
        print(f"    Предметы: {item['raw_subject']}")
        print(f"    Преподаватели: {item['raw_teacher']}")
        print(f"    Кабинеты: {item['raw_room']}")
        print(f"    -> subjects: {item['subjects']}")
        print(f"    -> teachers: {item['teachers']}")
        print(f"    -> rooms: {item['rooms']}")
        if item['alternating']:
            print(f"    -> LEFT WEEK: {item['left_week']}")
            print(f"    -> RIGHT WEEK: {item['right_week']}")
        if item['split_english']:
            print(f"    -> SPLIT ENGLISH: Yes (2 subgroups)")

    if len(items) > 20:
        print(f"\n  ... and {len(items) - 20} more")

# Summary
print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
for pattern_type, items in sorted(pattern_types.items()):
    print(f"  {pattern_type}: {len(items)} occurrences")

# Count split English cases
split_english = [p for p in all_patterns if p['split_english']]
print(f"\n  Total SPLIT ENGLISH cases: {len(split_english)}")

# Count alternating subjects
alternating = [p for p in all_patterns if p['alternating']]
print(f"  Total ALTERNATING cases: {len(alternating)}")
