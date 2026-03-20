#!/usr/bin/env python
"""Create templates for workloads that don't have templates yet"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Workload, WorkloadTemplate, GUP, AcademicYear, Group

app = create_app()

# Hours per discipline
DISCIPLINE_HOURS = {
    'Казахская литература': 72,
    'Казахский литература': 72,
    'Русский язык и литература': 48,
    'Английский язык': 196,
    'Всемирная история': 24,
    'Всемирная История': 24,
    'Математика': 88,
    'Информатика': 72,
    'Физика': 64,
    'Химия': 60,
    'География': 24,
    'Начальная военная и технологическая подготовка': 64,
    'Физическая культура': 56,
    'Глобальные компетенции': 24,
}


def get_week_type(week_number):
    """Get week type: left (even) or right (odd)"""
    return 'left' if week_number % 2 == 0 else 'right'


def create_template_for_workload(workload, academic_year, week_type='all'):
    """Create template for workload"""
    # Get GUP weeks for this group
    gup_weeks = GUP.query.filter_by(
        group_id=workload.group_id,
        academic_year_id=academic_year.id
    ).filter(GUP.week_number >= 20).order_by(GUP.week_number).all()

    if not gup_weeks:
        return None

    # Filter weeks based on type
    target_weeks = []
    for gup in gup_weeks:
        if not gup.needs_schedule:
            continue

        gup_week_type = get_week_type(gup.week_number)

        if week_type == 'all':
            target_weeks.append(gup)
        elif week_type == 'left' and gup_week_type == 'left':
            target_weeks.append(gup)
        elif week_type == 'right' and gup_week_type == 'right':
            target_weeks.append(gup)

    if not target_weeks:
        return None

    # Calculate pairs per week
    total_hours = workload.total_hours
    total_pairs = total_hours // 2
    pairs_per_week = max(1, total_pairs // len(target_weeks))
    extra_pairs = total_pairs % len(target_weeks)

    # Build weeks data
    weeks_data = []
    for i, gup in enumerate(target_weeks):
        pairs_this_week = pairs_per_week + (1 if i < extra_pairs else 0)

        if pairs_this_week <= 0:
            continue

        preferences = {}
        pairs_assigned = 0

        for day in range(5):
            if pairs_assigned >= pairs_this_week:
                break

            preferences[str(day)] = {}
            pairs_today = min(2, pairs_this_week - pairs_assigned)

            for pair in range(1, pairs_today + 1):
                preferences[str(day)][str(pair)] = 'selected'
                pairs_assigned += 1

        weeks_data.append({
            'week': gup.week_number,
            'preferences': preferences
        })

    # Create template
    template_name = f"{workload.discipline} - {workload.group.name}"
    if week_type == 'left':
        template_name += " (Левые недели)"
    elif week_type == 'right':
        template_name += " (Правые недели)"

    template = WorkloadTemplate(
        name=template_name,
        workload_id=workload.id,
        group_id=workload.group_id,
        academic_year_id=academic_year.id,
        semester=2,
        total_hours=workload.total_hours,
        distribution_json=json.dumps(weeks_data),
        created_by='script'
    )
    db.session.add(template)
    return template


def create_missing_templates():
    with app.app_context():
        print("=" * 80)
        print("CREATING MISSING TEMPLATES")
        print("=" * 80)

        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not academic_year:
            academic_year = AcademicYear.query.first()

        # Get all workloads without templates
        all_workloads = Workload.query.filter_by(
            academic_year_id=academic_year.id,
            semester=2
        ).all()

        print(f"\nTotal workloads: {len(all_workloads)}")

        created = 0
        skipped = 0

        for workload in all_workloads:
            # Check if template exists
            existing = WorkloadTemplate.query.filter_by(
                workload_id=workload.id,
                group_id=workload.group_id,
                semester=2
            ).first()

            if existing:
                skipped += 1
                continue

            # Check if group has GUP
            gup_count = GUP.query.filter_by(
                group_id=workload.group_id,
                academic_year_id=academic_year.id
            ).count()

            if gup_count == 0:
                print(f"  No GUP for {workload.group.name}")
                continue

            # Create template
            template = create_template_for_workload(workload, academic_year)
            if template:
                created += 1
                print(f"  + {template.name}")

        db.session.commit()

        print("\n" + "=" * 80)
        print(f"Created: {created} templates")
        print(f"Skipped: {skipped} (already have templates)")


if __name__ == "__main__":
    create_missing_templates()
