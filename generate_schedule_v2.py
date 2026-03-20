"""
Schedule generator v2 - SLOT-FIRST algorithm.
Priority: fill all group slots (no gaps), 18-20 pairs/week, no teacher parallels.
Run: python generate_schedule_v2.py
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
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


def get_weeks(start_date, num_weeks):
    """Get list of weeks, each week is list of working days."""
    d = start_date
    while d.weekday() != 0:
        d += timedelta(days=1)
    weeks = []
    for w in range(num_weeks):
        week_start = d + timedelta(weeks=w)
        week_days = []
        for wd in range(5):
            day = week_start + timedelta(days=wd)
            if day not in HOLIDAYS:
                week_days.append(day)
        weeks.append(week_days)
    return weeks


def build_teacher_conflict_map():
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


def generate_slot_first(groups_config, pair_range, teacher_conflicts, teacher_prefs):
    """
    SLOT-FIRST algorithm:
    Iterate by group -> week -> day -> slot.
    For each empty slot, find the best available workload to place.
    This guarantees no gaps within a group's daily schedule.
    """
    all_schedules = []
    pairs_min, pairs_max = pair_range
    pair_slots = list(range(pairs_min, pairs_max + 1))
    slots_per_day = len(pair_slots)

    for gc in groups_config:
        group = gc['group']
        workloads = gc['workloads']
        start_date = gc['start_date']
        num_weeks = gc['num_weeks']

        weeks = get_weeks(start_date, num_weeks)
        total_available_slots = sum(len(wd) for wd in weeks) * slots_per_day

        # Build workload tracking
        wl_items = []
        total_pairs_needed = 0
        for wl in workloads:
            pairs_needed = wl.total_hours // 2
            total_pairs_needed += pairs_needed
            wl_items.append({
                'wl': wl,
                'remaining': pairs_needed,
                'teacher_id': wl.teacher_id,
                'total_pairs': pairs_needed,
            })

        # Calculate target pairs per week (aim for even distribution)
        target_ppw = min(slots_per_day * 5, max(1, total_pairs_needed // len(weeks))) if weeks else 0
        # Cap at 20 (4 slots * 5 days)
        target_ppw = min(target_ppw, slots_per_day * 5)

        # Calculate ideal pairs per week per workload
        for wi in wl_items:
            wi['ideal_ppw'] = max(1, round(wi['total_pairs'] / len(weeks))) if weeks else 1

        # Sort by total hours descending (larger workloads get priority for spreading)
        wl_items.sort(key=lambda x: -x['total_pairs'])

        # ---- WEEK BY WEEK ----
        for week_idx, week_days in enumerate(weeks):
            if not week_days:
                continue

            # Track placed this week per workload
            week_placed = defaultdict(int)
            # Track disciplines placed per day
            day_disciplines = {d: set() for d in week_days}
            # Track placed pairs per day
            day_pairs = {d: [] for d in week_days}

            # Calculate how many pairs each workload should get this week
            remaining_weeks = len(weeks) - week_idx
            wl_week_targets = {}
            for wi in wl_items:
                if wi['remaining'] <= 0:
                    continue
                # Distribute remaining evenly across remaining weeks
                target = max(1, round(wi['remaining'] / remaining_weeks))
                # Don't exceed remaining
                target = min(target, wi['remaining'])
                # Don't exceed number of days (max 1 per day per discipline)
                target = min(target, len(week_days))
                wl_week_targets[wi['wl'].id] = target

            # ---- FILL SLOTS: day by day, slot by slot ----
            for day in week_days:
                weekday = day.weekday()

                for pair_num in pair_slots:
                    # Find best workload for this slot
                    best = None
                    best_score = -999

                    for wi in wl_items:
                        if wi['remaining'] <= 0:
                            continue

                        wl = wi['wl']
                        tid = wi['teacher_id']
                        wl_id = wl.id

                        # Already placed this discipline today?
                        if wl_id in day_disciplines[day]:
                            continue

                        # Teacher preference blocks this slot?
                        if tid and (weekday, pair_num) in teacher_prefs.get(tid, set()):
                            continue

                        # Teacher already busy at this (date, pair)?
                        if tid and tid in teacher_conflicts.get((day, pair_num), set()):
                            continue

                        # Already hit weekly target for this workload?
                        wl_target = wl_week_targets.get(wl_id, 0)
                        over_target = week_placed[wl_id] >= wl_target

                        # Score: prefer workloads that still need this week's quota
                        score = 0
                        if not over_target:
                            score += 100  # priority to fill weekly quota
                        # Prefer workloads with more remaining hours
                        score += wi['remaining'] / max(1, wi['total_pairs']) * 10
                        # Prefer workloads with higher ideal ppw (they need more slots)
                        score += wi['ideal_ppw']

                        if score > best_score:
                            best_score = score
                            best = wi

                    if best is None:
                        # Try again allowing same discipline on same day (fill the gap!)
                        for wi in wl_items:
                            if wi['remaining'] <= 0:
                                continue
                            wl = wi['wl']
                            tid = wi['teacher_id']
                            if tid and (weekday, pair_num) in teacher_prefs.get(tid, set()):
                                continue
                            if tid and tid in teacher_conflicts.get((day, pair_num), set()):
                                continue
                            best = wi
                            break

                    if best is not None:
                        wl = best['wl']
                        tid = best['teacher_id']

                        # Place it
                        day_pairs[day].append((pair_num, wl.id, tid))
                        day_disciplines[day].add(wl.id)
                        if tid:
                            teacher_conflicts[(day, pair_num)].add(tid)
                        best['remaining'] -= 1
                        week_placed[wl.id] += 1

            # Create Schedule objects
            for day in week_days:
                for pair_num, wl_id, tid in day_pairs[day]:
                    sched = Schedule(
                        workload_id=wl_id,
                        date=day,
                        pair_number=pair_num,
                        status='planned'
                    )
                    all_schedules.append(sched)

        # Report remaining
        for wi in wl_items:
            if wi['remaining'] > 0:
                wl = wi['wl']
                print(f'  WARNING: {group.name} - {wl.discipline[:50]} has {wi["remaining"]*2}h unplaced')

    return all_schedules


def show_template(group_name, workloads, pair_range, num_weeks):
    """Show a template of how the schedule would look for 1 week."""
    pairs_min, pairs_max = pair_range
    pair_slots = list(range(pairs_min, pairs_max + 1))

    # Calculate ppw for each workload
    wl_info = []
    for wl in workloads:
        pairs = wl.total_hours // 2
        ppw = max(1, round(pairs / num_weeks))
        wl_info.append({
            'disc': wl.discipline[:30],
            'teacher': wl.teacher.full_name[:15] if wl.teacher else '?',
            'ppw': ppw,
            'total': pairs,
        })
    wl_info.sort(key=lambda x: -x['ppw'])

    print(f'\n  === TEMPLATE: {group_name} (pairs {pairs_min}-{pairs_max}, {num_weeks} weeks) ===')
    print(f'  Total workloads: {len(wl_info)}, Total pairs: {sum(w["total"] for w in wl_info)}')
    print(f'  Target: {sum(w["total"] for w in wl_info) // num_weeks} pairs/week')
    print()

    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    # Simulate filling 1 week
    plan = {d: {} for d in days}
    used_per_day = {d: set() for d in days}
    wl_placed = defaultdict(int)

    for pair in pair_slots:
        for day in days:
            for wi in wl_info:
                disc = wi['disc']
                if disc in used_per_day[day]:
                    continue
                if wl_placed[disc] >= wi['ppw']:
                    continue
                plan[day][pair] = f"{disc}({wi['teacher']})"
                used_per_day[day].add(disc)
                wl_placed[disc] += 1
                break
            else:
                # Allow repeats to fill gap
                for wi in wl_info:
                    disc = wi['disc']
                    if wl_placed[disc] >= wi['total']:
                        continue
                    plan[day][pair] = f"{disc}({wi['teacher']})*"
                    wl_placed[disc] += 1
                    break

    # Print
    header = f'  {"Pair":5s}'
    for d in days:
        header += f' | {d:40s}'
    print(header)
    print('  ' + '-' * (5 + 5 * 43))

    for pair in pair_slots:
        row = f'  {pair:5d}'
        for d in days:
            cell = plan[d].get(pair, '---')
            row += f' | {cell:40s}'
        print(row)
    print()


def main():
    with app.app_context():
        # ============ LOAD TEACHER PREFERENCES ============
        teachers = {t.full_name: t.id for t in Teacher.query.all()}
        teacher_prefs = {}

        if tid := teachers.get('Романов Б.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}
        if tid := teachers.get('Кадргалиева А.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}
        if tid := teachers.get('Темирханова Г.'):
            teacher_prefs[tid] = {(0, 5), (0, 6), (1, 5), (1, 6)}
        if tid := teachers.get('Кайыров А.'):
            teacher_prefs[tid] = {(4, 5), (4, 6), (4, 7)}

        # ============ BUILD TEACHER CONFLICT MAP (from 1st course) ============
        print('Loading existing schedules (1st course) for conflict checking...')
        teacher_conflicts = build_teacher_conflict_map()
        print(f'  Loaded {sum(len(v) for v in teacher_conflicts.values())} teacher-slot entries')

        # ============ 4 COURSE (1-4 pairs, start Feb 2) ============
        print('\n=== 4 COURSE schedule ===')
        groups_4 = Group.query.filter(Group.name.like('%-22')).order_by(Group.name).all()
        config_4 = []
        for g in groups_4:
            wls = Workload.query.filter_by(group_id=g.id).all()
            total = sum(w.total_hours for w in wls)
            # Target 18-20 pairs/week -> num_weeks = total_pairs / 20 (rounded up)
            total_pairs = total // 2
            num_weeks = max(7, -(-total_pairs // 20))  # ceiling division by 20
            # But also check: don't exceed available calendar
            num_weeks = min(num_weeks, 22)  # max ~22 weeks until June
            print(f'  {g.name}: {total}h ({total_pairs} pairs) -> {num_weeks} weeks, ~{total_pairs//num_weeks} ppw')
            config_4.append({
                'group': g, 'workloads': wls,
                'start_date': date(2026, 2, 2), 'num_weeks': num_weeks,
            })

        # Show template for first group
        if config_4:
            gc = config_4[0]
            show_template(gc['group'].name, gc['workloads'], (1, 4), gc['num_weeks'])

        schedules_4 = generate_slot_first(config_4, (1, 4), teacher_conflicts, teacher_prefs)
        print(f'  Generated: {len(schedules_4)} entries')

        # ============ 2 COURSE (4-7 pairs, start Feb 2, 19 weeks) ============
        print('\n=== 2 COURSE schedule ===')
        groups_2 = Group.query.filter(Group.name.like('%-24')).order_by(Group.name).all()
        config_2 = []
        for g in groups_2:
            wls = Workload.query.filter_by(group_id=g.id).all()
            total = sum(w.total_hours for w in wls)
            total_pairs = total // 2
            print(f'  {g.name}: {total}h ({total_pairs} pairs), 19 weeks, ~{total_pairs//19} ppw')
            config_2.append({
                'group': g, 'workloads': wls,
                'start_date': date(2026, 2, 2), 'num_weeks': 19,
            })

        if config_2:
            gc = config_2[0]
            show_template(gc['group'].name, gc['workloads'], (4, 7), 19)

        schedules_2 = generate_slot_first(config_2, (4, 7), teacher_conflicts, teacher_prefs)
        print(f'  Generated: {len(schedules_2)} entries')

        # ============ 3 COURSE (4-7 pairs, varying start dates) ============
        print('\n=== 3 COURSE schedule ===')
        groups_3 = Group.query.filter(Group.name.like('%-23')).order_by(Group.name).all()
        config_3 = []
        for g in groups_3:
            wls = Workload.query.filter_by(group_id=g.id).all()
            total = sum(w.total_hours for w in wls)
            start = GROUP_START_DATES_3.get(g.name)
            if not start:
                print(f'  SKIP {g.name}: no start date configured')
                continue
            total_pairs = total // 2
            num_weeks = max(7, -(-total_pairs // 20))
            num_weeks = min(num_weeks, 18)
            print(f'  {g.name}: {total}h ({total_pairs} pairs) -> {num_weeks} weeks, start {start}, ~{total_pairs//num_weeks} ppw')
            config_3.append({
                'group': g, 'workloads': wls,
                'start_date': start, 'num_weeks': num_weeks,
            })

        if config_3:
            gc = config_3[0]
            show_template(gc['group'].name, gc['workloads'], (4, 7), gc['num_weeks'])

        schedules_3 = generate_slot_first(config_3, (4, 7), teacher_conflicts, teacher_prefs)
        print(f'  Generated: {len(schedules_3)} entries')

        # ============ VALIDATE & SAVE ============
        all_schedules = schedules_4 + schedules_2 + schedules_3
        print(f'\n=== TOTAL: {len(all_schedules)} schedule entries ===')

        # Validate no teacher conflicts
        conflict_count = 0
        gen_map = defaultdict(set)
        for s in all_schedules:
            wl = Workload.query.get(s.workload_id)
            if wl and wl.teacher_id:
                key = (s.date, s.pair_number)
                if wl.teacher_id in gen_map[key]:
                    conflict_count += 1
                gen_map[key].add(wl.teacher_id)

        print(f'Internal teacher conflicts: {conflict_count}')

        if conflict_count > 0:
            print('WARNING: Teacher conflicts exist!')

        # Analyze gaps
        group_daily = defaultdict(lambda: defaultdict(list))
        for s in all_schedules:
            wl = Workload.query.get(s.workload_id)
            if wl:
                group_daily[wl.group_id][s.date].append(s.pair_number)

        total_gaps = 0
        for gid in group_daily:
            for d in group_daily[gid]:
                pairs = sorted(group_daily[gid][d])
                if len(pairs) > 1:
                    for p in range(min(pairs), max(pairs) + 1):
                        if p not in pairs:
                            total_gaps += 1
        print(f'Total gaps across all groups: {total_gaps}')

        # Analyze pairs per week
        group_weekly = defaultdict(lambda: defaultdict(int))
        for s in all_schedules:
            wl = Workload.query.get(s.workload_id)
            if wl:
                wk = s.date.isocalendar()[1]
                group_weekly[wl.group_id][wk] += 1

        print('\nPairs per week summary:')
        all_group_names = {}
        for g in groups_4 + groups_2 + groups_3:
            all_group_names[g.id] = g.name

        for gid in sorted(group_weekly.keys(), key=lambda x: all_group_names.get(x, '')):
            weeks = group_weekly[gid]
            vals = list(weeks.values())
            gname = all_group_names.get(gid, '?')
            print(f'  {gname}: avg={sum(vals)/len(vals):.1f} min={min(vals)} max={max(vals)}')

        # Save
        print('\nSaving to database...')
        for s in all_schedules:
            db.session.add(s)
        db.session.commit()
        print('DONE!')

        print(f'\n=== SUMMARY ===')
        print(f'4 course: {len(schedules_4)} entries')
        print(f'2 course: {len(schedules_2)} entries')
        print(f'3 course: {len(schedules_3)} entries')
        print(f'Total: {len(all_schedules)} entries')
        print(f'Gaps: {total_gaps}')
        print(f'Teacher conflicts: {conflict_count}')


if __name__ == '__main__':
    main()
