#!/usr/bin/env python
"""Analyze all subjects in Excel schedule"""

import pandas as pd
import re
from collections import defaultdict

# Read Excel
excel_path = r"C:\Users\tkulz\Downloads\college_schedule_backup_20251212\Копия 1 курс Расписание 2 семестр.xlsx"
df = pd.read_excel(excel_path, sheet_name=0, header=None)

print("=" * 80)
print("ANALYZING ALL SUBJECTS IN EXCEL")
print("=" * 80)

# Group columns (subject columns only)
GROUP_COLUMNS = {
    'БНГС 1-25': 3,
    'ТДНГ 1-25': 5,
    'ЭНГМ 1-25': 7,
    'ЭС 1-25': 9,
    'ЭС 2-25': 11,
    'ЭС 3-25': 13,
    'ХТП 1-25': 15,
    'ХТП 2-25': 17,
    'ХТП 3-25': 19,
    'АиУ 1-25': 21,
    'АиУ 2-25': 23,
    'АиУ 3-25': 25,
    'АиУ 4-25': 27,
    'АиУ 5-25': 29,
    'ПО 1-25': 31,
    'ПО 2-25': 33,
}

# Subject rows (where subjects are listed)
# Monday: rows 5, 7, 9, 11 (pairs 1-4)
# Tuesday: rows 18, 20, 22, 24
# Wednesday: rows 31, 33, 35, 37
# Thursday: rows 44, 46, 48, 50
# Friday: rows 57, 59, 61, 63
# Saturday: rows 70, 72, 74, 76

SUBJECT_ROWS = [
    5, 7, 9, 11,      # Monday
    18, 20, 22, 24,   # Tuesday
    31, 33, 35, 37,   # Wednesday
    44, 46, 48, 50,   # Thursday
    57, 59, 61, 63,   # Friday
    70, 72, 74, 76,   # Saturday
]

# Collect all subjects
all_subjects = set()
subjects_by_group = defaultdict(set)

def clean_subject(text):
    """Clean subject name"""
    if pd.isna(text) or text is None:
        return None
    text = str(text).strip()
    if text in ['', 'nan', 'None']:
        return None
    text = text.replace('\n', '').strip()
    return text

def split_subjects(text):
    """Split subjects like 'Английский язык/Физика'"""
    if not text:
        return []
    parts = text.split('/')
    return [p.strip() for p in parts if p.strip()]

for row in SUBJECT_ROWS:
    for group_name, col in GROUP_COLUMNS.items():
        cell = df.iloc[row, col]
        subject = clean_subject(cell)
        if subject:
            # Split if multiple subjects
            for subj in split_subjects(subject):
                if subj:
                    all_subjects.add(subj)
                    subjects_by_group[group_name].add(subj)

# Print all unique subjects
print(f"\nAll unique subjects found ({len(all_subjects)}):")
print("-" * 80)
for subj in sorted(all_subjects):
    print(f"  - {subj}")

# Hours mapping from user
HOURS_MAP = {
    'Казахская литература': 72,
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

print("\n" + "=" * 80)
print("SUBJECTS WITHOUT HOURS MAPPING:")
print("=" * 80)

for subj in sorted(all_subjects):
    found = False
    for key in HOURS_MAP.keys():
        if key.lower() in subj.lower() or subj.lower() in key.lower():
            found = True
            break
    if not found:
        print(f"  - {subj}")

print("\n" + "=" * 80)
print("SUBJECTS BY GROUP:")
print("=" * 80)

for group_name in sorted(subjects_by_group.keys()):
    subjects = subjects_by_group[group_name]
    print(f"\n{group_name} ({len(subjects)} subjects):")
    for subj in sorted(subjects):
        print(f"  - {subj}")
