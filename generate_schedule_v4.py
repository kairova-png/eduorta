"""
Schedule generator v4 - TEMPLATE-BASED with 18ppw hybrid formula.
Mon/Fri = 3 pairs (short), Tue/Wed/Thu = 4 pairs (full) -> 18ppw default.
Groups with >342 pairs in 19 weeks auto-upgrade to 20ppw.
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, timedelta
from collections import defaultdict
from app import create_app, db
from app.models import Workload, Group, Teacher, Schedule

app = create_app()

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

SHORT_DAYS = {0, 4}  # Monday, Friday


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


def get_day_slots(pair_range, weekday, use_18ppw):
    pairs_min, pairs_max = pair_range
    all_slots = list(range(pairs_min, pairs_max + 1))
    if use_18ppw and weekday in SHORT_DAYS:
        return all_slots[:-1]
    return all_slots


def build_weekly_template(workloads, pair_range, num_weeks, teacher_prefs, use_18ppw):
    day_slots = {}
    for wd in range(5):
        day_slots[wd] = get_day_slots(pair_range, wd, use_18ppw)

    wl_items = []
    for wl in workloads:
        total_pairs = wl.total_hours // 2
        ppw = max(1, round(total_pairs / num_weeks))
        ppw = min(ppw, 5)
        wl_items.append({
            'wl': wl, 'ppw': ppw, 'total_pairs': total_pairs,
            'teacher_id': wl.teacher_id,
        })
    wl_items.sort(key=lambda x: (-x['ppw'], -x['total_pairs']))

    template = {}
    day_disciplines = defaultdict(set)
    assigned = defaultdict(int)

    for weekday in range(5):
        for pair_num in day_slots[weekday]:
            best = None
            best_score = -999
            for wi in wl_items:
                wl = wi['wl']
                tid = wi['teacher_id']
                if assigned[wl.id] >= wi['ppw']:
                    continue
                if wl.id in day_disciplines[weekday]:
                    continue
                if tid and (weekday, pair_num) in teacher_prefs.get(tid, set()):
                    continue
                score = (wi['ppw'] - assigned[wl.id]) * 100 + wi['total_pairs']
                if score > best_score:
                    best_score = score
                    best = wi
            if best is None:
                for wi in wl_items:
                    if assigned[wi['wl'].id] >= wi['ppw']:
                        continue
                    tid = wi['teacher_id']
                    if tid and (weekday, pair_num) in teacher_prefs.get(tid, set()):
                        continue
                    best = wi
                    break
            if best is not None:
                template[(weekday, pair_num)] = best['wl']
                day_disciplines[weekday].add(best['wl'].id)
                assigned[best['wl'].id] += 1

    return template, day_slots


def generate_from_template(groups_config, pair_range, teacher_conflicts, teacher_prefs):
    all_schedules = []
    for gc in groups_config:
        group = gc['group']
        workloads = gc['workloads']
        start_date = gc['start_date']
        num_weeks = gc['num_weeks']
        use_18ppw = gc['use_18ppw']

        weeks = get_weeks(start_date, num_weeks)
        template, day_slots = build_weekly_template(
            workloads, pair_range, num_weeks, teacher_prefs, use_18ppw
        )

        remaining = {wl.id: wl.total_hours // 2 for wl in workloads}

        for week_days in weeks:
            if not week_days:
                continue
            for day in week_days:
                weekday = day.weekday()
                for pair_num in day_slots.get(weekday, []):
                    wl = template.get((weekday, pair_num))
                    if not wl or remaining.get(wl.id, 0) <= 0:
                        wl = None
                        for sub_wl in workloads:
                            if remaining.get(sub_wl.id, 0) <= 0:
                                continue
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
                    if tid and tid in teacher_conflicts.get((day, pair_num), set()):
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

                    room_id = TEACHER_ROOM.get(tid)
                    sched = Schedule(
                        workload_id=wl.id, date=day,
                        pair_number=pair_num, room_id=room_id,
                        status='planned'
                    )
                    all_schedules.append(sched)
                    remaining[wl.id] -= 1
                    if tid:
                        teacher_conflicts[(day, pair_num)].add(tid)

        for wl in workloads:
            r = remaining.get(wl.id, 0)
            if r > 0:
                print(f'  WARNING: {group.name} - {wl.discipline[:50]} has {r*2}h unplaced')

    return all_schedules


def main():
    with app.app_context():
        teachers = {t.full_name: t.id for t in Teacher.query.all()}
        teacher_prefs = {}

        if tid := teachers.get('Романов Б.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}
        if tid := teachers.get('Кадргалиева А.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}
        if tid := teachers.get('Рахым К.'):
            teacher_prefs[tid] = {(wd, 7) for wd in range(5)}
        if tid := teachers.get('Темирханова Г.'):
            teacher_prefs[tid] = {(0, 5), (0, 6), (1, 5), (1, 6)}
        if tid := teachers.get('Кайыров А.'):
            teacher_prefs[tid] = {(4, 5), (4, 6), (4, 7)}

        suleimen_id = teachers.get('Сулеймен Ж.')
        teacher_prefs_4 = dict(teacher_prefs)
        teacher_prefs_23 = dict(teacher_prefs)
        if suleimen_id:
            teacher_prefs_4[suleimen_id] = {(wd, 1) for wd in range(5)} | {(wd, 2) for wd in range(5)}
            teacher_prefs_23[suleimen_id] = {(wd, 4) for wd in range(5)} | {(wd, 5) for wd in range(5)} | {(wd, 6) for wd in range(5)}

        print('Loading 1st course conflicts...')
        teacher_conflicts = build_teacher_conflict_map()
        print(f'  {sum(len(v) for v in teacher_conflicts.values())} entries')

        # 4 COURSE (pairs 1-4)
        print('\n=== 4 COURSE ===')
        groups_4 = Group.query.filter(Group.name.like('%-22')).order_by(Group.name).all()
        config_4 = []
        for g in groups_4:
            wls = Workload.query.filter_by(group_id=g.id).all()
            tp = sum(w.total_hours for w in wls) // 2
            avail = 22
            w18 = -(-tp // 18)
            use_18 = w18 <= avail
            nw = max(7, min(avail, w18 if use_18 else -(-tp // 20)))
            print(f'  {g.name}: {tp}p -> {nw}wk {"18" if use_18 else "20"}ppw')
            config_4.append({'group': g, 'workloads': wls, 'start_date': date(2026, 2, 2),
                             'num_weeks': nw, 'use_18ppw': use_18})
        s4 = generate_from_template(config_4, (1, 4), teacher_conflicts, teacher_prefs_4)
        print(f'  Total: {len(s4)}')

        # 2 COURSE (pairs 4-7)
        print('\n=== 2 COURSE ===')
        groups_2 = Group.query.filter(Group.name.like('%-24')).order_by(Group.name).all()
        config_2 = []
        for g in groups_2:
            wls = Workload.query.filter_by(group_id=g.id).all()
            tp = sum(w.total_hours for w in wls) // 2
            avail = 19
            w18 = -(-tp // 18)
            use_18 = w18 <= avail
            print(f'  {g.name}: {tp}p {avail}wk {"18" if use_18 else "20"}ppw')
            config_2.append({'group': g, 'workloads': wls, 'start_date': date(2026, 2, 2),
                             'num_weeks': avail, 'use_18ppw': use_18})
        s2 = generate_from_template(config_2, (4, 7), teacher_conflicts, teacher_prefs_23)
        print(f'  Total: {len(s2)}')

        # 3 COURSE (pairs 4-7)
        print('\n=== 3 COURSE ===')
        groups_3 = Group.query.filter(Group.name.like('%-23')).order_by(Group.name).all()
        config_3 = []
        for g in groups_3:
            wls = Workload.query.filter_by(group_id=g.id).all()
            tp = sum(w.total_hours for w in wls) // 2
            start = GROUP_START_DATES_3.get(g.name)
            if not start:
                print(f'  SKIP {g.name}')
                continue
            avail = 18
            w18 = -(-tp // 18)
            use_18 = w18 <= avail
            nw = max(7, min(avail, w18 if use_18 else -(-tp // 20)))
            print(f'  {g.name}: {tp}p -> {nw}wk start {start} {"18" if use_18 else "20"}ppw')
            config_3.append({'group': g, 'workloads': wls, 'start_date': start,
                             'num_weeks': nw, 'use_18ppw': use_18})
        s3 = generate_from_template(config_3, (4, 7), teacher_conflicts, teacher_prefs_23)
        print(f'  Total: {len(s3)}')

        # VALIDATE & SAVE
        all_s = s4 + s2 + s3
        print(f'\n=== TOTAL: {len(all_s)} ===')

        cc = 0
        gm = defaultdict(set)
        wc = {}
        for s in all_s:
            if s.workload_id not in wc:
                wc[s.workload_id] = db.session.get(Workload, s.workload_id)
            wl = wc[s.workload_id]
            if wl and wl.teacher_id:
                k = (s.date, s.pair_number)
                if wl.teacher_id in gm[k]:
                    cc += 1
                gm[k].add(wl.teacher_id)
        print(f'Teacher conflicts: {cc}')

        gd = defaultdict(lambda: defaultdict(list))
        for s in all_s:
            wl = wc.get(s.workload_id)
            if wl:
                gd[wl.group_id][s.date].append(s.pair_number)
        tg = 0
        for gid in gd:
            for d in gd[gid]:
                ps = sorted(gd[gid][d])
                if len(ps) > 1:
                    for p in range(min(ps), max(ps) + 1):
                        if p not in ps:
                            tg += 1
        print(f'Total gaps: {tg}')

        gw = defaultdict(lambda: defaultdict(int))
        gn = {}
        for g in groups_4 + groups_2 + groups_3:
            gn[g.id] = g.name
        for s in all_s:
            wl = wc.get(s.workload_id)
            if wl:
                gw[wl.group_id][s.date.isocalendar()[1]] += 1
        print('\nPairs/week:')
        for gid in sorted(gw.keys(), key=lambda x: gn.get(x, '')):
            vs = list(gw[gid].values())
            print(f'  {gn.get(gid,"?")}: avg={sum(vs)/len(vs):.1f} min={min(vs)} max={max(vs)}')

        an = {}
        for gc in config_4 + config_2 + config_3:
            an[gc['group'].id] = gc['group'].name
        c4 = sum(1 for s in all_s if wc.get(s.workload_id) and an.get(wc[s.workload_id].group_id,'').endswith('-22'))
        c2 = sum(1 for s in all_s if wc.get(s.workload_id) and an.get(wc[s.workload_id].group_id,'').endswith('-24'))
        c3 = sum(1 for s in all_s if wc.get(s.workload_id) and an.get(wc[s.workload_id].group_id,'').endswith('-23'))

        print(f'\n=== SUMMARY ===')
        print(f'4c: {c4} | 2c: {c2} | 3c: {c3} | Total: {len(all_s)} | Gaps: {tg} | Conflicts: {cc}')

        print('\nSaving...')
        for s in all_s:
            db.session.add(s)
        db.session.commit()
        print('DONE!')


if __name__ == '__main__':
    main()
