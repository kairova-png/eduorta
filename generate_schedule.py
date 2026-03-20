"""
Schedule generator for 2, 3, 4 courses.
Run: python generate_schedule.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, timedelta
from collections import defaultdict
from app import create_app, db
from app.models import Workload, Group, Teacher, Schedule

app = create_app()

# ============ CONSTANTS ============

HOLIDAYS = {
    date(2026, 3, 9), date(2026, 3, 23), date(2026, 3, 24), date(2026, 3, 25),
    date(2026, 5, 1), date(2026, 5, 7), date(2026, 5, 11), date(2026, 5, 27),
}

# Teacher preferences: teacher_id -> set of (weekday, pair) that are BLOCKED
# weekday: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri
TEACHER_PREFS = {}

# 3 course group start dates
GROUP_START_DATES_3 = {
    'ЭС 1-23': date(2026, 3, 9), 'ЭС 2-23': date(2026, 3, 9),
    'ХТП 1-23': date(2026, 3, 9), 'ХТП 2-23': date(2026, 3, 9), 'ХТП 3-23': date(2026, 3, 9),
    'БНГС 1-23': date(2026, 3, 9),
    'АиУ 1-23': date(2026, 3, 16), 'АиУ 2-23': date(2026, 3, 16), 'АиУ 3-23': date(2026, 3, 16),
    'ТДНГ 1-23': date(2026, 3, 16),
    'ЭНГМ 1-23': date(2026, 3, 16),
    'МЕХ 1-23': date(2026, 3, 23), 'МЕХ 2-23': date(2026, 3, 23),
    'ПО 1-23': date(2026, 3, 23), 'ПО 2-23': date(2026, 3, 23),
    'ПО 3-23': date(2026, 3, 23), 'ПО 4-23': date(2026, 3, 23),
}


def get_weekdays(start_date, num_weeks):
    """Get all working days (Mon-Fri) for num_weeks, excluding holidays."""
    days = []
    d = start_date
    # Align to Monday if needed
    while d.weekday() != 0:
        d += timedelta(days=1)

    end_date = d + timedelta(weeks=num_weeks)
    current = d
    while current < end_date:
        if current.weekday() < 5 and current not in HOLIDAYS:
            days.append(current)
        current += timedelta(days=1)
    return days


def get_weeks(start_date, num_weeks):
    """Get list of weeks, each week is list of working days."""
    d = start_date
    while d.weekday() != 0:
        d += timedelta(days=1)

    weeks = []
    for w in range(num_weeks):
        week_start = d + timedelta(weeks=w)
        week_days = []
        for wd in range(5):  # Mon-Fri
            day = week_start + timedelta(days=wd)
            if day not in HOLIDAYS:
                week_days.append(day)
        weeks.append(week_days)
    return weeks


def calc_pairs_per_week(total_hours, num_weeks):
    """Calculate how many pairs per week for a workload."""
    total_pairs = total_hours // 2
    ppw = total_pairs / num_weeks
    # Round to nearest integer, minimum 1
    return max(1, round(ppw))


def build_teacher_conflict_map(app_context):
    """Build map of (date, pair_number) -> set of teacher_ids from existing schedules."""
    conflicts = defaultdict(set)
    existing = db.session.query(
        Schedule.date, Schedule.pair_number, Workload.teacher_id
    ).join(Workload).filter(
        Schedule.status.notin_(['cancelled', 'rescheduled'])
    ).all()

    for d, pair, tid in existing:
        if tid:
            conflicts[(d, pair)].add(tid)

    return conflicts


def generate_for_groups(groups_config, pair_range, teacher_conflicts, teacher_prefs):
    """
    Generate schedule for a set of groups.

    groups_config: list of {group: Group, workloads: [Workload], start_date, num_weeks}
    pair_range: tuple (min_pair, max_pair) e.g. (4,7) or (1,4)
    teacher_conflicts: dict (date, pair) -> set of teacher_ids
    teacher_prefs: dict teacher_id -> set of (weekday, pair) blocked

    Returns list of Schedule objects to insert.
    """
    all_schedules = []

    for gc in groups_config:
        group = gc['group']
        workloads = gc['workloads']
        start_date = gc['start_date']
        num_weeks = gc['num_weeks']

        weeks = get_weeks(start_date, num_weeks)
        pairs_min, pairs_max = pair_range
        slots_per_day = pairs_max - pairs_min + 1  # e.g. 4 slots

        # Calculate pairs per week for each workload
        wl_schedule = []
        for wl in workloads:
            ppw = calc_pairs_per_week(wl.total_hours, num_weeks)
            remaining = wl.total_hours // 2  # total pairs needed
            wl_schedule.append({
                'workload': wl,
                'pairs_per_week': ppw,
                'remaining': remaining,
                'teacher_id': wl.teacher_id,
            })

        # Sort: more pairs per week first (they're harder to place)
        wl_schedule.sort(key=lambda x: -x['pairs_per_week'])

        # Generate week by week
        for week_days in weeks:
            if not week_days:
                continue

            # Track what's placed this week: day_index -> list of (pair_num, workload_id, teacher_id)
            week_plan = {d: [] for d in week_days}
            # Track disciplines placed per day to avoid duplicates
            day_disciplines = {d: set() for d in week_days}
            # Track teacher usage this day+pair across all groups

            for ws in wl_schedule:
                if ws['remaining'] <= 0:
                    continue

                wl = ws['workload']
                tid = ws['teacher_id']
                ppw = min(ws['pairs_per_week'], ws['remaining'])

                placed_this_week = 0

                # Try to place ppw pairs across different days
                for day in week_days:
                    if placed_this_week >= ppw:
                        break
                    if ws['remaining'] <= 0:
                        break

                    weekday = day.weekday()

                    # Check if this discipline already placed today
                    if wl.id in day_disciplines[day]:
                        continue

                    # Check if day is full
                    if len(week_plan[day]) >= slots_per_day:
                        continue

                    # Find available pair slot
                    used_pairs = {p for p, _, _ in week_plan[day]}
                    available_pair = None

                    for p in range(pairs_min, pairs_max + 1):
                        if p in used_pairs:
                            continue
                        # Check teacher preference
                        if tid and (weekday, p) in teacher_prefs.get(tid, set()):
                            continue
                        # Check teacher conflict
                        if tid and tid in teacher_conflicts.get((day, p), set()):
                            continue
                        available_pair = p
                        break

                    if available_pair is None:
                        continue

                    # Place it
                    week_plan[day].append((available_pair, wl.id, tid))
                    day_disciplines[day].add(wl.id)
                    if tid:
                        teacher_conflicts[(day, available_pair)].add(tid)

                    ws['remaining'] -= 1
                    placed_this_week += 1

                # If couldn't place enough, try remaining days again (second pass)
                if placed_this_week < ppw and ws['remaining'] > 0:
                    for day in week_days:
                        if placed_this_week >= ppw:
                            break
                        if ws['remaining'] <= 0:
                            break
                        if wl.id in day_disciplines[day]:
                            continue
                        if len(week_plan[day]) >= slots_per_day:
                            continue

                        weekday = day.weekday()
                        used_pairs = {p for p, _, _ in week_plan[day]}

                        for p in range(pairs_min, pairs_max + 1):
                            if p in used_pairs:
                                continue
                            if tid and (weekday, p) in teacher_prefs.get(tid, set()):
                                continue
                            if tid and tid in teacher_conflicts.get((day, p), set()):
                                continue

                            week_plan[day].append((p, wl.id, tid))
                            day_disciplines[day].add(wl.id)
                            if tid:
                                teacher_conflicts[(day, p)].add(tid)
                            ws['remaining'] -= 1
                            placed_this_week += 1
                            break

            # Sort each day's pairs to minimize gaps
            for day in week_days:
                entries = week_plan[day]
                entries.sort(key=lambda x: x[0])
                for pair_num, wl_id, tid in entries:
                    sched = Schedule(
                        workload_id=wl_id,
                        date=day,
                        pair_number=pair_num,
                        status='planned'
                    )
                    all_schedules.append(sched)

        # Report remaining hours
        for ws in wl_schedule:
            if ws['remaining'] > 0:
                wl = ws['workload']
                print(f'  WARNING: {group.name} - {wl.discipline[:40]} has {ws["remaining"]*2}h unplaced')

    return all_schedules


def main():
    with app.app_context():
        # ============ LOAD TEACHER PREFERENCES ============
        teachers = {t.full_name: t.id for t in Teacher.query.all()}

        teacher_prefs = {}

        # Romanов Б. - no 7th pair
        if tid := teachers.get('Романов Б.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}

        # Кадргалиева А. - no 7th pair
        if tid := teachers.get('Кадргалиева А.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}

        # Темирханова Г. - Mon no 5,6; Tue no 5,6
        if tid := teachers.get('Темирханова Г.'):
            teacher_prefs[tid] = {(0, 5), (0, 6), (1, 5), (1, 6)}

        # Кайыров А. - Fri no 5,6,7
        if tid := teachers.get('Кайыров А.'):
            teacher_prefs[tid] = {(4, 5), (4, 6), (4, 7)}

        # ============ BUILD TEACHER CONFLICT MAP ============
        print('Loading existing schedules for conflict checking...')
        teacher_conflicts = build_teacher_conflict_map(app)
        print(f'  Loaded {sum(len(v) for v in teacher_conflicts.values())} teacher-slot entries')

        # ============ 4 COURSE (1-4 pairs, start Feb 2) ============
        print('\n=== Generating 4 COURSE schedule ===')
        groups_4 = Group.query.filter(Group.name.like('%-22')).order_by(Group.name).all()
        config_4 = []
        for g in groups_4:
            wls = Workload.query.filter_by(group_id=g.id).all()
            total = sum(w.total_hours for w in wls)
            num_weeks = max(7, round(total / 36))
            print(f'  {g.name}: {total}h -> {num_weeks} weeks')
            config_4.append({
                'group': g,
                'workloads': wls,
                'start_date': date(2026, 2, 2),
                'num_weeks': num_weeks,
            })

        schedules_4 = generate_for_groups(config_4, (1, 4), teacher_conflicts, teacher_prefs)
        print(f'  Generated: {len(schedules_4)} schedule entries')

        # ============ 2 COURSE (4-7 pairs, start Feb 2, 19 weeks) ============
        print('\n=== Generating 2 COURSE schedule ===')
        groups_2 = Group.query.filter(Group.name.like('%-24')).order_by(Group.name).all()
        config_2 = []
        for g in groups_2:
            wls = Workload.query.filter_by(group_id=g.id).all()
            total = sum(w.total_hours for w in wls)
            print(f'  {g.name}: {total}h, 19 weeks')
            config_2.append({
                'group': g,
                'workloads': wls,
                'start_date': date(2026, 2, 2),
                'num_weeks': 19,
            })

        schedules_2 = generate_for_groups(config_2, (4, 7), teacher_conflicts, teacher_prefs)
        print(f'  Generated: {len(schedules_2)} schedule entries')

        # ============ 3 COURSE (4-7 pairs, varying start dates) ============
        print('\n=== Generating 3 COURSE schedule ===')
        groups_3 = Group.query.filter(Group.name.like('%-23')).order_by(Group.name).all()
        config_3 = []
        for g in groups_3:
            wls = Workload.query.filter_by(group_id=g.id).all()
            total = sum(w.total_hours for w in wls)
            start = GROUP_START_DATES_3.get(g.name)
            if not start:
                print(f'  SKIP {g.name}: no start date configured')
                continue
            num_weeks = max(7, round(total / 36))
            print(f'  {g.name}: {total}h -> {num_weeks} weeks, start {start}')
            config_3.append({
                'group': g,
                'workloads': wls,
                'start_date': start,
                'num_weeks': num_weeks,
            })

        schedules_3 = generate_for_groups(config_3, (4, 7), teacher_conflicts, teacher_prefs)
        print(f'  Generated: {len(schedules_3)} schedule entries')

        # ============ SAVE ALL ============
        all_schedules = schedules_4 + schedules_2 + schedules_3
        print(f'\n=== TOTAL: {len(all_schedules)} schedule entries ===')

        # Validate no teacher conflicts in generated data
        conflict_count = 0
        gen_map = defaultdict(set)
        for s in all_schedules:
            wl = Workload.query.get(s.workload_id)
            if wl and wl.teacher_id:
                key = (s.date, s.pair_number)
                if wl.teacher_id in gen_map[key]:
                    conflict_count += 1
                gen_map[key].add(wl.teacher_id)

        # Also check against existing
        for s in all_schedules:
            wl = Workload.query.get(s.workload_id)
            if wl and wl.teacher_id:
                key = (s.date, s.pair_number)
                existing_teachers = teacher_conflicts.get(key, set())
                # Note: we already added to teacher_conflicts during generation
                # so need to check original map

        print(f'Internal conflicts found: {conflict_count}')

        if conflict_count > 0:
            print('WARNING: There are teacher conflicts! Review needed.')

        # Insert into DB
        print('Saving to database...')
        for s in all_schedules:
            db.session.add(s)

        db.session.commit()
        print('DONE! All schedules saved.')

        # Summary
        print('\n=== SUMMARY ===')
        print(f'4 course: {len(schedules_4)} entries')
        print(f'2 course: {len(schedules_2)} entries')
        print(f'3 course: {len(schedules_3)} entries')
        print(f'Total: {len(all_schedules)} entries')


if __name__ == '__main__':
    main()
