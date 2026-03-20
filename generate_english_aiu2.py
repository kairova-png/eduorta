#!/usr/bin/env python
"""Generate English schedule for АиУ 2-25 and АиУ 2-25б using saved templates"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Group, Workload, AcademicYear, WorkloadTemplate
from app.services.smart_scheduler import SmartScheduleGenerator

app = create_app()

def run_generation():
    with app.app_context():
        print("=" * 60)
        print("ENGLISH GENERATION FOR АиУ 2-25 AND АиУ 2-25б")
        print("=" * 60)

        # Get current academic year
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            print("ERROR: No current academic year found!")
            return

        # Find groups
        group1 = Group.query.filter_by(name='АиУ 2-25').first()
        group2 = Group.query.filter_by(name='АиУ 2-25б').first()

        if not group1:
            print("ERROR: Group АиУ 2-25 not found!")
            return

        print(f"Group: {group1.name} (ID: {group1.id})")
        if group2:
            print(f"Subgroup: {group2.name} (ID: {group2.id})")

        semester = 2

        # Find English workloads
        group_ids = [group1.id]
        if group2:
            group_ids.append(group2.id)

        workloads = Workload.query.filter(
            Workload.group_id.in_(group_ids),
            Workload.academic_year_id == current_year.id,
            Workload.semester == semester,
            Workload.discipline.ilike('%Английский%')
        ).all()

        print(f"\nEnglish workloads found: {len(workloads)}")

        for w in workloads:
            template = WorkloadTemplate.query.filter_by(workload_id=w.id).first()
            template_info = f"Template ID {template.id}" if template else "NO TEMPLATE"
            print(f"  - Workload ID {w.id}: {w.group.name} - {w.discipline}")
            print(f"    Teacher: {w.teacher.full_name if w.teacher else 'Not assigned'}")
            print(f"    {template_info}")

        if not workloads:
            print("ERROR: No English workloads found!")
            return

        # Check all have templates
        for w in workloads:
            template = WorkloadTemplate.query.filter_by(workload_id=w.id).first()
            if not template:
                print(f"ERROR: No template for workload {w.id} ({w.group.name})")
                return

        print("\n" + "-" * 60)
        print("STARTING GENERATION")
        print("-" * 60)

        total_created = 0

        for w in workloads:
            print(f"\n--- Generating for {w.group.name} ---")

            try:
                generator = SmartScheduleGenerator(
                    group_id=w.group_id,
                    semester=semester,
                    academic_year_id=current_year.id,
                    workload_ids=[w.id]
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

                    for warning in generator.warnings[:3]:
                        print(f"  WARNING: {warning}")
                else:
                    print("  FAILED: Generation error")
                    for error in generator.errors:
                        print(f"  ERROR: {error}")

            except Exception as e:
                print(f"  EXCEPTION: {e}")
                import traceback
                traceback.print_exc()

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total schedules created: {total_created}")


if __name__ == "__main__":
    run_generation()
