#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Пересоздание расписания Физкультуры для БНГС 1-25

Логика:
- Четверг, пара 1 - КАЖДУЮ неделю
- Понедельник, пара 3 - ЧЕРЕЗ НЕДЕЛЮ начиная с 21 недели (21, 23, 25...)
"""

import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
from app import create_app, db
from app.models import Schedule, Workload, Group, GUP, Room, WorkloadTemplate
import json

app = create_app()

GROUP_ID = 17  # БНГС 1-25
WORKLOAD_ID = 3  # Физическая культура
ACADEMIC_YEAR_ID = 1

def main():
    with app.app_context():
        # Получаем данные
        group = db.session.get(Group, GROUP_ID)
        workload = db.session.get(Workload, WORKLOAD_ID)

        print(f"Группа: {group.name}")
        print(f"Дисциплина: {workload.discipline}")
        print(f"Всего часов: {workload.total_hours}")
        print(f"Преподаватель: {workload.teacher.full_name}")

        # 1. УДАЛЯЕМ существующее расписание Физкультуры для БНГС 1-25
        print("\n=== ШАГ 1: Удаление старого расписания ===")
        old_schedules = Schedule.query.filter_by(workload_id=WORKLOAD_ID).all()
        deleted_count = len(old_schedules)

        for s in old_schedules:
            db.session.delete(s)

        db.session.commit()
        print(f"Удалено {deleted_count} записей")

        # 2. СОЗДАЁМ новое расписание
        print("\n=== ШАГ 2: Создание нового расписания ===")

        # Получаем недели 2 семестра (20+)
        gup_weeks = GUP.query.filter(
            GUP.group_id == GROUP_ID,
            GUP.academic_year_id == ACADEMIC_YEAR_ID,
            GUP.week_number >= 20
        ).order_by(GUP.week_number).all()

        # Фильтруем только недели с расписанием
        schedule_weeks = [w for w in gup_weeks if w.needs_schedule]
        print(f"Найдено {len(schedule_weeks)} недель для расписания")

        # Находим спортзал
        gym = Room.query.filter(Room.number.like('%порт%') | Room.number.like('%зал%') | Room.number == 'С').first()
        if not gym:
            gym = Room.query.first()  # Любая аудитория
        print(f"Аудитория: {gym.number if gym else 'Не найдена'}")

        created_count = 0
        total_hours = 0
        max_hours = workload.total_hours

        template_data = []  # Для обновления шаблона

        for week in schedule_weeks:
            if total_hours >= max_hours:
                print(f"Достигнут лимит часов ({max_hours})")
                break

            week_num = week.week_number
            week_start = week.start_date

            week_prefs = {}

            # Четверг (день 3), пара 1 - КАЖДУЮ неделю
            if total_hours < max_hours:
                thursday = week_start + timedelta(days=3)

                schedule = Schedule(
                    workload_id=WORKLOAD_ID,
                    room_id=gym.id if gym else None,
                    date=thursday,
                    pair_number=1,
                    status='planned'
                )
                db.session.add(schedule)
                created_count += 1
                total_hours += 2

                week_prefs['3'] = {'1': 'selected'}  # День 3, пара 1
                print(f"  Неделя {week_num}: Чт {thursday} пара 1 (+2ч, итого {total_hours}ч)")

            # Понедельник (день 0), пара 3 - ЧЕРЕЗ НЕДЕЛЮ начиная с 21
            # Нечётные недели: 21, 23, 25, 27...
            if week_num >= 21 and week_num % 2 == 1 and total_hours < max_hours:
                monday = week_start  # Понедельник = начало недели

                schedule = Schedule(
                    workload_id=WORKLOAD_ID,
                    room_id=gym.id if gym else None,
                    date=monday,
                    pair_number=3,
                    status='planned'
                )
                db.session.add(schedule)
                created_count += 1
                total_hours += 2

                week_prefs['0'] = {'3': 'selected'}  # День 0, пара 3
                print(f"  Неделя {week_num}: Пн {monday} пара 3 (+2ч, итого {total_hours}ч)")

            if week_prefs:
                template_data.append({
                    'week': week_num,
                    'preferences': week_prefs
                })

        db.session.commit()
        print(f"\nСоздано {created_count} записей расписания")
        print(f"Всего часов: {total_hours} из {max_hours}")

        # 3. ОБНОВЛЯЕМ шаблон
        print("\n=== ШАГ 3: Обновление шаблона ===")

        template = WorkloadTemplate.query.filter_by(
            workload_id=WORKLOAD_ID,
            group_id=GROUP_ID
        ).first()

        if template:
            template.distribution_json = json.dumps(template_data, ensure_ascii=False)
            template.name = f"{workload.discipline} - 2 семестр (Чт каждую + Пн через неделю)"
            db.session.commit()
            print(f"Шаблон обновлён: {template.name}")
        else:
            template = WorkloadTemplate(
                name=f"{workload.discipline} - 2 семестр (Чт каждую + Пн через неделю)",
                workload_id=WORKLOAD_ID,
                group_id=GROUP_ID,
                academic_year_id=ACADEMIC_YEAR_ID,
                semester=2,
                total_hours=workload.total_hours,
                distribution_json=json.dumps(template_data, ensure_ascii=False)
            )
            db.session.add(template)
            db.session.commit()
            print(f"Создан новый шаблон: {template.name}")

        # Обновляем hours_completed в workload
        workload.hours_completed = 0  # Сбрасываем, т.к. пары ещё не проведены
        db.session.commit()

        print("\n=== ГОТОВО! ===")
        print(f"Расписание Физкультуры для {group.name} пересоздано")
        print(f"Создано {created_count} пар ({total_hours} часов)")

if __name__ == '__main__':
    main()
