#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
from app import create_app, db
from app.models import Schedule, Workload, Group, GUP, Room, Teacher

app = create_app()

with app.app_context():
    group_id = 17  # BNGS 1-25

    # Get Physical Culture workload
    phys_workload = Workload.query.filter_by(group_id=group_id, id=3).first()
    print(f"Physical Culture workload ID: {phys_workload.id}")
    print(f"Teacher: {phys_workload.teacher.full_name if phys_workload.teacher else 'None'}")
    print(f"Teacher ID: {phys_workload.teacher_id}")

    # Check Monday 19.01.2026, Pair 3
    check_date = date(2026, 1, 19)
    check_pair = 3

    print(f"\n=== Checking why pair not placed on {check_date}, pair {check_pair} ===")

    # 1. Check if group slot is free
    group_conflict = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date == check_date,
        Schedule.pair_number == check_pair
    ).first()

    if group_conflict:
        print(f"GROUP CONFLICT: Slot occupied by {group_conflict.workload.discipline}")
    else:
        print("GROUP: Slot is FREE")

    # 2. Check if teacher is free
    teacher_conflict = Schedule.query.join(Workload).filter(
        Workload.teacher_id == phys_workload.teacher_id,
        Schedule.date == check_date,
        Schedule.pair_number == check_pair
    ).first()

    if teacher_conflict:
        print(f"TEACHER CONFLICT: {phys_workload.teacher.full_name} is busy with {teacher_conflict.workload.discipline} for group {teacher_conflict.workload.group.name}")
    else:
        print(f"TEACHER: {phys_workload.teacher.full_name} is FREE")

    # 3. Check available rooms
    occupied_rooms = Schedule.query.filter(
        Schedule.date == check_date,
        Schedule.pair_number == check_pair,
        Schedule.room_id.isnot(None)
    ).all()

    occupied_room_ids = [s.room_id for s in occupied_rooms]
    all_rooms = Room.query.all()
    available_rooms = [r for r in all_rooms if r.id not in occupied_room_ids]

    print(f"\nROOMS: {len(occupied_rooms)} occupied, {len(available_rooms)} available")
    if available_rooms:
        print(f"Available rooms: {', '.join([r.number for r in available_rooms[:10]])}...")
    else:
        print("NO ROOMS AVAILABLE!")

    # 4. Show what teacher is doing on Monday 19.01
    print(f"\n=== Teacher {phys_workload.teacher.full_name} schedule on {check_date} ===")
    teacher_day = Schedule.query.join(Workload).filter(
        Workload.teacher_id == phys_workload.teacher_id,
        Schedule.date == check_date
    ).order_by(Schedule.pair_number).all()

    if teacher_day:
        for s in teacher_day:
            print(f"  Pair {s.pair_number}: {s.workload.discipline} - {s.workload.group.name}")
    else:
        print("  No classes!")
