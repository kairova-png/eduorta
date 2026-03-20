#!/usr/bin/env python
"""Create alternating template for АиУ 4-25 and АиУ 4-25б"""

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
    (2026, 1, 1): "Новый год",
    (2026, 1, 2): "Новый год",
    (2026, 3, 8): "Международный женский день",
    (2026, 3, 21): "Наурыз",
    (2026, 3, 22): "Наурыз",
    (2026, 3, 23): "Наурыз",
    (2026, 5, 1): "День единства",
    (2026, 5, 7): "День защитника",
    (2026, 5, 9): "День Победы",
    (2026, 7, 6): "День столицы",
    (2026, 8, 30): "День Конституции",
}

def is_holiday(d):
    return (d.year, d.month, d.day) in HOLIDAYS

def create_template():
    with app.app_context():
        print("=" * 60)
        print("CREATING ALTERNATING TEMPLATE FOR АиУ 4-25")
        print("=" * 60)

        current_year = AcademicYear.query.filter_by(is_current=True).first()

        group1 = Group.query.filter_by(name='АиУ 4-25').first()
        group2 = Group.query.filter_by(name='АиУ 4-25б').first()

        if not group1:
            print("ERROR: Group not found!")
            return

        print(f"Group: {group1.name} (ID: {group1.id})")
        if group2:
            print(f"Subgroup: {group2.name} (ID: {group2.id})")

        semester = 2
        group_ids = [group1.id]
        if group2:
            group_ids.append(group2.id)

        workloads = Workload.query.filter(
            Workload.group_id.in_(group_ids),
            Workload.academic_year_id == current_year.id,
            Workload.semester == semester,
            Workload.discipline.ilike('%Английский%')
        ).all()

        print(f"\nEnglish workloads: {len(workloads)}")
        for w in workloads:
            print(f"  - {w.group.name}: {w.discipline}")

        if not workloads:
            print("ERROR: No workloads found!")
            return

        target_hours = 196

        for w in workloads:
            print(f"\n--- Creating template for {w.group.name} ---")

            # Build week-by-week schedule
            # Format expected by smart_scheduler:
            # [{"week": 20, "preferences": {"1": {"3": "left", "4": "left"}, ...}}, ...]

            distribution = []
            total_hours = 0
            week_num = 20
            start_date = date(2026, 1, 12)

            while total_hours < target_hours and week_num <= 50:
                # Find Monday of this week
                week_start = start_date + timedelta(weeks=(week_num - 20))
                while week_start.weekday() != 0:
                    week_start -= timedelta(days=1)

                # Week pattern: even = 6 pairs, odd = 4 pairs
                is_full_week = (week_num % 2 == 0)

                preferences = {}
                week_hours = 0

                # Tuesday (day 1) - pairs 3, 4
                tuesday = week_start + timedelta(days=1)
                if not is_holiday(tuesday):
                    day_prefs = {}
                    if total_hours + week_hours + 2 <= target_hours:
                        day_prefs["3"] = "left"
                        week_hours += 2
                    if total_hours + week_hours + 2 <= target_hours:
                        day_prefs["4"] = "left"
                        week_hours += 2
                    if day_prefs:
                        preferences["1"] = day_prefs

                # Thursday (day 3) - pairs 1, 2
                thursday = week_start + timedelta(days=3)
                if not is_holiday(thursday):
                    day_prefs = {}
                    if total_hours + week_hours + 2 <= target_hours:
                        day_prefs["1"] = "left"
                        week_hours += 2
                    if total_hours + week_hours + 2 <= target_hours:
                        day_prefs["2"] = "left"
                        week_hours += 2
                    if day_prefs:
                        preferences["3"] = day_prefs

                # Friday (day 4) - pairs 1, 2 (only full weeks)
                if is_full_week:
                    friday = week_start + timedelta(days=4)
                    if not is_holiday(friday):
                        day_prefs = {}
                        if total_hours + week_hours + 2 <= target_hours:
                            day_prefs["1"] = "left"
                            week_hours += 2
                        if total_hours + week_hours + 2 <= target_hours:
                            day_prefs["2"] = "left"
                            week_hours += 2
                        if day_prefs:
                            preferences["4"] = day_prefs

                if preferences and week_hours > 0:
                    distribution.append({
                        "week": week_num,
                        "preferences": preferences
                    })
                    total_hours += week_hours
                    week_type = "6 пар" if is_full_week else "4 пары"
                    print(f"  Week {week_num}: {week_hours}h ({week_type}) -> Total: {total_hours}h")

                week_num += 1

            print(f"  Final total: {total_hours} hours")

            # Save template
            template = WorkloadTemplate.query.filter_by(workload_id=w.id).first()

            if template:
                template.distribution_json = json.dumps(distribution)
                template.name = "Английский язык - чередующийся (6/4 пары)"
                print(f"  Updated template ID {template.id}")
            else:
                template = WorkloadTemplate(
                    workload_id=w.id,
                    name="Английский язык - чередующийся (6/4 пары)",
                    distribution_json=json.dumps(distribution)
                )
                db.session.add(template)
                print(f"  Created new template")

            db.session.commit()

        print("\n" + "=" * 60)
        print("DONE!")


if __name__ == "__main__":
    create_template()
