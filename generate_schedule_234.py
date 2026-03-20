"""
Schedule Generator v3 for courses 2, 3, 4
Strategy:
  1. Build per-group templates WITHOUT global teacher locks
  2. Generate week-by-week, resolving teacher conflicts dynamically
  3. Unplaced pairs get retried on empty slots of that week
"""
import sqlite3, math, sys
from datetime import datetime, timedelta
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
DB_PATH = 'instance/college.db'
DAYS = 5
DAY_RU = {0:'Пн',1:'Вт',2:'Ср',3:'Чт',4:'Пт'}

# ── CONFIG ────────────────────────────────────────────────
C2_START = datetime(2026,2,2); C2_WEEKS = 19; C2_PAIRS = [4,5,6,7]
C2_EXPLICIT = {144:8, 54:4, 48:4, 36:2, 24:2}

C3_GROUPS = {
    'АиУ 1-23':(datetime(2026,3,16),13,468),'АиУ 2-23':(datetime(2026,3,16),13,468),
    'АиУ 3-23':(datetime(2026,3,16),13,468),'БНГС 1-23':(datetime(2026,3,9),14,504),
    'МЕХ 1-23':(datetime(2026,3,23),12,432),'МЕХ 2-23':(datetime(2026,3,23),12,432),
    'ПО 1-23':(datetime(2026,3,23),12,432),'ПО 2-23':(datetime(2026,3,23),12,432),
    'ПО 3-23':(datetime(2026,3,23),12,432),'ПО 4-23':(datetime(2026,3,23),12,432),
    'ТДНГ 1-23':(datetime(2026,3,16),13,468),
    'ХТП 1-23':(datetime(2026,3,9),14,504),'ХТП 2-23':(datetime(2026,3,9),14,504),
    'ХТП 3-23':(datetime(2026,3,9),14,504),'ЭНГМ 1-23':(datetime(2026,3,16),13,468),
    'ЭС 1-23':(datetime(2026,3,9),14,504),'ЭС 2-23':(datetime(2026,3,9),14,504),
}
C3_PAIRS = [4,5,6,7]
C3_EXPLICIT = {144:12,132:10,72:6,54:4,48:4,36:2,24:2}

C4_GROUPS = {
    'ЭС 1-22':(datetime(2026,2,2),7,252),'ЭС 2-22':(datetime(2026,2,2),7,252),
    'АиУ 1-22':(datetime(2026,2,2),7,252),'АиУ 2-22':(datetime(2026,2,2),7,252),
    'ХТП 1-22':(datetime(2026,2,2),9,324),'ХТП 2-22':(datetime(2026,2,2),9,324),
    'ХТП 3-22':(datetime(2026,2,2),9,324),'ПО 1-22':(datetime(2026,2,2),9,324),
    'ПО 2-22':(datetime(2026,2,2),9,324),'ПО 3-22':(datetime(2026,2,2),9,324),
    'ЭНГМ 1-22':(datetime(2026,2,2),9,324),'ЭНГМ 2-22':(datetime(2026,2,2),9,324),
    'ТДНГ 1-22':(datetime(2026,2,2),9,324),'БНГС 1-22':(datetime(2026,2,2),9,324),
    'МЕХ 1-22':(datetime(2026,2,2),10,360),'МЕХ 2-22':(datetime(2026,2,2),10,360),
}
C4_PAIRS = [1,2,3,4]

ES_HPW = {'Модули OPITO':22,'Современные технологии в энергетике':12}

# ── TEACHER CONSTRAINTS ───────────────────────────────────
def build_tc():
    tc = defaultdict(set)
    for d in range(5): tc['Романов Б.'].add((d,7))
    for d in range(5): tc['Кадргалиева А.'].add((d,7))
    for p in [5,6]: tc['Темирханова Г.'].add((0,p)); tc['Темирханова Г.'].add((1,p))
    for p in [5,6,7]: tc['Кайыров А.'].add((4,p))
    for d in range(5): tc['Рахым К.'].add((d,7))
    return tc
TC = build_tc()

def teacher_blocked(tname, day, pair, course):
    if not tname: return False
    if (day,pair) in TC.get(tname, set()): return True
    if 'Сулеймен' in tname:
        if course == 4 and pair not in (3,4): return True
        if course in (2,3) and pair != 7: return True
    return False

# ── HELPERS ───────────────────────────────────────────────
def ceil_even(v):
    r = math.ceil(v)
    if r%2: r+=1
    return max(r,2)

def get_hpw(h, course, weeks, gname, disc):
    if h<=2: return 0
    if course==2:
        return C2_EXPLICIT.get(h, ceil_even(h/C2_WEEKS))
    if course==3:
        return C3_EXPLICIT.get(h, ceil_even(h/weeks))
    if course==4:
        if gname in ('ЭС 1-22','ЭС 2-22'):
            if disc in ES_HPW: return ES_HPW[disc]
            if 'Физическая культура' in disc: return 4
        if 'Физическая культура' in disc: return 2
        return ceil_even(h/weeks)
    return 0

# ── TEMPLATE BUILDER (per group, no global locks) ─────────
def build_template(workloads, pairs, course, gname):
    np_ = len(pairs)
    max_slots = DAYS * np_
    active = [(w, w['hpw']//2) for w in workloads if w['hpw']>0]
    if not active: return []

    total_ppw = sum(p for _,p in active)
    nd = len(active)

    # Dynamic max_per_day
    if total_ppw <= nd * DAYS:
        mpd_default = 1
    elif total_ppw <= nd * DAYS * 2:
        mpd_default = 2
    else:
        mpd_default = 3

    # Cap at max_slots
    if total_ppw > max_slots:
        active.sort(key=lambda x: x[0]['hours'])
        over = total_ppw - max_slots
        for i in range(len(active)):
            w, ppw = active[i]
            if over<=0: break
            red = min(over, ppw-1)
            if red>0: active[i]=(w,ppw-red); over-=red

    active.sort(key=lambda x: -x[1])
    grid = [[None]*np_ for _ in range(DAYS)]
    dpd = defaultdict(lambda: defaultdict(int))
    tmpl = []

    for w, ppw in active:
        t = w.get('teacher','')
        mpd = max(mpd_default, math.ceil(ppw/DAYS)) if ppw > DAYS else mpd_default
        mpd = min(mpd, np_)
        placed = 0
        base = ppw//DAYS; extra = ppw%DAYS

        for d in range(DAYS):
            tgt = base + (1 if d < extra else 0)
            for _ in range(tgt):
                if placed>=ppw: break
                if dpd[d][w['wid']]>=mpd: break
                for pi in range(np_):
                    if grid[d][pi] is not None: continue
                    pn = pairs[pi]
                    if teacher_blocked(t, d, pn, course): continue
                    grid[d][pi] = w; dpd[d][w['wid']]+=1
                    tmpl.append((d,pn,w)); placed+=1; break
                else: continue
                break  # inner break was hit

        # Retry on any remaining slot
        if placed < ppw:
            for d in range(DAYS):
                for pi in range(np_):
                    if placed>=ppw: break
                    if grid[d][pi] is not None: continue
                    if dpd[d][w['wid']]>=mpd: break
                    pn = pairs[pi]
                    if teacher_blocked(t, d, pn, course): continue
                    grid[d][pi]=w; dpd[d][w['wid']]+=1
                    tmpl.append((d,pn,w)); placed+=1

        if placed<ppw:
            print(f"  WARN tmpl: {gname} placed {placed}/{ppw} for {w['discipline'][:45]}")

    return tmpl

# ── MAIN ──────────────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('''SELECT g.id gid, g.name gn, g.enrollment_year ey,
                        w.id wid, w.discipline disc, w.total_hours th,
                        t.id tid, t.full_name tn
                 FROM workload w JOIN groups g ON w.group_id=g.id
                 LEFT JOIN teachers t ON w.teacher_id=t.id
                 WHERE g.enrollment_year IN (2022,2023,2024)
                 ORDER BY g.name, w.total_hours DESC''')

    gd = {}
    for r in c.fetchall():
        gn = r['gn']; co = 2025 - r['ey'] + 1
        if gn not in gd: gd[gn] = {'gid':r['gid'],'course':co,'wl':[]}
        gd[gn]['wl'].append({'wid':r['wid'],'discipline':r['disc'],
                             'hours':r['th'],'teacher':r['tn'],'teacher_id':r['tid']})

    # Phase 1: Build templates
    templates = {}  # gname -> (template, config)
    for gn, g in sorted(gd.items()):
        co = g['course']
        if co==2:
            sd,nw,ps = C2_START,C2_WEEKS,C2_PAIRS
        elif co==3:
            if gn not in C3_GROUPS: continue
            sd,nw,_ = C3_GROUPS[gn]; ps=C3_PAIRS
        elif co==4:
            if gn not in C4_GROUPS: continue
            sd,nw,_ = C4_GROUPS[gn]; ps=C4_PAIRS
        else: continue

        for w in g['wl']:
            w['hpw'] = get_hpw(w['hours'],co,nw,gn,w['discipline'])

        tmpl = build_template(g['wl'],ps,co,gn)
        # Align start to Monday
        s = sd
        while s.weekday()!=0: s-=timedelta(days=1)
        templates[gn] = (tmpl, s, nw, co, g['wl'])

        active = [w for w in g['wl'] if w['hpw']>0]
        print(f"{gn} (к{co}): {len(tmpl)} pairs/wk = {len(tmpl)*2}h, "
              f"{len(active)} дисц., target {sum(w['hours'] for w in active)}h")

    # Phase 2: Generate week-by-week with conflict resolution
    print(f"\n{'='*60}\nPhase 2: Generating entries with conflict resolution...\n")

    all_entries = []
    remaining = {}  # wid -> hours remaining
    for gn, (tmpl, sd, nw, co, wl) in templates.items():
        for w in wl:
            if w['hpw']>0:
                remaining[w['wid']] = w['hours']

    # Collect all (date, entries) across all groups
    # Process week by week, date by date
    # For each date+pair, only one teacher can be assigned

    # First, generate all desired entries
    desired = []  # (date_str, day_idx, pair_num, wid, tid, gname, course)
    for gn, (tmpl, sd, nw, co, wl) in templates.items():
        for week in range(nw):
            monday = sd + timedelta(weeks=week)
            for di, pn, w in tmpl:
                if remaining.get(w['wid'],0) <= 0: continue
                dt = monday + timedelta(days=di)
                ds = dt.strftime('%Y-%m-%d')
                desired.append((ds, di, pn, w['wid'], w['teacher_id'],
                                gn, co, w))
                remaining[w['wid']] -= 2

    # Reset remaining
    for gn, (tmpl, sd, nw, co, wl) in templates.items():
        for w in wl:
            if w['hpw']>0:
                remaining[w['wid']] = w['hours']

    # Sort desired by date, then pair
    desired.sort(key=lambda x: (x[0], x[2]))

    # Process: accept entries, skip if teacher conflict
    teacher_used = defaultdict(set)  # (date_str, pair_num) -> set of teacher_ids
    group_used = defaultdict(set)    # (date_str, pair_num) -> set of group_names
    accepted = []
    rejected = []

    for ds, di, pn, wid, tid, gn, co, w in desired:
        if remaining.get(wid, 0) <= 0:
            continue

        # Check teacher conflict
        key = (ds, pn)
        if tid and tid in teacher_used[key]:
            rejected.append((ds, di, pn, wid, tid, gn, co, w))
            continue

        # Check group slot (same group can't have 2 entries at same time)
        gkey = (ds, pn, gn)
        if gn in group_used[key]:
            rejected.append((ds, di, pn, wid, tid, gn, co, w))
            continue

        # Accept
        if tid: teacher_used[key].add(tid)
        group_used[key].add(gn)
        remaining[wid] -= 2
        accepted.append({'workload_id':wid,'date':ds,'pair_number':pn,
                         'status':'planned','room_id':None})

    print(f"Accepted: {len(accepted)}, Rejected (conflicts): {len(rejected)}")

    # Phase 3: Try to place rejected entries in alternative slots
    # For each rejected entry, find a free slot on the same week
    rescheduled = 0
    for ds, di, pn, wid, tid, gn, co, w in rejected:
        if remaining.get(wid, 0) <= 0:
            continue

        # Get the Monday of this week
        dt = datetime.strptime(ds, '%Y-%m-%d')
        monday = dt - timedelta(days=dt.weekday())

        # Determine available pairs
        if co == 4:
            avail_pairs = C4_PAIRS
        else:
            avail_pairs = C2_PAIRS  # same for 2 and 3

        # Try each day+pair of this week
        placed = False
        for try_day in range(DAYS):
            for try_pair in avail_pairs:
                try_date = monday + timedelta(days=try_day)
                try_ds = try_date.strftime('%Y-%m-%d')
                tkey = (try_ds, try_pair)

                if tid and tid in teacher_used[tkey]:
                    continue
                if gn in group_used[tkey]:
                    continue
                if teacher_blocked(w.get('teacher',''), try_day, try_pair, co):
                    continue

                # Accept
                if tid: teacher_used[tkey].add(tid)
                group_used[tkey].add(gn)
                remaining[wid] -= 2
                accepted.append({'workload_id':wid,'date':try_ds,'pair_number':try_pair,
                                 'status':'planned','room_id':None})
                rescheduled += 1
                placed = True
                break
            if placed: break

    print(f"Rescheduled: {rescheduled} of {len(rejected)} rejected")

    # Stats per group
    print(f"\n{'='*60}")
    group_planned = defaultdict(int)
    group_target = defaultdict(int)
    for e in accepted:
        # Find group
        pass  # will check via DB

    total_hours = len(accepted) * 2
    total_target = sum(remaining.get(wid, 0) for wid in remaining)
    # Actually calculate from original
    orig_total = 0
    for gn, (tmpl, sd, nw, co, wl) in templates.items():
        for w in wl:
            if w['hpw']>0:
                orig_total += w['hours']

    leftover = sum(max(r,0) for r in remaining.values())
    print(f"SUMMARY")
    print(f"  Total entries: {len(accepted)}")
    print(f"  Total hours planned: {total_hours}")
    print(f"  Total hours target: {orig_total}")
    print(f"  Leftover: {leftover}h")
    print(f"  Coverage: {(orig_total-leftover)/orig_total*100:.1f}%")

    # Insert
    print(f"\nInserting {len(accepted)} entries...")
    inserted = dupes = 0
    for e in accepted:
        try:
            c.execute('INSERT INTO schedule (workload_id,date,pair_number,status,room_id) VALUES (?,?,?,?,?)',
                      (e['workload_id'],e['date'],e['pair_number'],e['status'],e['room_id']))
            inserted += 1
        except sqlite3.IntegrityError:
            dupes += 1
    conn.commit()
    print(f"  Inserted: {inserted}, Dupes: {dupes}")

    # Verify conflicts
    print(f"\nVerifying teacher conflicts...")
    c.execute('''
        SELECT t.full_name, s.date, s.pair_number, COUNT(*) as cnt
        FROM schedule s
        JOIN workload w ON s.workload_id = w.id
        JOIN groups g ON w.group_id = g.id
        JOIN teachers t ON w.teacher_id = t.id
        WHERE g.enrollment_year IN (2022,2023,2024)
        GROUP BY t.id, s.date, s.pair_number
        HAVING cnt > 1
        ORDER BY cnt DESC
        LIMIT 20
    ''')
    conflicts = c.fetchall()
    if conflicts:
        print(f"  {len(conflicts)} conflict slots found:")
        for r in conflicts:
            print(f"    {r[0]} | {r[1]} п{r[2]} | {r[3]} groups")
    else:
        print(f"  No conflicts!")

    # Per-group coverage
    print(f"\nPer-group coverage:")
    c.execute('''
        SELECT g.name, (2025 - g.enrollment_year + 1) as course,
               (SELECT SUM(w2.total_hours) FROM workload w2
                WHERE w2.group_id=g.id AND w2.total_hours>2) as target,
               COUNT(s.id)*2 as planned
        FROM schedule s
        JOIN workload w ON s.workload_id=w.id
        JOIN groups g ON w.group_id=g.id
        WHERE g.enrollment_year IN (2022,2023,2024)
        GROUP BY g.id
        ORDER BY (2025 - g.enrollment_year + 1), g.name
    ''')
    low_groups = []
    for r in c.fetchall():
        pct = r[3]/r[2]*100 if r[2] else 0
        mark = ' !' if pct < 95 else ''
        if pct < 95: low_groups.append(r[0])
        print(f"  {r[0]:>15} к{r[1]} | {r[2]:>5}h -> {r[3]:>5}h | {pct:>5.1f}%{mark}")

    if low_groups:
        print(f"\n  {len(low_groups)} groups below 95%")

    c.execute('''
        SELECT (2025 - g.enrollment_year + 1) as course, COUNT(s.id)
        FROM schedule s JOIN workload w ON s.workload_id=w.id
        JOIN groups g ON w.group_id=g.id
        GROUP BY course ORDER BY course
    ''')
    print(f"\nFinal by course:")
    for r in c.fetchall():
        print(f"  Course {r[0]}: {r[1]} entries")

    conn.close()
    print("\nDone!")

if __name__=='__main__':
    main()
