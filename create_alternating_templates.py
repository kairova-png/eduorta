#!/usr/bin/env python
"""Create alternating templates for multiple groups"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Group, Workload, AcademicYear, WorkloadTemplate
from datetime import date, timedelta

app = create_app()

# Kazakhstan holidays 2026
HOLIDAYS = {
    (2026, 1, 1), (2026, 1, 2), (2026, 3, 8),
    (2026, 3, 21), (2026, 3, 22), (2026, 3, 23),
    (2026, 5, 1), (2026, 5, 7), (2026, 5, 9),
    (2026, 7, 6), (2026, 8, 30),
}

def is_holiday(d):
    return (d.year, d.month, d.day) in HOLIDAYS

def get_week_start(week_num):
    """Get Monday of week number (week 1 = first week of Sept 2025)"""
    start = date(2025, 9, 1)
    while start.weekday() != 0:
        start += timedelta(days=1)
    return start + timedelta(weeks=(week_num - 1))

def create_template_for_group(group_name, base_prefs_full, base_prefs_short, full_week_first=True, target_hours=196):
    """
    Create alternating template.
    base_prefs_full: preferences for full week (6 pairs)
    base_prefs_short: preferences for short week (4 pairs)
    full_week_first: if True, week 20 is full, week 21 is short; if False, opposite
    """
    with app.app_context():
        current_year = AcademicYear.query.filter_by(is_current=True).first()

        # Find main group and subgroup
        main_group = Group.query.filter_by(name=group_name).first()
        sub_group = Group.query.filter_by(name=group_name + 'б').first()

        if not main_group:
            print(f"ERROR: Group {group_name} not found")
            return

        groups = [main_group]
        if sub_group:
            groups.append(sub_group)

        for group in groups:
            print(f"\n--- {group.name} ---")

            workload = Workload.query.filter(
                Workload.group_id == group.id,
                Workload.academic_year_id == current_year.id,
                Workload.semester == 2,
                Workload.discipline.ilike('%Английский%')
            ).first()

            if not workload:
                print(f"  No English workload found")
                continue

            print(f"  Workload ID: {workload.id}")

            # Build distribution
            distribution = []
            total_hours = 0
            week_num = 20

            while total_hours < target_hours and week_num <= 50:
                week_start = get_week_start(week_num)

                # Determine if this is a full or short week
                week_offset = week_num - 20
                if full_week_first:
                    is_full = (week_offset % 2 == 0)  # 20, 22, 24... are full
                else:
                    is_full = (week_offset % 2 == 1)  # 21, 23, 25... are full

                base_prefs = base_prefs_full if is_full else base_prefs_short

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
                    distribution.append({
                        "week": week_num,
                        "preferences": preferences
                    })
                    total_hours += week_hours
                    week_type = "6 пар" if is_full else "4 пары"
                    print(f"  Week {week_num}: {week_hours}h ({week_type}) -> Total: {total_hours}h")

                week_num += 1

            print(f"  Final: {total_hours} hours")

            # Save template
            template = WorkloadTemplate.query.filter_by(workload_id=workload.id).first()
            if template:
                template.distribution_json = json.dumps(distribution)
                template.name = f"Английский язык - чередующийся"
            else:
                template = WorkloadTemplate(
                    workload_id=workload.id,
                    name=f"Английский язык - чередующийся",
                    distribution_json=json.dumps(distribution)
                )
                db.session.add(template)

            db.session.commit()
            print(f"  Template saved!")


def main():
    print("=" * 60)
    print("CREATING ALTERNATING TEMPLATES")
    print("=" * 60)

    # АиУ 5-25: Tue 1-2, Thu 3-4, Fri 3-4 (full) / Tue 1-2, Thu 3-4 (short)
    # Пятница мигает
    print("\n### АиУ 5-25 ###")
    create_template_for_group(
        'АиУ 5-25',
        base_prefs_full={1: [1, 2], 3: [3, 4], 4: [3, 4]},  # Tue, Thu, Fri
        base_prefs_short={1: [1, 2], 3: [3, 4]},  # Tue, Thu only
        full_week_first=True
    )

    # ПО 1-25: Mon 3-4, Tue 1-2, Thu 1-2 (full) / Tue 1-2, Thu 1-2 (short)
    # Понедельник мигает
    print("\n### ПО 1-25 ###")
    create_template_for_group(
        'ПО 1-25',
        base_prefs_full={0: [3, 4], 1: [1, 2], 3: [1, 2]},  # Mon, Tue, Thu
        base_prefs_short={1: [1, 2], 3: [1, 2]},  # Tue, Thu only
        full_week_first=True
    )

    # ПО 2-25: Tue 3-4, Thu 3-4, Fri 1-2 (full) / Tue 3-4, Thu 3-4 (short)
    # Пятница мигает
    print("\n### ПО 2-25 ###")
    create_template_for_group(
        'ПО 2-25',
        base_prefs_full={1: [3, 4], 3: [3, 4], 4: [1, 2]},  # Tue, Thu, Fri
        base_prefs_short={1: [3, 4], 3: [3, 4]},  # Tue, Thu only
        full_week_first=True
    )

    # ТДНГ 1-25: Wed 3-4, Fri 3-4 (short) / Mon 3-4, Wed 3-4, Fri 3-4 (full)
    # Понедельник мигает ОБРАТНО (сначала 4 пары, потом 6)
    print("\n### ТДНГ 1-25 ###")
    create_template_for_group(
        'ТДНГ 1-25',
        base_prefs_full={0: [3, 4], 2: [3, 4], 4: [3, 4]},  # Mon, Wed, Fri
        base_prefs_short={2: [3, 4], 4: [3, 4]},  # Wed, Fri only
        full_week_first=False  # Week 20 is SHORT, Week 21 is FULL
    )

    print("\n" + "=" * 60)
    print("ALL TEMPLATES CREATED!")


if __name__ == "__main__":
    main()
