"""
Schedule generator v3 - TEMPLATE-BASED stable schedule.
Creates a weekly template per group and repeats it every week.
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

# Teacher -> room mapping
TEACHER_ROOM = {
    1:70, 2:10, 3:18, 4:71, 6:49, 8:52, 9:73, 10:29, 11:2, 12:24,
    13:79, 14:13, 15:14, 16:72, 18:12, 19:28, 20:23, 21:44, 22:47,
    23:45, 24:20, 25:68, 26:5, 27:7, 28:41, 30:6, 31:37, 32:48,
    33:78, 34:16, 35:25, 36:65, 37:75, 39:46, 41:39, 42:69, 43:34,
    44:36, 45:40, 46:19, 47:11, 50:1, 52:74, 53:43, 54:42, 55:66,
    56:64, 57:22, 59:3, 60:9, 61:35, 62:4, 63:31, 64:52, 65:52,
    66:21, 68:33, 69:27, 70:26, 71:8, 72:77, 73:32, 74:76, 76:67,
    77:52, 80:31, 81:52, 82:73, 84:30, 86:58,
}


def get_weeks(start_date, num_weeks):
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


def build_weekly_template(group, workloads, pair_range, num_weeks, teacher_prefs, course_type):
    """
    Build a fixed weekly template: list of (weekday, pair_num, workload).
    weekday: 0=Mon..4=Fri
    """
    pairs_min, pairs_max = pair_range
    pair_slots = list(range(pairs_min, pairs_max + 1))

    # Calculate pairs per week for each workload
    wl_items = []
    for wl in workloads:
        total_pairs = wl.total_hours // 2
        ppw = max(1, round(total_pairs / num_weeks))
        # Cap: no more than 5 per week (one per day max)
        ppw = min(ppw, 5)
        wl_items.append({
            'wl': wl,
            'ppw': ppw,
            'total_pairs': total_pairs,
            'teacher_id': wl.teacher_id,
        })

    # Sort by ppw descending (most frequent first), then by total hours
    wl_items.sort(key=lambda x: (-x['ppw'], -x['total_pairs']))

    # Build template: fill (weekday, pair) slots
    template = {}  # (weekday, pair) -> workload
    day_disciplines = defaultdict(set)  # weekday -> set of wl.id

    # Track how many slots assigned per workload
    assigned = defaultdict(int)

    for weekday in range(5):  # Mon-Fri
        for pair_num in pair_slots:
            best = None
            best_score = -999

            for wi in wl_items:
                wl = wi['wl']
                tid = wi['teacher_id']

                # Already placed enough for this week?
                if assigned[wl.id] >= wi['ppw']:
                    continue

                # Already placed this discipline today?
                if wl.id in day_disciplines[weekday]:
                    continue

                # Teacher preference blocks this slot?
                if tid and (weekday, pair_num) in teacher_prefs.get(tid, set()):
                    continue

                # Score: prefer workloads needing more ppw that haven't been placed yet
                score = (wi['ppw'] - assigned[wl.id]) * 100 + wi['total_pairs']

                if score > best_score:
                    best_score = score
                    best = wi

            if best is None:
                # Allow same discipline on same day as fallback
                for wi in wl_items:
                    wl = wi['wl']
                    tid = wi['teacher_id']
                    if assigned[wl.id] >= wi['ppw']:
                        continue
                    if tid and (weekday, pair_num) in teacher_prefs.get(tid, set()):
                        continue
                    best = wi
                    break

            if best is not None:
                wl = best['wl']
                template[(weekday, pair_num)] = wl
                day_disciplines[weekday].add(wl.id)
                assigned[wl.id] += 1

    return template


def generate_from_template(groups_config, pair_range, teacher_conflicts, teacher_prefs, course_type):
    """
    Generate schedules by repeating weekly templates.
    course_type: '4', '2', '3' - used for teacher-specific rules
    """
    all_schedules = []
    pairs_min, pairs_max = pair_range

    for gc in groups_config:
        group = gc['group']
        workloads = gc['workloads']
        start_date = gc['start_date']
        num_weeks = gc['num_weeks']

        weeks = get_weeks(start_date, num_weeks)

        # Build the template
        template = build_weekly_template(
            group, workloads, pair_range, num_weeks, teacher_prefs, course_type
        )

        # Track remaining pairs per workload
        remaining = {}
        for wl in workloads:
            remaining[wl.id] = wl.total_hours // 2

        # Show template
        days_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        pair_slots = list(range(pairs_min, pairs_max + 1))
        print(f'\n  Template for {group.name}:')
        for p in pair_slots:
            row = f'    P{p}: '
            for wd in range(5):
                wl = template.get((wd, p))
                if wl:
                    row += f'{days_names[wd]}={wl.discipline[:20]:20s} '
                else:
                    row += f'{days_names[wd]}={"---":20s} '
            print(row)

        # Apply template week by week
        for week_idx, week_days in enumerate(weeks):
            if not week_days:
                continue

            for day in week_days:
                weekday = day.weekday()

                for pair_num in pair_slots:
                    wl = template.get((weekday, pair_num))
                    if not wl:
                        continue
                    if remaining.get(wl.id, 0) <= 0:
                        # This workload is done, try to find a substitute
                        wl = None
                        for sub_wl in workloads:
                            if remaining.get(sub_wl.id, 0) > 0:
                                tid = sub_wl.teacher_id
                                if tid and (weekday, pair_num) in teacher_prefs.get(tid, set()):
                                    continue
                                if tid and tid in teacher_conflicts.get((day, pair_num), set()):
                                    continue
                                wl = sub_wl
                                break
                        if not wl:
                            continue

                    tid = wl.teacher_id

                    # Check teacher conflict for this specific date
                    if tid and tid in teacher_conflicts.get((day, pair_num), set()):
                        # Teacher busy - try another workload for this slot
                        found = False
                        for sub_wl in workloads:
                            if remaining.get(sub_wl.id, 0) <= 0:
                                continue
                            stid = sub_wl.teacher_id
                            if stid and (weekday, pair_num) in teacher_prefs.get(stid, set()):
                                continue
                            if stid and stid in teacher_conflicts.get((day, pair_num), set()):
                                continue
                            wl = sub_wl
                            tid = stid
                            found = True
                            break
                        if not found:
                            continue

                    # Place it
                    room_id = TEACHER_ROOM.get(tid)
                    sched = Schedule(
                        workload_id=wl.id,
                        date=day,
                        pair_number=pair_num,
                        room_id=room_id,
                        status='planned'
                    )
                    all_schedules.append(sched)
                    remaining[wl.id] -= 1
                    if tid:
                        teacher_conflicts[(day, pair_num)].add(tid)

        # Report remaining
        for wl in workloads:
            r = remaining.get(wl.id, 0)
            if r > 0:
                print(f'  WARNING: {group.name} - {wl.discipline[:50]} has {r*2}h unplaced')

    return all_schedules


def main():
    with app.app_context():
        teachers = {t.full_name: t.id for t in Teacher.query.all()}
        teacher_prefs = {}

        # Романов Б. - no 7th pair
        if tid := teachers.get('Романов Б.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}

        # Кадргалиева А. - no 7th pair
        if tid := teachers.get('Кадргалиева А.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}

        # Рахым К. - no 7th pair
        if tid := teachers.get('Рахым К.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}

        # Темирханова Г. - Mon no 5,6; Tue no 5,6
        if tid := teachers.get('Темирханова Г.'):
            teacher_prefs[tid] = {(0, 5), (0, 6), (1, 5), (1, 6)}

        # Кайыров А. - Fri no 5,6,7
        if tid := teachers.get('Кайыров А.'):
            teacher_prefs[tid] = {(4, 5), (4, 6), (4, 7)}

        # Сулеймен Ж. - different per course type
        # For 4 course (pairs 1-4): only pairs 3,4 -> block 1,2
        # For 2-3 course (pairs 4-7): only pair 7 -> block 4,5,6
        suleimen_id = teachers.get('Сулеймен Ж.')

        # We'll handle Сулеймен separately per course type
        teacher_prefs_4 = dict(teacher_prefs)
        teacher_prefs_23 = dict(teacher_prefs)

        if suleimen_id:
            teacher_prefs_4[suleimen_id] = {(wd, 1) for wd in range(5)} | {(wd, 2) for wd in range(5)}
            teacher_prefs_23[suleimen_id] = {(wd, 4) for wd in range(5)} | {(wd, 5) for wd in range(5)} | {(wd, 6) for wd in range(5)}

        # Build teacher conflict map from 1st course
        print('Loading existing schedules (1st course)...')
        teacher_conflicts = build_teacher_conflict_map()
        print(f'  Loaded {sum(len(v) for v in teacher_conflicts.values())} teacher-slot entries')

        # ============ 4 COURSE ============
        print('\n=== 4 COURSE (pairs 1-4) ===')
        groups_4 = Group.query.filter(Group.name.like('%-22')).order_by(Group.name).all()
        config_4 = []
        for g in groups_4:
            wls = Workload.query.filter_by(group_id=g.id).all()
            total = sum(w.total_hours for w in wls)
            total_pairs = total // 2
            num_weeks = max(7, -(-total_pairs // 20))
            num_weeks = min(num_weeks, 22)
            print(f'  {g.name}: {total}h ({total_pairs}p) -> {num_weeks}wk ~{total_pairs//num_weeks}ppw')
            config_4.append({
                'group': g, 'workloads': wls,
                'start_date': date(2026, 2, 2), 'num_weeks': num_weeks,
            })

        schedules_4 = generate_from_template(config_4, (1, 4), teacher_conflicts, teacher_prefs_4, '4')
        print(f'  Total 4 course: {len(schedules_4)} entries')

        # ============ 2 COURSE ============
        print('\n=== 2 COURSE (pairs 4-7) ===')
        groups_2 = Group.query.filter(Group.name.like('%-24')).order_by(Group.name).all()
        config_2 = []
        for g in groups_2:
            wls = Workload.query.filter_by(group_id=g.id).all()
            total = sum(w.total_hours for w in wls)
            total_pairs = total // 2
            print(f'  {g.name}: {total}h ({total_pairs}p) 19wk ~{total_pairs//19}ppw')
            config_2.append({
                'group': g, 'workloads': wls,
                'start_date': date(2026, 2, 2), 'num_weeks': 19,
            })

        schedules_2 = generate_from_template(config_2, (4, 7), teacher_conflicts, teacher_prefs_23, '2')
        print(f'  Total 2 course: {len(schedules_2)} entries')

        # ============ 3 COURSE ============
        print('\n=== 3 COURSE (pairs 4-7) ===')
        groups_3 = Group.query.filter(Group.name.like('%-23')).order_by(Group.name).all()
        config_3 = []
        for g in groups_3:
            wls = Workload.query.filter_by(group_id=g.id).all()
            total = sum(w.total_hours for w in wls)
            start = GROUP_START_DATES_3.get(g.name)
            if not start:
                print(f'  SKIP {g.name}: no start date')
                continue
            total_pairs = total // 2
            num_weeks = max(7, -(-total_pairs // 20))
            num_weeks = min(num_weeks, 18)
            print(f'  {g.name}: {total}h ({total_pairs}p) -> {num_weeks}wk start {start} ~{total_pairs//num_weeks}ppw')
            config_3.append({
                'group': g, 'workloads': wls,
                'start_date': start, 'num_weeks': num_weeks,
            })

        schedules_3 = generate_from_template(config_3, (4, 7), teacher_conflicts, teacher_prefs_23, '3')
        print(f'  Total 3 course: {len(schedules_3)} entries')

        # ============ VALIDATE & SAVE ============
        all_schedules = schedules_4 + schedules_2 + schedules_3
        print(f'\n=== TOTAL: {len(all_schedules)} entries ===')

        # Check teacher conflicts
        conflict_count = 0
        gen_map = defaultdict(set)
        wl_cache = {}
        for s in all_schedules:
            if s.workload_id not in wl_cache:
                wl_cache[s.workload_id] = Workload.query.get(s.workload_id)
            wl = wl_cache[s.workload_id]
            if wl and wl.teacher_id:
                key = (s.date, s.pair_number)
                if wl.teacher_id in gen_map[key]:
                    conflict_count += 1
                gen_map[key].add(wl.teacher_id)

        print(f'Teacher conflicts: {conflict_count}')

        # Check gaps
        group_daily = defaultdict(lambda: defaultdict(list))
        for s in all_schedules:
            wl = wl_cache.get(s.workload_id)
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
        print(f'Total gaps: {total_gaps}')

        # Pairs per week
        group_weekly = defaultdict(lambda: defaultdict(int))
        all_group_names = {}
        for g in groups_4 + groups_2 + groups_3:
            all_group_names[g.id] = g.name
        for s in all_schedules:
            wl = wl_cache.get(s.workload_id)
            if wl:
                wk = s.date.isocalendar()[1]
                group_weekly[wl.group_id][wk] += 1

        print('\nPairs/week:')
        for gid in sorted(group_weekly.keys(), key=lambda x: all_group_names.get(x, '')):
            weeks = group_weekly[gid]
            vals = list(weeks.values())
            gname = all_group_names.get(gid, '?')
            print(f'  {gname}: avg={sum(vals)/len(vals):.1f} min={min(vals)} max={max(vals)}')

        # Save
        print('\nSaving...')
        for s in all_schedules:
            db.session.add(s)
        db.session.commit()
        print('DONE!')

        print(f'\n=== SUMMARY ===')
        print(f'4 course: {len(schedules_4)}')
        print(f'2 course: {len(schedules_2)}')
        print(f'3 course: {len(schedules_3)}')
        print(f'Total: {len(all_schedules)}')
        print(f'Gaps: {total_gaps}')
        print(f'Teacher conflicts: {conflict_count}')


if __name__ == '__main__':
    main()
