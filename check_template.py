#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check template for Physical Culture"""

import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from app import create_app, db
from app.models import Schedule, Workload, Group, WorkloadTemplate
import json

app = create_app()

with app.app_context():
    group_id = 17  # BNGS 1-25
    group = db.session.get(Group, group_id)
    print(f"Group: {group.name}")

    # Find Physical Culture workload
    workloads = Workload.query.filter_by(group_id=group_id).all()
    print(f"\nAll workloads for group {group.name}:")
    for wl in workloads:
        print(f"  ID={wl.id}: {wl.discipline} (sem {wl.semester})")

    # Find templates for this group
    print(f"\n=== Templates for group {group.name} ===")
    templates = WorkloadTemplate.query.filter_by(group_id=group_id).all()
    for t in templates:
        wl = db.session.get(Workload, t.workload_id)
        print(f"\nTemplate ID={t.id}: {t.name}")
        print(f"  Workload: {wl.discipline if wl else 'N/A'}")
        print(f"  Semester: {t.semester}")
        print(f"  Distribution: {t.distribution_json[:200] if t.distribution_json else 'None'}...")

        # Parse distribution
        try:
            dist = json.loads(t.distribution_json) if t.distribution_json else []
            for week_data in dist[:3]:  # Show first 3 weeks
                week = week_data.get('week')
                prefs = week_data.get('preferences', {})
                print(f"  Week {week}: preferences={prefs}")
        except:
            pass

    # Check existing schedule for Jan 20-24
    print(f"\n=== Schedule for Jan 20-24, 2026 (Week 21) ===")
    schedules = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date >= date(2026, 1, 20),
        Schedule.date <= date(2026, 1, 24)
    ).order_by(Schedule.date, Schedule.pair_number).all()

    current_date = None
    for s in schedules:
        if s.date != current_date:
            current_date = s.date
            day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][s.date.weekday()]
            print(f"\n{day_name} {s.date}:")
        discipline = s.workload.discipline if s.workload else 'N/A'
        print(f"  Para {s.pair_number}: {discipline}")
