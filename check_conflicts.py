#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check for real schedule conflicts"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Schedule, Workload, Teacher, Room, Group
from datetime import date
from collections import defaultdict

app = create_app()

def check_conflicts():
    with app.app_context():
        print("=" * 60)
        print("CHECKING FOR REAL CONFLICTS")
        print("=" * 60)

        schedules = Schedule.query.join(Workload).filter(
            Schedule.date >= date(2026, 1, 12)
        ).all()

        print(f"Total schedules to check: {len(schedules)}")

        # 1. Teacher conflicts (same teacher, different base groups, same time)
        print("\n--- TEACHER CONFLICTS ---")

        teacher_slots = defaultdict(list)
        for s in schedules:
            if s.workload and s.workload.teacher:
                key = (s.date, s.pair_number, s.workload.teacher_id)
                teacher_slots[key].append(s)

        teacher_conflicts = []
        for key, entries in teacher_slots.items():
            if len(entries) > 1:
                base_groups = set()
                for e in entries:
                    base_name = e.workload.group.name.rstrip('б')
                    base_groups.add(base_name)

                if len(base_groups) > 1:
                    teacher_conflicts.append((key, entries))

        if teacher_conflicts:
            for key, entries in teacher_conflicts[:10]:
                date_str, pair, teacher_id = key
                teacher = entries[0].workload.teacher.full_name
                print(f"  {date_str} pair {pair}: {teacher}")
                for e in entries:
                    print(f"    - {e.workload.group.name}: {e.workload.discipline}")
            print(f"  Total: {len(teacher_conflicts)}")
        else:
            print("  No teacher conflicts!")

        # 2. Room conflicts (exclude gym - room С/c/спортзал)
        print("\n--- ROOM CONFLICTS (excluding gym) ---")

        room_slots = defaultdict(list)
        for s in schedules:
            if s.room:
                room_num = s.room.number.lower().strip()
                # Skip gym
                if room_num in ['с', 'c', 'спортзал', 'gym', 'сп']:
                    continue
                key = (s.date, s.pair_number, s.room_id)
                room_slots[key].append(s)

        room_conflicts = []
        for key, entries in room_slots.items():
            if len(entries) > 1:
                base_groups = set()
                for e in entries:
                    base_name = e.workload.group.name.rstrip('б')
                    base_groups.add(base_name)

                # Real conflict if different base groups
                if len(base_groups) > 1:
                    room_conflicts.append((key, entries))

        if room_conflicts:
            for key, entries in room_conflicts[:10]:
                date_str, pair, room_id = key
                room = entries[0].room.number
                print(f"  {date_str} pair {pair}: room {room}")
                for e in entries:
                    print(f"    - {e.workload.group.name}: {e.workload.discipline}")
            if len(room_conflicts) > 10:
                print(f"  ... and {len(room_conflicts) - 10} more")
            print(f"  Total: {len(room_conflicts)}")
        else:
            print("  No room conflicts!")

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Teacher conflicts: {len(teacher_conflicts)}")
        print(f"Room conflicts: {len(room_conflicts)}")


if __name__ == "__main__":
    check_conflicts()
