#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fix schedule patterns - correct pairs that don't match Excel patterns
1. Find incorrect pairs and delete them
2. Find missing pairs and create them using correct workloads
3. Preserve workloads (don't delete them)
"""

import sys
import os
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
from app import create_app, db
from app.models import Schedule, Workload, Group, Teacher, Room, GUP, AcademicYear
from collections import defaultdict
from sqlalchemy import and_

app = create_app()

# Academic year starts Sep 1, 2025
ACADEMIC_YEAR_START = date(2025, 9, 1)

def get_academic_week_number(d):
    """Get week number from start of academic year (Sep 1)"""
    days_since_monday = ACADEMIC_YEAR_START.weekday()
    week_start = ACADEMIC_YEAR_START - timedelta(days=days_since_monday)
    days_diff = (d - week_start).days
    week_num = (days_diff // 7) + 1
    return week_num

def get_week_type(d):
    """Get week type: LEFT (odd) or RIGHT (even)"""
    week_num = get_academic_week_number(d)
    return 'RIGHT' if week_num % 2 == 0 else 'LEFT'

DAY_NAMES = {
    0: 'ПОНЕДЕЛЬНИК',
    1: 'ВТОРНИК',
    2: 'СРЕДА',
    3: 'ЧЕТВЕРГ',
    4: 'ПЯТНИЦА',
    5: 'СУББОТА',
    6: 'ВОСКРЕСЕНЬЕ'
}

DAY_TO_WEEKDAY = {
    'ПОНЕДЕЛЬНИК': 0,
    'ВТОРНИК': 1,
    'СРЕДА': 2,
    'ЧЕТВЕРГ': 3,
    'ПЯТНИЦА': 4,
    'СУББОТА': 5,
    'ВОСКРЕСЕНЬЕ': 6
}

def normalize_discipline(name):
    """Normalize discipline name for comparison"""
    if not name:
        return ''
    name = str(name).strip().lower()
    name = name.replace('ё', 'е').replace('  ', ' ')
    # Remove common variations
    name = name.replace('казахский', 'казахская')
    name = name.replace('литература', 'литература')
    return name

def disciplines_match(db_disc, excel_disc):
    """Check if two discipline names match (fuzzy comparison)"""
    if not db_disc or not excel_disc:
        return False

    norm_db = normalize_discipline(db_disc)
    norm_excel = normalize_discipline(excel_disc)

    # Exact match
    if norm_db == norm_excel:
        return True

    # One contains the other
    if norm_excel in norm_db or norm_db in norm_excel:
        return True

    # Check first 10 chars for similar disciplines
    if len(norm_db) >= 10 and len(norm_excel) >= 10:
        if norm_db[:10] == norm_excel[:10]:
            return True

    return False

def load_patterns():
    """Load patterns from parsed_schedule.json"""
    with open('parsed_schedule.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def find_workload(group_name, discipline, teacher_name_pattern=None):
    """Find workload by group and discipline"""
    with app.app_context():
        group = Group.query.filter_by(name=group_name).first()
        if not group:
            return None

        # Find workloads for this group and discipline (semester 2)
        workloads = Workload.query.filter(
            Workload.group_id == group.id,
            Workload.semester == 2
        ).all()

        for w in workloads:
            if disciplines_match(w.discipline, discipline):
                return w

        return None

def is_study_day(d, group_name):
    """Check if this day is a study day (not holiday/practice/etc)"""
    with app.app_context():
        group = Group.query.filter_by(name=group_name).first()
        if not group:
            return True  # Assume study day if group not found

        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not academic_year:
            return True

        week_num = get_academic_week_number(d)

        gup = GUP.query.filter_by(
            group_id=group.id,
            academic_year_id=academic_year.id,
            week_number=week_num
        ).first()

        if gup and not gup.needs_schedule:
            return False  # Not a study week

        return True

def get_semester_dates():
    """Get all dates for 2nd semester"""
    start = date(2026, 1, 12)
    end = date(2026, 6, 30)

    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday-Friday
            dates.append(current)
        current += timedelta(days=1)

    return dates

def analyze_and_fix(dry_run=True):
    """Analyze patterns and fix schedule"""

    patterns = load_patterns()
    print(f"Loaded patterns for {len(patterns)} groups")

    stats = {
        'correct': 0,
        'to_delete': [],
        'to_create': [],
        'no_workload': []
    }

    all_dates = get_semester_dates()
    print(f"Analyzing {len(all_dates)} dates in semester 2")

    with app.app_context():
        for group_name, days in patterns.items():
            group = Group.query.filter_by(name=group_name).first()
            if not group:
                print(f"  Warning: Group {group_name} not found in DB")
                continue

            for day_name, pairs in days.items():
                weekday = DAY_TO_WEEKDAY[day_name]

                for pair_num_str, pattern in pairs.items():
                    pair_num = int(pair_num_str)

                    # Get dates for this weekday
                    day_dates = [d for d in all_dates if d.weekday() == weekday]

                    for d in day_dates:
                        # Check if study day
                        if not is_study_day(d, group_name):
                            continue

                        week_type = get_week_type(d)

                        # Determine expected discipline
                        expected_discipline = None
                        if pattern['type'] == 'every_week':
                            expected_discipline = pattern['discipline']
                        elif pattern['type'] == 'alternating':
                            if week_type == 'LEFT':
                                expected_discipline = pattern.get('left_discipline', '')
                            else:
                                expected_discipline = pattern.get('right_discipline', '')
                        elif pattern['type'] == 'left_only':
                            if week_type == 'LEFT':
                                expected_discipline = pattern['discipline']
                        elif pattern['type'] == 'right_only':
                            if week_type == 'RIGHT':
                                expected_discipline = pattern['discipline']

                        # Skip placeholder disciplines
                        if expected_discipline and '---' in expected_discipline:
                            expected_discipline = None

                        # Find existing schedule
                        existing = Schedule.query.join(Workload).filter(
                            Workload.group_id == group.id,
                            Schedule.date == d,
                            Schedule.pair_number == pair_num
                        ).first()

                        if expected_discipline:
                            # Should have a pair
                            if existing:
                                # Check if discipline matches
                                if disciplines_match(existing.workload.discipline, expected_discipline):
                                    stats['correct'] += 1
                                else:
                                    # Wrong discipline - need to fix
                                    stats['to_delete'].append({
                                        'id': existing.id,
                                        'group': group_name,
                                        'date': d,
                                        'pair': pair_num,
                                        'current': existing.workload.discipline,
                                        'expected': expected_discipline
                                    })

                                    # And create correct one
                                    workload = find_workload(group_name, expected_discipline)
                                    if workload:
                                        stats['to_create'].append({
                                            'group': group_name,
                                            'date': d,
                                            'pair': pair_num,
                                            'workload_id': workload.id,
                                            'discipline': expected_discipline
                                        })
                                    else:
                                        stats['no_workload'].append({
                                            'group': group_name,
                                            'discipline': expected_discipline
                                        })
                            else:
                                # Missing pair - need to create
                                workload = find_workload(group_name, expected_discipline)
                                if workload:
                                    stats['to_create'].append({
                                        'group': group_name,
                                        'date': d,
                                        'pair': pair_num,
                                        'workload_id': workload.id,
                                        'discipline': expected_discipline
                                    })
                                else:
                                    stats['no_workload'].append({
                                        'group': group_name,
                                        'discipline': expected_discipline
                                    })
                        else:
                            # Should NOT have a pair
                            if existing:
                                stats['to_delete'].append({
                                    'id': existing.id,
                                    'group': group_name,
                                    'date': d,
                                    'pair': pair_num,
                                    'current': existing.workload.discipline,
                                    'expected': 'NONE (should be empty)',
                                    'reason': f'{week_type} week - no class'
                                })

    # Print results
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    print(f"Correct pairs: {stats['correct']}")
    print(f"Pairs to delete: {len(stats['to_delete'])}")
    print(f"Pairs to create: {len(stats['to_create'])}")
    print(f"Missing workloads: {len(set(str(x) for x in stats['no_workload']))}")

    if stats['to_delete']:
        print("\n\nFirst 10 pairs to DELETE:")
        for i, item in enumerate(stats['to_delete'][:10]):
            print(f"  {i+1}. {item['group']} | {item['date']} | Para {item['pair']}")
            print(f"      Current: {item['current']}")
            print(f"      Expected: {item['expected']}")

    if stats['to_create']:
        print("\n\nFirst 10 pairs to CREATE:")
        for i, item in enumerate(stats['to_create'][:10]):
            print(f"  {i+1}. {item['group']} | {item['date']} | Para {item['pair']}")
            print(f"      Discipline: {item['discipline']}")

    if stats['no_workload']:
        unique_missing = set()
        for item in stats['no_workload']:
            unique_missing.add(f"{item['group']}: {item['discipline']}")
        print("\n\nMissing workloads (need to create):")
        for m in sorted(unique_missing)[:20]:
            print(f"  - {m}")

    if not dry_run:
        print("\n\n" + "=" * 60)
        print("APPLYING CHANGES...")
        print("=" * 60)

        with app.app_context():
            # Delete incorrect pairs
            deleted = 0
            for item in stats['to_delete']:
                schedule = Schedule.query.get(item['id'])
                if schedule:
                    db.session.delete(schedule)
                    deleted += 1

            db.session.commit()
            print(f"Deleted {deleted} incorrect pairs")

            # Create missing pairs
            created = 0
            errors = 0
            for item in stats['to_create']:
                try:
                    # Check if already exists
                    existing = Schedule.query.filter_by(
                        workload_id=item['workload_id'],
                        date=item['date'],
                        pair_number=item['pair']
                    ).first()

                    if not existing:
                        schedule = Schedule(
                            workload_id=item['workload_id'],
                            date=item['date'],
                            pair_number=item['pair'],
                            status='planned'
                        )
                        db.session.add(schedule)
                        created += 1
                except Exception as e:
                    errors += 1

            db.session.commit()
            print(f"Created {created} new pairs ({errors} errors)")

    return stats

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry run)')
    args = parser.parse_args()

    if args.apply:
        print("=" * 60)
        print("RUNNING IN APPLY MODE - CHANGES WILL BE SAVED")
        print("=" * 60)
        analyze_and_fix(dry_run=False)
    else:
        print("=" * 60)
        print("RUNNING IN DRY RUN MODE - NO CHANGES WILL BE MADE")
        print("=" * 60)
        analyze_and_fix(dry_run=True)
