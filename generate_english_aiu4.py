#!/usr/bin/env python
"""Generate English schedule for АиУ 4-25 and АиУ 4-25б"""

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
        print("ENGLISH GENERATION FOR АиУ 4-25")
        print("=" * 60)

        current_year = AcademicYear.query.filter_by(is_current=True).first()

        group1 = Group.query.filter_by(name='АиУ 4-25').first()
        group2 = Group.query.filter_by(name='АиУ 4-25б').first()

        semester = 2
        group_ids = [group1.id, group2.id]

        workloads = Workload.query.filter(
            Workload.group_id.in_(group_ids),
            Workload.academic_year_id == current_year.id,
            Workload.semester == semester,
            Workload.discipline.ilike('%Английский%')
        ).all()

        print(f"Workloads: {len(workloads)}")
        for w in workloads:
            template = WorkloadTemplate.query.filter_by(workload_id=w.id).first()
            print(f"  - {w.group.name}: Template ID {template.id if template else 'NONE'}")

        total_created = 0

        for w in workloads:
            print(f"\n--- Generating for {w.group.name} ---")

            generator = SmartScheduleGenerator(
                group_id=w.group_id,
                semester=semester,
                academic_year_id=current_year.id,
                workload_ids=[w.id]
            )

            success = generator.generate()

            if success:
                created_count = len(generator.created_schedules)
                print(f"  Created {created_count} pairs, quality: {generator.quality_score}/100")

                if generator.created_schedules and generator.save_results():
                    total_created += created_count
                    print(f"  Saved!")
            else:
                print(f"  FAILED")
                for error in generator.errors:
                    print(f"  ERROR: {error}")

        print(f"\nTotal: {total_created} schedules")


if __name__ == "__main__":
    run_generation()
