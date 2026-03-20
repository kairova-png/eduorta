#!/usr/bin/env python
"""Check English results for АиУ 2-25"""

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
        print("ENGLISH RESULTS FOR АиУ 2-25")
        print("=" * 60)

        group1 = Group.query.filter_by(name='АиУ 2-25').first()
        group2 = Group.query.filter_by(name='АиУ 2-25б').first()

        workloads = Workload.query.filter(
            Workload.group_id.in_([group1.id, group2.id]),
            Workload.discipline.ilike('%Английский%')
        ).all()

        for w in workloads:
            schedules = Schedule.query.filter(
                Schedule.workload_id == w.id,
                Schedule.date >= date(2026, 1, 12)
            ).order_by(Schedule.date, Schedule.pair_number).all()

            print(f"\n{w.group.name}: {len(schedules)} schedules")
            print(f"  Teacher: {w.teacher.full_name if w.teacher else 'N/A'}")
            if schedules:
                print(f"  First entries:")
                for s in schedules[:5]:
                    room = s.room.number if s.room else "No room"
                    print(f"    {s.date} pair {s.pair_number}: room {room}")

        total = sum(
            Schedule.query.filter(
                Schedule.workload_id == w.id,
                Schedule.date >= date(2026, 1, 12)
            ).count() for w in workloads
        )
        print(f"\nTotal: {total} schedules")


if __name__ == "__main__":
    check_results()
