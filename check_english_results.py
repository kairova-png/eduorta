#!/usr/bin/env python
"""Check results of English generation for АиУ 1-25"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Schedule, Workload, Group
from datetime import date

app = create_app()

def check_results():
    with app.app_context():
        print("=" * 60)
        print("ENGLISH GENERATION RESULTS FOR АиУ 1-25")
        print("=" * 60)

        # Find АиУ 1-25 and АиУ 1-25б groups
        group1 = Group.query.filter_by(name='АиУ 1-25').first()
        group2 = Group.query.filter_by(name='АиУ 1-25б').first()

        if not group1:
            print("ERROR: Group АиУ 1-25 not found!")
            return

        print(f"\nGroup: {group1.name} (ID: {group1.id})")
        if group2:
            print(f"Subgroup: {group2.name} (ID: {group2.id})")

        # Find English workloads
        workloads = Workload.query.filter(
            Workload.group_id.in_([group1.id, group2.id] if group2 else [group1.id]),
            Workload.discipline.ilike('%Английский%')
        ).all()

        print(f"\nEnglish workloads found: {len(workloads)}")

        for w in workloads:
            print(f"\n--- Workload ID {w.id}: {w.group.name} ---")
            print(f"  Discipline: {w.discipline}")
            print(f"  Teacher: {w.teacher.full_name if w.teacher else 'Not assigned'}")
            print(f"  Hours per week: {w.hours_per_week}")

            # Count schedules from Jan 12, 2026
            schedules = Schedule.query.filter(
                Schedule.workload_id == w.id,
                Schedule.date >= date(2026, 1, 12)
            ).order_by(Schedule.date, Schedule.pair_number).all()

            print(f"  Schedules created: {len(schedules)}")

            if schedules:
                print(f"  First 10 entries:")
                for s in schedules[:10]:
                    room_str = s.room.number if s.room else "No room"
                    print(f"    {s.date} pair {s.pair_number}: room {room_str}")

                if len(schedules) > 10:
                    print(f"    ... and {len(schedules) - 10} more")

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        total_schedules = sum(
            Schedule.query.filter(
                Schedule.workload_id == w.id,
                Schedule.date >= date(2026, 1, 12)
            ).count() for w in workloads
        )
        print(f"Total English schedules created: {total_schedules}")


if __name__ == "__main__":
    check_results()
