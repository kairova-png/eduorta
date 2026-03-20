#!/usr/bin/env python
"""Update workload hours based on real data"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Workload, Group

app = create_app()

# Real hours per discipline
DISCIPLINE_HOURS = {
    'Казахская литература': 72,
    'Казахский литература': 72,  # Alternative spelling
    'Русский язык и литература': 48,
    'Английский язык': 196,
    'Всемирная история': 24,
    'Математика': 88,
    'Информатика': 72,
    'Физика': 64,
    'Химия': 60,
    'Графика и проектирование': 24,
    'Начальная военная и технологическая подготовка': 64,
    'Физическая культура': 56,
    'Глобальные компетенции': 24,
    'География': 24,  # Similar to global competencies
}

def update_hours():
    with app.app_context():
        print("=" * 80)
        print("UPDATING WORKLOAD HOURS")
        print("=" * 80)

        # Get first course groups
        first_course_groups = Group.query.filter(Group.enrollment_year == 2025).all()
        group_ids = [g.id for g in first_course_groups]

        # Get all workloads for first course
        workloads = Workload.query.filter(Workload.group_id.in_(group_ids)).all()

        print(f"\nFound {len(workloads)} workloads for first course groups")
        print("\nUpdating hours:")
        print("-" * 80)

        updated = 0
        not_found = set()

        for workload in workloads:
            discipline = workload.discipline

            # Find matching hours
            hours = None
            for disc_name, disc_hours in DISCIPLINE_HOURS.items():
                if disc_name.lower() in discipline.lower() or discipline.lower() in disc_name.lower():
                    hours = disc_hours
                    break

            if hours:
                old_hours = workload.total_hours
                if old_hours != hours:
                    workload.total_hours = hours
                    # Calculate hours_per_week (assuming 22 weeks in semester)
                    workload.hours_per_week = max(2, hours // 22 * 2)  # Round to pairs
                    print(f"  {discipline[:50]:50} | {old_hours:3} -> {hours:3} hours")
                    updated += 1
            else:
                not_found.add(discipline)

        db.session.commit()

        print("\n" + "=" * 80)
        print(f"Updated {updated} workloads")

        if not_found:
            print(f"\nDisciplines not in the list (kept default 72 hours):")
            for d in sorted(not_found):
                print(f"  - {d}")

        # Summary
        print("\n" + "=" * 80)
        print("CURRENT HOURS BY DISCIPLINE:")
        print("=" * 80)

        from sqlalchemy import func
        summary = db.session.query(
            Workload.discipline,
            func.count(Workload.id).label('count'),
            Workload.total_hours
        ).filter(
            Workload.group_id.in_(group_ids)
        ).group_by(
            Workload.discipline, Workload.total_hours
        ).order_by(Workload.discipline).all()

        for disc, count, hours in summary:
            print(f"  {disc[:55]:55} | {count:2} groups | {hours:3} hours")

if __name__ == "__main__":
    update_hours()
