#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Compare Excel patterns with database schedule - CORRECTED VERSION
Uses academic year week numbering (starting from Sep 1)
Week 20 = Jan 12-16, 2026 = RIGHT (even)
"""

import sys
import os
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
from app import create_app, db
from app.models import Schedule, Workload, Group, Teacher, Room
from collections import defaultdict

app = create_app()

# Academic year starts Sep 1, 2025
ACADEMIC_YEAR_START = date(2025, 9, 1)

def get_academic_week_number(d):
    """Get week number from start of academic year (Sep 1)
    Week 1 starts Sep 1, 2025
    """
    # Find the Monday of the week containing Sep 1
    days_since_monday = ACADEMIC_YEAR_START.weekday()
    week_start = ACADEMIC_YEAR_START - timedelta(days=days_since_monday)

    # Calculate weeks since start
    days_diff = (d - week_start).days
    week_num = (days_diff // 7) + 1

    return week_num

def get_week_type(d):
    """Get week type: LEFT (odd) or RIGHT (even)
    Week 20 (Jan 12-16, 2026) = RIGHT (even)
    """
    week_num = get_academic_week_number(d)
    return 'RIGHT' if week_num % 2 == 0 else 'LEFT'

# Verify the logic
print("Verifying week calculation:")
test_dates = [
    date(2026, 1, 12),  # Should be week 20 = RIGHT
    date(2026, 1, 19),  # Should be week 21 = LEFT
    date(2026, 1, 26),  # Should be week 22 = RIGHT
]
for d in test_dates:
    wn = get_academic_week_number(d)
    wt = get_week_type(d)
    print(f"  {d}: Week {wn} = {wt}")

# Day name mapping
DAY_NAMES = {
    0: 'ПОНЕДЕЛЬНИК',
    1: 'ВТОРНИК',
    2: 'СРЕДА',
    3: 'ЧЕТВЕРГ',
    4: 'ПЯТНИЦА',
    5: 'СУББОТА',
    6: 'ВОСКРЕСЕНЬЕ'
}

def normalize_discipline(name):
    """Normalize discipline name for comparison"""
    if not name:
        return ''
    name = str(name).strip().lower()
    name = name.replace('ё', 'е').replace('  ', ' ')
    return name

def load_patterns():
    """Load patterns from parsed_schedule.json"""
    with open('parsed_schedule.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_db_schedule():
    """Get schedule from database for 2nd semester (Jan-June 2026)"""
    with app.app_context():
        # 2nd semester: January 12, 2026 - June 30, 2026
        start_date = date(2026, 1, 12)
        end_date = date(2026, 6, 30)

        schedules = Schedule.query.filter(
            Schedule.date >= start_date,
            Schedule.date <= end_date
        ).order_by(Schedule.date, Schedule.pair_number).all()

        # Structure: {group_name: {date: {pair_num: schedule_info}}}
        db_data = defaultdict(lambda: defaultdict(dict))

        for s in schedules:
            if s.workload and s.workload.group:
                group_name = s.workload.group.name
                day = s.date
                pair_num = s.pair_number

                teacher_name = s.workload.teacher.full_name if s.workload.teacher else 'N/A'
                discipline = s.workload.discipline

                db_data[group_name][day][pair_num] = {
                    'id': s.id,
                    'discipline': discipline,
                    'teacher': teacher_name,
                    'workload_id': s.workload_id
                }

        return db_data

def compare_pattern_with_db(group, day_name, pair_num, pattern, db_data):
    """
    Compare pattern from Excel with what's in DB for this group/day/pair
    Returns: dict with comparison results
    """
    results = {
        'correct_pairs': [],      # Pairs that match pattern
        'incorrect_pairs': [],    # Pairs that don't match pattern
        'missing_pairs': []       # Pairs that should exist but don't
    }

    # Find all dates in DB for this group/day_name/pair_num
    for d, pairs in db_data[group].items():
        if DAY_NAMES[d.weekday()] != day_name:
            continue

        pair_info = pairs.get(pair_num)
        week_type = get_week_type(d)
        week_num = get_academic_week_number(d)

        # Determine expected discipline based on pattern and week type
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
            else:
                expected_discipline = None  # Should be empty on right weeks
        elif pattern['type'] == 'right_only':
            if week_type == 'RIGHT':
                expected_discipline = pattern['discipline']
            else:
                expected_discipline = None  # Should be empty on left weeks

        # Skip placeholder disciplines
        if expected_discipline and '---' in expected_discipline:
            expected_discipline = None

        # Compare
        if expected_discipline:
            if pair_info:
                db_disc = normalize_discipline(pair_info['discipline'])
                expected_disc = normalize_discipline(expected_discipline)

                if db_disc == expected_disc or expected_disc in db_disc or db_disc in expected_disc:
                    results['correct_pairs'].append({
                        'date': d,
                        'week_num': week_num,
                        'week_type': week_type,
                        'schedule_id': pair_info['id'],
                        'discipline': pair_info['discipline']
                    })
                else:
                    results['incorrect_pairs'].append({
                        'date': d,
                        'week_num': week_num,
                        'week_type': week_type,
                        'schedule_id': pair_info['id'],
                        'db_discipline': pair_info['discipline'],
                        'expected_discipline': expected_discipline
                    })
            else:
                results['missing_pairs'].append({
                    'date': d,
                    'week_num': week_num,
                    'week_type': week_type,
                    'expected_discipline': expected_discipline
                })
        else:
            # No pair expected for this week type
            if pair_info:
                # There's a pair but shouldn't be
                results['incorrect_pairs'].append({
                    'date': d,
                    'week_num': week_num,
                    'week_type': week_type,
                    'schedule_id': pair_info['id'],
                    'db_discipline': pair_info['discipline'],
                    'expected_discipline': None,
                    'reason': f'Should be empty on {week_type} week'
                })

    return results

def main():
    print("\n" + "=" * 80)
    print("PATTERN COMPARISON V2: Excel vs Database (Academic Year Weeks)")
    print("=" * 80)

    # Load patterns from Excel
    print("\n1. Loading patterns from parsed_schedule.json...")
    patterns = load_patterns()
    print(f"   Loaded patterns for {len(patterns)} groups")

    # Get DB schedule
    print("\n2. Loading schedule from database...")
    db_data = get_db_schedule()
    print(f"   Found {len(db_data)} groups in database")

    # Compare
    print("\n3. Comparing patterns...")

    total_correct = 0
    total_incorrect = 0
    total_missing = 0

    report = {
        'by_group': {},
        'incorrect_to_delete': [],
        'missing_to_create': []
    }

    for group, days in patterns.items():
        group_report = {
            'correct': 0,
            'incorrect': 0,
            'missing': 0,
            'details': []
        }

        for day_name, pairs in days.items():
            for pair_num_str, pattern in pairs.items():
                pair_num = int(pair_num_str)

                results = compare_pattern_with_db(group, day_name, pair_num, pattern, db_data)

                group_report['correct'] += len(results['correct_pairs'])
                group_report['incorrect'] += len(results['incorrect_pairs'])
                group_report['missing'] += len(results['missing_pairs'])

                # Add to global lists
                for inc in results['incorrect_pairs']:
                    report['incorrect_to_delete'].append({
                        'group': group,
                        'day': day_name,
                        'pair': pair_num,
                        **inc
                    })

                for miss in results['missing_pairs']:
                    report['missing_to_create'].append({
                        'group': group,
                        'day': day_name,
                        'pair': pair_num,
                        'pattern': pattern,
                        **miss
                    })

        report['by_group'][group] = group_report
        total_correct += group_report['correct']
        total_incorrect += group_report['incorrect']
        total_missing += group_report['missing']

    # Print summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"\nTotal correct pairs (match pattern):   {total_correct}")
    print(f"Total incorrect pairs (wrong disc):    {total_incorrect}")
    print(f"Total missing pairs (need to create):  {total_missing}")

    # Print by group
    print("\n\nBY GROUP:")
    print("-" * 60)
    for group in sorted(report['by_group'].keys()):
        g = report['by_group'][group]
        status = "OK" if g['incorrect'] == 0 else "NEEDS FIX"
        print(f"{group:15} | Correct: {g['correct']:3} | Wrong: {g['incorrect']:3} | Missing: {g['missing']:3} | {status}")

    # Print first few incorrect pairs with more details
    if report['incorrect_to_delete']:
        print("\n\nFIRST 20 INCORRECT PAIRS (to fix/delete):")
        print("-" * 80)
        for i, inc in enumerate(report['incorrect_to_delete'][:20]):
            date_str = inc['date'].strftime('%d.%m.%Y') if 'date' in inc else 'N/A'
            print(f"{i+1:2}. {inc['group']:12} | {inc['day']:12} | Para {inc['pair']} | {date_str}")
            print(f"    Week {inc.get('week_num', '?')} ({inc.get('week_type', '?')})")
            print(f"    DB: {inc.get('db_discipline', 'N/A')[:50]}")
            print(f"    Expected: {inc.get('expected_discipline', 'EMPTY')}")
            print()

    # Save full report
    output_file = 'pattern_comparison_report_v2.json'

    # Convert dates to strings for JSON
    def convert_dates(obj):
        if isinstance(obj, dict):
            return {k: convert_dates(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_dates(i) for i in obj]
        elif isinstance(obj, date):
            return obj.isoformat()
        return obj

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(convert_dates(report), f, ensure_ascii=False, indent=2)

    print(f"\n\nFull report saved to: {output_file}")

if __name__ == '__main__':
    main()
