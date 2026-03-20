"""Analyze generated schedule: gaps, weekly pairs, unplaced hours."""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from collections import defaultdict
from app import create_app, db
from app.models import Schedule, Workload, Group, Teacher

app = create_app()

with app.app_context():
    groups_2 = {g.id: g.name for g in Group.query.filter(Group.name.like('%-24')).all()}
    groups_3 = {g.id: g.name for g in Group.query.filter(Group.name.like('%-23')).all()}
    groups_4 = {g.id: g.name for g in Group.query.filter(Group.name.like('%-22')).all()}
    all_gids = set(list(groups_2.keys()) + list(groups_3.keys()) + list(groups_4.keys()))
    all_names = {**groups_2, **groups_3, **groups_4}

    teachers = {t.id: t.full_name for t in Teacher.query.all()}

    # Count scheduled pairs per workload
    scheduled = defaultdict(int)
    rows = db.session.query(
        Schedule.workload_id, db.func.count(Schedule.id)
    ).filter(
        Schedule.status.notin_(['cancelled', 'rescheduled'])
    ).group_by(Schedule.workload_id).all()
    for wl_id, cnt in rows:
        scheduled[wl_id] = cnt

    # Check all workloads for 2,3,4 courses
    workloads = Workload.query.filter(Workload.group_id.in_(all_gids)).all()

    print('=== UNPLACED HOURS ===')
    print()

    total_unplaced = 0
    unplaced_list = []

    for wl in workloads:
        total_pairs_needed = wl.total_hours // 2
        placed = scheduled.get(wl.id, 0)
        remaining = total_pairs_needed - placed
        if remaining > 0:
            gname = all_names.get(wl.group_id, '?')
            tname = teachers.get(wl.teacher_id, 'Vacant')
            unplaced_list.append((gname, wl.discipline, tname, wl.total_hours, placed * 2, remaining * 2))
            total_unplaced += remaining * 2

    # Sort by group, then remaining desc
    unplaced_list.sort(key=lambda x: (x[0], -x[5]))

    current_group = ''
    for gname, disc, tname, total, placed, remaining in unplaced_list:
        if gname != current_group:
            current_group = gname
            print(f'--- {gname} ---')
        print(f'  {disc[:50]:50s} | {tname[:20]:20s} | total={total:4d}h placed={placed:4d}h remain={remaining:4d}h')

    print()
    print(f'TOTAL UNPLACED: {total_unplaced} hours across {len(unplaced_list)} workloads')

    # Also show detail: groups with gaps
    print()
    print('=== GROUPS WITH GAPS (windows) ===')
    print()

    group_daily = defaultdict(lambda: defaultdict(list))
    scheds = db.session.query(
        Schedule.date, Schedule.pair_number, Workload.group_id
    ).join(Workload).filter(
        Workload.group_id.in_(all_gids),
        Schedule.status.notin_(['cancelled', 'rescheduled'])
    ).all()

    for date, pair, gid in scheds:
        group_daily[gid][date].append(pair)

    for course_name, gids in [('4 COURSE', groups_4), ('2 COURSE', groups_2), ('3 COURSE', groups_3)]:
        print(f'--- {course_name} ---')
        for gid in sorted(gids.keys(), key=lambda x: gids[x]):
            gname = gids[gid]
            days = group_daily[gid]
            gap_details = []

            for d in sorted(days.keys()):
                pairs = sorted(days[d])
                if len(pairs) <= 1:
                    continue
                min_p = min(pairs)
                max_p = max(pairs)
                gaps = [p for p in range(min_p, max_p + 1) if p not in pairs]
                if gaps:
                    gap_details.append(f'{d}: pairs={pairs} missing={gaps}')

            if gap_details:
                print(f'  {gname}: {len(gap_details)} days with gaps')
                for detail in gap_details[:5]:
                    print(f'    {detail}')
                if len(gap_details) > 5:
                    print(f'    ... and {len(gap_details) - 5} more')
        print()
