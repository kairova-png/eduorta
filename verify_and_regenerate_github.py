#!/usr/bin/env python
"""Verify Вакант schedules and regenerate GitHub Pages package"""

import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Teacher, Workload, Schedule, Group

app = create_app()

def verify_vacant():
    with app.app_context():
        print("=" * 80)
        print("VERIFYING VACANT TEACHER DATA")
        print("=" * 80)

        # Find Vacant teacher
        vacant = Teacher.query.filter(Teacher.full_name.ilike('%Вакант%')).first()

        if not vacant:
            print("ERROR: Vacant teacher not found in database!")
            return False

        print(f"\nVacant teacher found: ID={vacant.id}, Name='{vacant.full_name}'")

        # Get workloads
        workloads = Workload.query.filter_by(teacher_id=vacant.id).all()
        print(f"\nVacant workloads: {len(workloads)}")

        for w in workloads:
            print(f"  - {w.discipline} | Group: {w.group.name}")

        # Get schedules
        workload_ids = [w.id for w in workloads]
        schedules = Schedule.query.filter(Schedule.workload_id.in_(workload_ids)).all() if workload_ids else []
        print(f"\nVacant schedules: {len(schedules)}")

        for s in schedules:
            print(f"  - {s.date} pair {s.pair_number}: {s.workload.discipline} | {s.workload.group.name}")

        return len(schedules) > 0


def regenerate_github_package():
    with app.app_context():
        print("\n" + "=" * 80)
        print("REGENERATING GITHUB PAGES PACKAGE")
        print("=" * 80)

        from app.services.google_sites_service import GoogleSitesService

        # Calculate week 20 period
        week_20_monday = date(2026, 1, 12)
        week_20_sunday = week_20_monday + timedelta(days=6)

        print(f"\nPeriod: {week_20_monday} - {week_20_sunday}")

        service = GoogleSitesService()
        result = service.generate_github_pages_package(week_20_monday, week_20_sunday)

        if result['success']:
            print("\nSUCCESS! GitHub Pages package generated")
            print(f"Files created in: exports/github_pages/")

            # Verify Vacant in JSON
            import json
            schedule_json_path = 'exports/github_pages/docs/api/schedule.json'
            if os.path.exists(schedule_json_path):
                with open(schedule_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                vacant_schedules = [s for s in data.get('schedules', [])
                                   if s.get('teacher') and 'Вакант' in s['teacher'].get('name', '')]
                print(f"\nVacant schedules in JSON: {len(vacant_schedules)}")

                for s in vacant_schedules:
                    print(f"  - {s['date']} pair {s['pair_number']}: {s['discipline']} | {s['group']['name']}")

            return True
        else:
            print(f"\nERROR: {result.get('error', 'Unknown error')}")
            return False


if __name__ == "__main__":
    has_data = verify_vacant()

    if has_data:
        regenerate_github_package()
    else:
        print("\nNo Vacant schedules found. Please run create_schedule_week20.py first.")
