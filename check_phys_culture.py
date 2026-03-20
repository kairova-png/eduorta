#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
from app import create_app, db
from app.models import Schedule, Workload, Group, GUP

app = create_app()

with app.app_context():
    group_id = 17  # BNGS 1-25

    # Check week 20 dates
    gup = GUP.query.filter_by(group_id=group_id, week_number=20, academic_year_id=1).first()
    print(f"Week 20: {gup.start_date} - {gup.end_date}")

    print("\n=== Checking slots for Physical Culture template ===")
    print("Template says: Week 20: Day 3 (Thursday), Pair 1")

    # Week 20: Thursday (day 3) = start_date + 3 days
    thu_week20 = gup.start_date + timedelta(days=3)
    print(f"\nWeek 20, Thursday (day 3): {thu_week20}")

    # Check what's on Thursday Week 20, Pair 1
    existing = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date == thu_week20,
        Schedule.pair_number == 1
    ).first()

    if existing:
        print(f"  Pair 1 OCCUPIED by: {existing.workload.discipline}")
    else:
        print(f"  Pair 1 is FREE")

    # Check all pairs on that day
    day_schedules = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date == thu_week20
    ).order_by(Schedule.pair_number).all()

    print(f"\n  All pairs on {thu_week20}:")
    for s in day_schedules:
        print(f"    Pair {s.pair_number}: {s.workload.discipline}")

    # Week 21
    gup21 = GUP.query.filter_by(group_id=group_id, week_number=21, academic_year_id=1).first()
    if gup21:
        print(f"\n\nWeek 21: {gup21.start_date} - {gup21.end_date}")
        print("Template says: Week 21: Day 0 (Monday), Pair 3 + Day 3 (Thursday), Pair 1")

        mon_week21 = gup21.start_date  # Monday
        thu_week21 = gup21.start_date + timedelta(days=3)  # Thursday

        print(f"\nWeek 21, Monday (day 0): {mon_week21}")
        # Check Monday pair 3
        existing_mon = Schedule.query.join(Workload).filter(
            Workload.group_id == group_id,
            Schedule.date == mon_week21,
            Schedule.pair_number == 3
        ).first()
        if existing_mon:
            print(f"  Pair 3 OCCUPIED by: {existing_mon.workload.discipline}")
        else:
            print(f"  Pair 3 is FREE")

        # All Monday pairs
        mon_schedules = Schedule.query.join(Workload).filter(
            Workload.group_id == group_id,
            Schedule.date == mon_week21
        ).order_by(Schedule.pair_number).all()
        print(f"  All Monday pairs:")
        if mon_schedules:
            for s in mon_schedules:
                print(f"    Pair {s.pair_number}: {s.workload.discipline}")
        else:
            print("    No classes scheduled!")

        print(f"\nWeek 21, Thursday (day 3): {thu_week21}")
        # Check Thursday pair 1
        existing_thu = Schedule.query.join(Workload).filter(
            Workload.group_id == group_id,
            Schedule.date == thu_week21,
            Schedule.pair_number == 1
        ).first()
        if existing_thu:
            print(f"  Pair 1 OCCUPIED by: {existing_thu.workload.discipline}")
        else:
            print(f"  Pair 1 is FREE")
