#!/usr/bin/env python
"""Check workloads per group"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Workload, Group
from collections import defaultdict

app = create_app()

with app.app_context():
    # Get first course groups
    first_course_groups = Group.query.filter(Group.enrollment_year == 2025).all()

    # Target groups from Excel
    target_groups = [
        'БНГС 1-25', 'ТДНГ 1-25', 'ЭНГМ 1-25',
        'ЭС 1-25', 'ЭС 2-25', 'ЭС 3-25',
        'ХТП 1-25', 'ХТП 2-25', 'ХТП 3-25',
        'АиУ 1-25', 'АиУ 2-25', 'АиУ 3-25', 'АиУ 4-25', 'АиУ 5-25',
        'ПО 1-25', 'ПО 2-25'
    ]

    print("=" * 80)
    print("WORKLOADS PER GROUP")
    print("=" * 80)

    # Expected subjects
    expected_subjects = {
        'Английский язык', 'Математика', 'Информатика',
        'Казахская литература', 'Казахский литература',
        'Физика', 'Начальная военная и технологическая подготовка',
        'Химия', 'Физическая культура', 'Русский язык и литература',
        'Всемирная история', 'География', 'Глобальные компетенции'
    }

    for group_name in target_groups:
        group = Group.query.filter_by(name=group_name).first()
        if not group:
            print(f"\n{group_name}: NOT FOUND")
            continue

        workloads = Workload.query.filter_by(group_id=group.id).all()
        subjects = set(w.discipline for w in workloads)

        print(f"\n{group_name} ({len(workloads)} workloads):")
        for w in sorted(workloads, key=lambda x: x.discipline):
            print(f"  - {w.discipline}")

        # Find missing subjects
        missing = expected_subjects - subjects
        if missing:
            print(f"  MISSING: {missing}")
