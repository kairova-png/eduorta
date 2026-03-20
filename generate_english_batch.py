#!/usr/bin/env python
"""Generate English schedules for multiple groups"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Group, Workload, AcademicYear, Schedule
from app.services.smart_scheduler import SmartScheduleGenerator
from datetime import date

app = create_app()

GROUPS = [
    'АиУ 5-25', 'АиУ 5-25б',
    'ПО 1-25', 'ПО 1-25б',
    'ПО 2-25', 'ПО 2-25б',
    'ТДНГ 1-25', 'ТДНГ 1-25б'
]

def run_generation():
    with app.app_context():
        print("=" * 60)
        print("GENERATING ENGLISH FOR MULTIPLE GROUPS")
        print("=" * 60)

        current_year = AcademicYear.query.filter_by(is_current=True).first()
        semester = 2
        total_created = 0

        for group_name in GROUPS:
            print(f"\n--- {group_name} ---")

            group = Group.query.filter_by(name=group_name).first()
            if not group:
                print(f"  Group not found")
                continue

            workload = Workload.query.filter(
                Workload.group_id == group.id,
                Workload.academic_year_id == current_year.id,
                Workload.semester == semester,
                Workload.discipline.ilike('%Английский%')
            ).first()

            if not workload:
                print(f"  No English workload")
                continue

            # Check existing schedules
            existing = Schedule.query.filter(
                Schedule.workload_id == workload.id,
                Schedule.date >= date(2026, 1, 12)
            ).count()

            if existing > 0:
                print(f"  Already has {existing} schedules, skipping")
                continue

            try:
                generator = SmartScheduleGenerator(
                    group_id=group.id,
                    semester=semester,
                    academic_year_id=current_year.id,
                    workload_ids=[workload.id]
                )

                success = generator.generate()

                if success and generator.created_schedules:
                    created = len(generator.created_schedules)
                    if generator.save_results():
                        total_created += created
                        hours = created * 2
                        print(f"  Created {created} pairs ({hours} hours)")
                    else:
                        print(f"  ERROR saving")
                else:
                    print(f"  Generation failed")
                    for e in generator.errors[:2]:
                        print(f"    {e}")

            except Exception as e:
                print(f"  Exception: {e}")

        print("\n" + "=" * 60)
        print(f"TOTAL: {total_created} schedules created")


if __name__ == "__main__":
    run_generation()
