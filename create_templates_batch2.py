#!/usr/bin/env python
"""Create alternating templates for batch 2 groups"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Group, Workload, AcademicYear, WorkloadTemplate, Schedule
from app.services.smart_scheduler import SmartScheduleGenerator
from datetime import date, timedelta

app = create_app()

HOLIDAYS = {
    (2026, 1, 1), (2026, 1, 2), (2026, 3, 8),
    (2026, 3, 21), (2026, 3, 22), (2026, 3, 23),
    (2026, 5, 1), (2026, 5, 7), (2026, 5, 9),
    (2026, 7, 6), (2026, 8, 30),
}

def is_holiday(d):
    return (d.year, d.month, d.day) in HOLIDAYS

def get_week_start(week_num):
    start = date(2025, 9, 1)
    while start.weekday() != 0:
        start += timedelta(days=1)
    return start + timedelta(weeks=(week_num - 1))

# Group configurations
# Format: (group_name, full_prefs, short_prefs, full_week_first)
GROUPS_CONFIG = [
    # ХТП 1-25: Wed 3-4, Fri 3-4 (short) / +Mon 3-4 (full). Mon alternating, starts short
    ('ХТП 1-25',
     {0: [3, 4], 2: [3, 4], 4: [3, 4]},  # full: Mon, Wed, Fri
     {2: [3, 4], 4: [3, 4]},  # short: Wed, Fri
     False),  # Week 20 is short

    # ХТП 2-25: Tue 3-4, Thu 3-4, Fri 1-2 (full) / no Fri (short). Fri alternating, starts full
    ('ХТП 2-25',
     {1: [3, 4], 3: [3, 4], 4: [1, 2]},  # full: Tue, Thu, Fri
     {1: [3, 4], 3: [3, 4]},  # short: Tue, Thu
     True),  # Week 20 is full

    # ХТП 3-25: Tue 1-2, Thu 1-2 (short) / +Mon 1-2 (full). Mon alternating, starts short
    ('ХТП 3-25',
     {0: [1, 2], 1: [1, 2], 3: [1, 2]},  # full: Mon, Tue, Thu
     {1: [1, 2], 3: [1, 2]},  # short: Tue, Thu
     False),  # Week 20 is short

    # ЭНГМ 1-25: Mon 1-2, Tue 1-2, Thu 3-4 (full) / no Mon (short). Mon alternating, starts full
    ('ЭНГМ 1-25',
     {0: [1, 2], 1: [1, 2], 3: [3, 4]},  # full: Mon, Tue, Thu
     {1: [1, 2], 3: [3, 4]},  # short: Tue, Thu
     True),  # Week 20 is full

    # ЭС 1-25: Tue 3-4, Thu 1-2 (short) / +Mon 3-4 (full). Mon alternating, starts short
    ('ЭС 1-25',
     {0: [3, 4], 1: [3, 4], 3: [1, 2]},  # full: Mon, Tue, Thu
     {1: [3, 4], 3: [1, 2]},  # short: Tue, Thu
     False),  # Week 20 is short

    # ЭС 2-25: Mon 3-4, Wed 3-4 (short) / +Fri 3-4 (full). Fri alternating, starts short
    ('ЭС 2-25',
     {0: [3, 4], 2: [3, 4], 4: [3, 4]},  # full: Mon, Wed, Fri
     {0: [3, 4], 2: [3, 4]},  # short: Mon, Wed
     False),  # Week 20 is short

    # ЭС 3-25: Wed 1-2, Fri 3-4 (short) / +Mon 1-2 (full). Mon alternating, starts short
    ('ЭС 3-25',
     {0: [1, 2], 2: [1, 2], 4: [3, 4]},  # full: Mon, Wed, Fri
     {2: [1, 2], 4: [3, 4]},  # short: Wed, Fri
     False),  # Week 20 is short
]

def create_template(group_name, full_prefs, short_prefs, full_week_first, target_hours=196):
    current_year = AcademicYear.query.filter_by(is_current=True).first()

    main_group = Group.query.filter_by(name=group_name).first()
    sub_group = Group.query.filter_by(name=group_name + 'б').first()

    if not main_group:
        print(f"  {group_name}: NOT FOUND")
        return

    groups = [main_group]
    if sub_group:
        groups.append(sub_group)

    for group in groups:
        workload = Workload.query.filter(
            Workload.group_id == group.id,
            Workload.academic_year_id == current_year.id,
            Workload.semester == 2,
            Workload.discipline.ilike('%Английский%')
        ).first()

        if not workload:
            print(f"  {group.name}: No English workload")
            continue

        distribution = []
        total_hours = 0
        week_num = 20

        while total_hours < target_hours and week_num <= 50:
            week_start = get_week_start(week_num)
            week_offset = week_num - 20

            if full_week_first:
                is_full = (week_offset % 2 == 0)
            else:
                is_full = (week_offset % 2 == 1)

            base_prefs = full_prefs if is_full else short_prefs
            preferences = {}
            week_hours = 0

            for day_idx, pairs in base_prefs.items():
                day_date = week_start + timedelta(days=day_idx)
                if is_holiday(day_date):
                    continue

                day_prefs = {}
                for pair in pairs:
                    if total_hours + week_hours + 2 <= target_hours:
                        day_prefs[str(pair)] = "selected"
                        week_hours += 2

                if day_prefs:
                    preferences[str(day_idx)] = day_prefs

            if preferences and week_hours > 0:
                distribution.append({"week": week_num, "preferences": preferences})
                total_hours += week_hours

            week_num += 1

        template = WorkloadTemplate.query.filter_by(workload_id=workload.id).first()
        if template:
            template.distribution_json = json.dumps(distribution)
            template.name = "Английский язык - чередующийся"
        else:
            template = WorkloadTemplate(
                workload_id=workload.id,
                name="Английский язык - чередующийся",
                distribution_json=json.dumps(distribution)
            )
            db.session.add(template)

        db.session.commit()
        print(f"  {group.name}: {total_hours} hours template saved")


def generate_schedules(group_name):
    current_year = AcademicYear.query.filter_by(is_current=True).first()

    main_group = Group.query.filter_by(name=group_name).first()
    sub_group = Group.query.filter_by(name=group_name + 'б').first()

    if not main_group:
        return 0

    groups = [main_group]
    if sub_group:
        groups.append(sub_group)

    total = 0
    for group in groups:
        workload = Workload.query.filter(
            Workload.group_id == group.id,
            Workload.academic_year_id == current_year.id,
            Workload.semester == 2,
            Workload.discipline.ilike('%Английский%')
        ).first()

        if not workload:
            continue

        # Delete existing
        Schedule.query.filter(
            Schedule.workload_id == workload.id,
            Schedule.date >= date(2026, 1, 12)
        ).delete()
        db.session.commit()

        try:
            generator = SmartScheduleGenerator(
                group_id=group.id,
                semester=2,
                academic_year_id=current_year.id,
                workload_ids=[workload.id]
            )

            if generator.generate() and generator.created_schedules:
                if generator.save_results():
                    count = len(generator.created_schedules)
                    total += count
                    print(f"  {group.name}: {count} pairs ({count*2} hours)")
        except Exception as e:
            print(f"  {group.name}: ERROR - {e}")

    return total


def main():
    with app.app_context():
        print("=" * 60)
        print("CREATING TEMPLATES")
        print("=" * 60)

        for config in GROUPS_CONFIG:
            group_name, full_prefs, short_prefs, full_week_first = config
            print(f"\n{group_name}:")
            create_template(group_name, full_prefs, short_prefs, full_week_first)

        print("\n" + "=" * 60)
        print("GENERATING SCHEDULES")
        print("=" * 60)

        grand_total = 0
        for config in GROUPS_CONFIG:
            group_name = config[0]
            print(f"\n{group_name}:")
            grand_total += generate_schedules(group_name)

        print("\n" + "=" * 60)
        print(f"TOTAL: {grand_total} schedules")


if __name__ == "__main__":
    main()
