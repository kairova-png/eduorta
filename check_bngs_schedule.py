#!/usr/bin/env python
"""Check schedule for BNGS 1-25 group"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from app import create_app, db
from app.models import Schedule, Workload, Group

app = create_app()

with app.app_context():
    # Find BNGS 1-25 group
    group = Group.query.filter(Group.name.like('%BNGS%') | Group.name.like('%1-25%')).all()
    print("Groups found:")
    for g in group:
        print(f"  ID={g.id}: {g.name}")

    # Get group 17 (BNGS 1-25)
    group_id = 17
    group = Group.query.get(group_id)
    print(f"\nChecking group: {group.name} (ID: {group_id})")

    # Check what's scheduled for January 2026
    schedules = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date >= date(2026, 1, 12),
        Schedule.date <= date(2026, 1, 31)
    ).order_by(Schedule.date, Schedule.pair_number).all()

    print(f"\nFound {len(schedules)} schedule entries for Jan 12-31, 2026:")

    current_date = None
    for s in schedules:
        if s.date != current_date:
            current_date = s.date
            day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][s.date.weekday()]
            print(f"\n{day_name} {s.date}:")

        discipline = s.workload.discipline if s.workload else 'N/A'
        teacher = s.workload.teacher.full_name if s.workload and s.workload.teacher else 'N/A'
        room = s.room.number if s.room else 'N/A'
        status = s.status or 'planned'
        print(f"  Para {s.pair_number}: {discipline[:40]} | {teacher[:20]} | Room: {room} | Status: {status}")

    # Check workload for Physical Culture
    print("\n\n=== Physical Culture workload ===")
    phys_workloads = Workload.query.filter(
        Workload.group_id == group_id,
        Workload.discipline.like('%'+'ultur'+'%')  # Physical culture
    ).all()

    for wl in phys_workloads:
        print(f"ID={wl.id}: {wl.discipline}")
        print(f"  Teacher: {wl.teacher.full_name if wl.teacher else 'N/A'}")
        print(f"  Hours: {wl.total_hours}, Completed: {wl.hours_completed}")
        print(f"  Semester: {wl.semester}")
