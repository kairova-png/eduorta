#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Show detailed teacher conflicts
"""

import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
from app import create_app, db
from app.models import Schedule, Workload, Group, Teacher, Room
from collections import defaultdict

app = create_app()

DAY_NAMES = {
    0: 'Понедельник',
    1: 'Вторник',
    2: 'Среда',
    3: 'Четверг',
    4: 'Пятница',
    5: 'Суббота',
    6: 'Воскресенье'
}

ACADEMIC_YEAR_START = date(2025, 9, 1)

def get_week_type(d):
    days_since_monday = ACADEMIC_YEAR_START.weekday()
    week_start = ACADEMIC_YEAR_START - timedelta(days=days_since_monday)
    days_diff = (d - week_start).days
    week_num = (days_diff // 7) + 1
    return 'ПРАВАЯ' if week_num % 2 == 0 else 'ЛЕВАЯ'

def find_teacher_conflicts():
    with app.app_context():
        start_date = date(2026, 1, 12)
        end_date = date(2026, 6, 30)

        # Get all schedules
        schedules = Schedule.query.filter(
            Schedule.date >= start_date,
            Schedule.date <= end_date,
            Schedule.status.in_(['planned', 'done', 'completed', 'substitution'])
        ).all()

        # Group by teacher, date, pair
        teacher_slots = defaultdict(list)

        for s in schedules:
            if s.workload and s.workload.teacher:
                key = (s.workload.teacher_id, s.date, s.pair_number)
                teacher_slots[key].append(s)

        # Find conflicts
        conflicts = []
        for key, slot_schedules in teacher_slots.items():
            if len(slot_schedules) > 1:
                teacher_id, d, pair = key
                teacher = Teacher.query.get(teacher_id)

                groups = []
                for s in slot_schedules:
                    group_name = s.workload.group.name if s.workload.group else 'N/A'
                    discipline = s.workload.discipline if s.workload else 'N/A'
                    room = s.room.number if s.room else 'N/A'
                    groups.append({
                        'group': group_name,
                        'discipline': discipline,
                        'room': room,
                        'schedule_id': s.id
                    })

                conflicts.append({
                    'teacher': teacher.full_name if teacher else 'N/A',
                    'teacher_id': teacher_id,
                    'date': d,
                    'pair': pair,
                    'day_name': DAY_NAMES[d.weekday()],
                    'week_type': get_week_type(d),
                    'groups': groups
                })

        return conflicts

def main():
    print("=" * 80)
    print("ДЕТАЛЬНЫЕ КОНФЛИКТЫ ПО ПРЕПОДАВАТЕЛЯМ")
    print("=" * 80)

    conflicts = find_teacher_conflicts()

    # Group by teacher
    by_teacher = defaultdict(list)
    for c in conflicts:
        by_teacher[c['teacher']].append(c)

    print(f"\nВсего конфликтов: {len(conflicts)}")
    print(f"Преподавателей с конфликтами: {len(by_teacher)}")

    # Sort by number of conflicts
    sorted_teachers = sorted(by_teacher.items(), key=lambda x: len(x[1]), reverse=True)

    for teacher_name, teacher_conflicts in sorted_teachers:
        print("\n" + "=" * 80)
        print(f"ПРЕПОДАВАТЕЛЬ: {teacher_name}")
        print(f"Количество конфликтов: {len(teacher_conflicts)}")
        print("=" * 80)

        # Group by pattern (day + pair + week_type)
        patterns = defaultdict(list)
        for c in teacher_conflicts:
            pattern_key = (c['day_name'], c['pair'], c['week_type'])
            patterns[pattern_key].append(c)

        for (day, pair, week_type), pattern_conflicts in patterns.items():
            print(f"\n  {day}, Пара {pair}, {week_type} неделя:")

            # Get unique groups
            all_groups = set()
            for c in pattern_conflicts:
                for g in c['groups']:
                    all_groups.add((g['group'], g['discipline'][:40], g['room']))

            print(f"    Конфликтующие группы:")
            for group, disc, room in sorted(all_groups):
                print(f"      - {group}: {disc}... (ауд. {room})")

            # Show sample dates
            sample_dates = sorted(set(c['date'] for c in pattern_conflicts))[:3]
            print(f"    Пример дат: {', '.join(d.strftime('%d.%m.%Y') for d in sample_dates)}")

if __name__ == '__main__':
    main()
