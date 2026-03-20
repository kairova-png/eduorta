import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('instance/college.db')
c = conn.cursor()

# ============================================================
# 1. Build teacher -> room mapping from PDF + corrections
# ============================================================
pdf_mapping = {
    # П9 1 этаж
    'Бекет А.':       ('П9', '101'),
    'Кабиден К.':     ('П9', '105'),
    'Ажгалиев М.':    ('П9', '109'),
    'Мурынов Б.':     ('П9', '110'),
    # П9 2 этаж
    'Темирханова Г.': ('П9', '201'),
    'Саржанова Э.':   ('П9', '202'),
    'Даулетова Э.':   ('П9', '203'),
    'Бағытова А.':    ('П9', '204'),
    'Кабиденова Г.':  ('П9', '205'),
    'Умарова Б.':     ('П9', '206'),
    'Убігалиева А.':  ('П9', '207'),
    'Даулетбаева Г.': ('П9', '208'),
    'Аяпбергенова О.':('П9', '209'),
    'Сырымбетова А.': ('П9', '211'),
    'Хайрушева Ж.':   ('П9', '212'),
    'Тулегенова К.':  ('П9', '213'),
    'Лян А.':         ('П9', '214'),
    'Султангалиева А.':('П9', '215'),
    # П9 3 этаж
    'Иманалиева Г.':  ('П9', '301'),
    'Наурзбекова А.': ('П9', '302'),
    'Калмен С.':      ('П9', '303'),
    'Максотұлы Д.':   ('П9', '306'),
    'Ізімова С.':     ('П9', '307'),
    'Романов Б.':     ('П9', '308'),
    'Рахым К.':       ('П9', '309'),
    'Кайыров А.':     ('П9', '312'),
    'Дауылбай А.':    ('П9', '313'),
    'Ихсанова Г.':    ('П9', '314'),
    'Амангалиева Г.': ('П9', '315'),
    # Мастерские
    'Багиткалиев А.': ('Мастерская', '17'),
    'Султанов Е.':    ('Мастерская', '20'),
    'Жолдыбаева А.':  ('Мастерская', '21'),
    'Измуканова А.':  ('Мастерская', '22'),
    'Утеш М.':        ('Мастерская', '24'),
    'Адилова А.':     ('Мастерская', '26'),
    'Мырзагалиева А.':('Мастерская', '28'),
    'Бимурзаев А.':   ('Мастерская', '30'),
    'Байгужиева М.':  ('Мастерская', '34'),
    # П10
    'Кабиров Х.':     ('П10', '201'),
    'Сагындыккызы Д.':('П10', '202'),
    'Өтеуов Д.':      ('П10', '203'),
    'Жолдаскалиева А.':('П10', '204'),
    'Куанышева А.':   ('П10', '205'),
    'Абсенова Б.':    ('П10', '206'),
    'Айбарұлы Г.':    ('П10', '207'),
    'Бексултан Ә.':   ('П10', '208'),
    'Саматова А.':    ('П10', '105'),
}

# ============================================================
# 2. Apply user corrections
# ============================================================
pdf_mapping['Ермеков Д.'] = ('П9', '111')
pdf_mapping['Махмутов Т.'] = ('П9', '216')
pdf_mapping['Елеусинов Е.'] = ('П9', '311')
pdf_mapping['Жумагалиев Н.'] = ('Мастерская', '23')
pdf_mapping['Даурешова Э.'] = ('П9', '310')
pdf_mapping['Сериккалиев А.'] = ('Мастерская', '18')
pdf_mapping['Кадргалиева А.'] = ('Мастерская', '2')
pdf_mapping['Омурсинова А.'] = ('Мастерская', '5')
pdf_mapping['Рахметуллаев Б.'] = ('П10', '304')
pdf_mapping['Сулеймен Ж.'] = ('Мастерская', '25')
pdf_mapping['Хаббасов Ж.'] = ('П9', '210')
pdf_mapping['Шакенова А.'] = ('П10', '108')
pdf_mapping['Базарбаева А.'] = ('П10', '315')
pdf_mapping['Берік А.'] = ('П9', '211')
pdf_mapping['Ибетова Г.'] = ('П10', '209')
pdf_mapping['Рыскалиева А.'] = ('П9', '210')
pdf_mapping['Кабдолла А.'] = ('П10', '311')
pdf_mapping['Ахпанбетова А.'] = ('П10', '209')

# Remove Бижанова (replaced by Махмутов Т. at 216)
if 'Бижанова С.' in pdf_mapping:
    del pdf_mapping['Бижанова С.']

# ============================================================
# 3. Build room_number -> room_id lookup
# ============================================================
rooms_db = c.execute('SELECT id, number FROM rooms').fetchall()
room_lookup = {}
for rid, rnum in rooms_db:
    room_lookup[rnum] = rid

# Create missing rooms if needed
all_needed_keys = set()
for tname, (building, room_num) in pdf_mapping.items():
    key = f'П10-{room_num}' if building == 'П10' else room_num
    all_needed_keys.add(key)

missing = [k for k in all_needed_keys if k not in room_lookup]
if missing:
    print(f"Creating {len(missing)} missing rooms: {missing}")
    for key in missing:
        c.execute("INSERT INTO rooms (number, room_type, capacity) VALUES (?, 'учебная', 30)", (key,))
        room_lookup[key] = c.lastrowid
    conn.commit()

# ============================================================
# 4. Map teacher names to DB teacher IDs
# ============================================================
teachers_db = c.execute('SELECT id, full_name FROM teachers').fetchall()
teacher_by_name = {t[1]: t[0] for t in teachers_db}

name_aliases = {
    'Бағытова А.': 'Багытова А.',
    'Убігалиева А.': 'Убигалиева А.',
    'Максотұлы Д.': 'Махсотов Д.',
    'Ізімова С.': 'Изимова С.',
    'Бексултан Ә.': 'Бексултан А.',
    'Наурзбекова А.': 'Наурызбекова А.',
}

def resolve_room_id(building, room_num):
    key = f'П10-{room_num}' if building == 'П10' else room_num
    return room_lookup.get(key)

def resolve_teacher_id(name):
    if name in teacher_by_name:
        return teacher_by_name[name]
    alias = name_aliases.get(name)
    if alias and alias in teacher_by_name:
        return teacher_by_name[alias]
    # Fuzzy match
    for db_name, db_id in teacher_by_name.items():
        parts_pdf = name.split()
        parts_db = db_name.split()
        if len(parts_pdf) >= 2 and len(parts_db) >= 2:
            if parts_pdf[0][:4] == parts_db[0][:4] and parts_pdf[-1][0] == parts_db[-1][0]:
                return db_id
    return None

# Build teacher_id -> room_id
teacher_room = {}
unmatched_teachers = []
unmatched_rooms = []

for tname, (building, room_num) in pdf_mapping.items():
    tid = resolve_teacher_id(tname)
    rid = resolve_room_id(building, room_num)
    if tid is None:
        unmatched_teachers.append(tname)
        continue
    if rid is None:
        unmatched_rooms.append((tname, building, room_num))
        continue
    teacher_room[tid] = rid

print(f'Mapped {len(teacher_room)} teachers to rooms')
if unmatched_teachers:
    print(f'Unmatched teachers: {unmatched_teachers}')
if unmatched_rooms:
    print(f'Unmatched rooms: {unmatched_rooms}')

# Show mapping
print('\nTeacher -> Room mapping:')
tid_to_name = {t[0]: t[1] for t in teachers_db}
for tid, rid in sorted(teacher_room.items(), key=lambda x: tid_to_name.get(x[0], '')):
    rnum = [k for k, v in room_lookup.items() if v == rid]
    print(f'  {tid_to_name.get(tid, "?")} -> {rnum[0] if rnum else "?"}')

# ============================================================
# 5. Физкультура -> Спортзал
# ============================================================
sport_room_id = room_lookup.get('Спортзал') or room_lookup.get('С/з')
print(f'\nСпортзал room_id: {sport_room_id}')

# ============================================================
# 6. Update schedule entries
# ============================================================
entries = c.execute('''
    SELECT s.id, w.teacher_id, w.discipline
    FROM schedule s
    JOIN workload w ON s.workload_id = w.id
    WHERE s.room_id IS NULL
''').fetchall()

print(f'\nSchedule entries without room: {len(entries)}')

updated = 0
sport_updated = 0
no_room = 0
no_room_teachers = {}

for sid, tid, disc in entries:
    disc_lower = disc.lower()
    if 'физ' in disc_lower and 'культ' in disc_lower:
        if sport_room_id:
            c.execute('UPDATE schedule SET room_id = ? WHERE id = ?', (sport_room_id, sid))
            sport_updated += 1
            updated += 1
            continue

    if tid in teacher_room:
        c.execute('UPDATE schedule SET room_id = ? WHERE id = ?', (teacher_room[tid], sid))
        updated += 1
    else:
        no_room += 1
        tname = tid_to_name.get(tid, f'id={tid}')
        no_room_teachers[tname] = no_room_teachers.get(tname, 0) + 1

conn.commit()

print(f'\nUpdated: {updated} entries')
print(f'  - Regular: {updated - sport_updated}')
print(f'  - Физкультура -> Спортзал: {sport_updated}')
print(f'No room mapping: {no_room} entries')
if no_room_teachers:
    print('Teachers without room:')
    for t, cnt in sorted(no_room_teachers.items()):
        print(f'  - {t}: {cnt} entries')

# Final stats
total = c.execute('SELECT COUNT(*) FROM schedule').fetchone()[0]
with_room = c.execute('SELECT COUNT(*) FROM schedule WHERE room_id IS NOT NULL').fetchone()[0]
print(f'\nFinal: {with_room}/{total} entries have rooms ({100*with_room/total:.1f}%)')

conn.close()
