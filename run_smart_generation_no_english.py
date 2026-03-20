#!/usr/bin/env python
"""
Run smart generation for all workloads EXCEPT English language
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Group, Workload, AcademicYear, WorkloadTemplate
from app.services.smart_scheduler import SmartScheduleGenerator

app = create_app()

def run_generation():
    with app.app_context():
        print("=" * 80)
        print("SMART GENERATION - ALL WORKLOADS EXCEPT ENGLISH")
        print("=" * 80)

        # Get current academic year
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            print("ERROR: No current academic year found!")
            return

        print(f"Academic year: {current_year.name}")

        # Get all groups with workloads (first course - 2025)
        groups = Group.query.filter(Group.enrollment_year == 2025).all()
        print(f"\nFound {len(groups)} first-course groups")

        semester = 2  # Second semester

        total_created = 0
        total_errors = 0

        for group in groups:
            # Skip subgroups (ending with 'б')
            if group.name.endswith('б'):
                continue

            print(f"\n--- {group.name} ---")

            # Get workloads for this group, excluding English
            workloads = Workload.query.filter(
                Workload.group_id == group.id,
                Workload.academic_year_id == current_year.id,
                Workload.semester == semester,
                ~Workload.discipline.ilike('%Английский%'),
                ~Workload.discipline.ilike('%English%')
            ).all()

            if not workloads:
                print("  No workloads (excluding English)")
                continue

            # Get workload IDs
            workload_ids = [w.id for w in workloads]

            print(f"  Workloads to generate ({len(workloads)}):")
            for w in workloads:
                has_template = WorkloadTemplate.query.filter_by(workload_id=w.id).first() is not None
                template_mark = " [TEMPLATE]" if has_template else ""
                print(f"    - {w.discipline}{template_mark}")

            # Run smart generator
            try:
                generator = SmartScheduleGenerator(
                    group_id=group.id,
                    semester=semester,
                    academic_year_id=current_year.id,
                    workload_ids=workload_ids
                )

                success = generator.generate()

                if success:
                    created_count = len(generator.created_schedules)
                    print(f"  SUCCESS: Created {created_count} pairs, quality: {generator.quality_score}/100")

                    if generator.created_schedules:
                        if generator.save_results():
                            total_created += created_count
                            print(f"  Saved {created_count} schedules")
                        else:
                            print("  ERROR saving results")
                            total_errors += 1

                    # Show warnings
                    for warning in generator.warnings[:3]:
                        print(f"  WARNING: {warning}")

                else:
                    print("  FAILED: Generation error")
                    total_errors += 1
                    for error in generator.errors:
                        print(f"  ERROR: {error}")

            except Exception as e:
                print(f"  EXCEPTION: {e}")
                total_errors += 1

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total schedules created: {total_created}")
        print(f"Groups with errors: {total_errors}")


if __name__ == "__main__":
    run_generation()
