#!/usr/bin/env python
"""Create consultation and exam workloads for Kairov A."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Teacher, Group, Workload, Schedule, Room, AcademicYear
from datetime import date

app = create_app()

# Data for Kairov A.
KAIROV_DATA = [
    {
        'group': 'ПО 1-24',
        'discipline': 'БМ 02 Проектирование и анализ электрических схем и электронных устройств',
        'consultation': {'date': date(2026, 1, 12), 'time': '8:30', 'pair': 1, 'room': '312'},
        'exam': {'date': date(2026, 1, 14), 'time': '10:00', 'pair': 2, 'room': '111'}
    },
    {
        'group': 'ПО 2-24',
        'discipline': 'БМ 02 Проектирование и анализ электрических схем и электронных устройств',
        'consultation': {'date': date(2026, 1, 12), 'time': '10:00', 'pair': 2, 'room': '312'},
        'exam': {'date': date(2026, 1, 15), 'time': '10:00', 'pair': 2, 'room': '111'}
    },
    {
        'group': 'ПО 2-23',
        'discipline': 'ПМ 05 Создание отдельных элементов графического интерфейса',
        'consultation': {'date': date(2026, 1, 13), 'time': '8:30', 'pair': 1, 'room': '312'},
        'exam': {'date': date(2026, 1, 16), 'time': '9:00', 'pair': 1, 'room': '309'}
    }
]

def get_pair_from_time(time_str):
    """Convert time to pair number"""
    time_map = {
        '8:30': 1,
        '9:00': 1,
        '10:00': 2,
        '11:00': 3,
        '11:30': 3,
        '13:00': 4,
        '13:30': 4,
        '14:00': 4,
        '15:00': 5,
        '16:30': 6
    }
    return time_map.get(time_str, 1)

def main():
    with app.app_context():
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            print("ERROR: No current academic year found")
            return

        # Find or create teacher Kairov A.
        teacher = Teacher.query.filter(Teacher.full_name.ilike('%Кайыров%')).first()
        if not teacher:
            print("Teacher Kairov not found, creating...")
            teacher = Teacher(full_name='Кайыров А.')
            db.session.add(teacher)
            db.session.commit()
            print(f"Created teacher: {teacher.full_name} (ID: {teacher.id})")
        else:
            print(f"Found teacher: {teacher.full_name} (ID: {teacher.id})")

        created_workloads = []
        created_schedules = []

        for data in KAIROV_DATA:
            group_name = data['group']
            discipline = data['discipline']

            # Find group
            group = Group.query.filter_by(name=group_name).first()
            if not group:
                # Try alternative naming
                alt_names = [
                    group_name.replace(' ', ''),
                    group_name.replace('-', ' '),
                    group_name.replace('1-24', '1-24'),
                    group_name.replace('2-24', '2-24'),
                    group_name.replace('2-23', '2-23'),
                ]
                for alt in alt_names:
                    group = Group.query.filter_by(name=alt).first()
                    if group:
                        break

            if not group:
                print(f"WARNING: Group '{group_name}' not found, skipping...")
                continue

            print(f"\nProcessing: {group.name}")

            # Determine semester based on group year
            if '24' in group_name:
                semester = 2  # 2nd semester for 2024 enrollment (2nd year)
            elif '23' in group_name:
                semester = 4  # 4th semester for 2023 enrollment (3rd year)
            else:
                semester = 2

            # Create CONSULTATION workload
            consult_workload = Workload.query.filter(
                Workload.group_id == group.id,
                Workload.teacher_id == teacher.id,
                Workload.discipline.ilike(f'%{discipline[:20]}%'),
                Workload.lesson_type == 'consultation'
            ).first()

            if not consult_workload:
                consult_workload = Workload(
                    teacher_id=teacher.id,
                    group_id=group.id,
                    academic_year_id=current_year.id,
                    discipline=discipline + ' (Консультация)',
                    lesson_type='consultation',
                    semester=semester,
                    total_hours=2,
                    hours_per_week=0
                )
                db.session.add(consult_workload)
                db.session.commit()
                created_workloads.append(f"Consultation: {group.name} - {discipline[:30]}...")
                print(f"  Created consultation workload (ID: {consult_workload.id})")
            else:
                print(f"  Consultation workload already exists (ID: {consult_workload.id})")

            # Create EXAM workload
            exam_workload = Workload.query.filter(
                Workload.group_id == group.id,
                Workload.teacher_id == teacher.id,
                Workload.discipline.ilike(f'%{discipline[:20]}%'),
                Workload.lesson_type == 'exam'
            ).first()

            if not exam_workload:
                exam_workload = Workload(
                    teacher_id=teacher.id,
                    group_id=group.id,
                    academic_year_id=current_year.id,
                    discipline=discipline + ' (Экзамен)',
                    lesson_type='exam',
                    semester=semester,
                    total_hours=2,
                    hours_per_week=0
                )
                db.session.add(exam_workload)
                db.session.commit()
                created_workloads.append(f"Exam: {group.name} - {discipline[:30]}...")
                print(f"  Created exam workload (ID: {exam_workload.id})")
            else:
                print(f"  Exam workload already exists (ID: {exam_workload.id})")

            # Find rooms
            consult_room_num = data['consultation']['room']
            exam_room_num = data['exam']['room']

            consult_room = Room.query.filter_by(number=consult_room_num).first()
            exam_room = Room.query.filter_by(number=exam_room_num).first()

            if not consult_room:
                print(f"  WARNING: Room {consult_room_num} not found for consultation")
            if not exam_room:
                print(f"  WARNING: Room {exam_room_num} not found for exam")

            # Create CONSULTATION schedule
            consult_date = data['consultation']['date']
            consult_pair = get_pair_from_time(data['consultation']['time'])

            existing_consult = Schedule.query.filter_by(
                workload_id=consult_workload.id,
                date=consult_date,
                pair_number=consult_pair
            ).first()

            if not existing_consult:
                consult_schedule = Schedule(
                    workload_id=consult_workload.id,
                    date=consult_date,
                    pair_number=consult_pair,
                    room_id=consult_room.id if consult_room else None,
                    status='scheduled'
                )
                db.session.add(consult_schedule)
                created_schedules.append(f"Consult: {group.name} {consult_date} pair {consult_pair}")
                print(f"  Created consultation schedule: {consult_date} pair {consult_pair}")
            else:
                print(f"  Consultation schedule already exists")

            # Create EXAM schedule
            exam_date = data['exam']['date']
            exam_pair = get_pair_from_time(data['exam']['time'])

            existing_exam = Schedule.query.filter_by(
                workload_id=exam_workload.id,
                date=exam_date,
                pair_number=exam_pair
            ).first()

            if not existing_exam:
                exam_schedule = Schedule(
                    workload_id=exam_workload.id,
                    date=exam_date,
                    pair_number=exam_pair,
                    room_id=exam_room.id if exam_room else None,
                    status='scheduled'
                )
                db.session.add(exam_schedule)
                created_schedules.append(f"Exam: {group.name} {exam_date} pair {exam_pair}")
                print(f"  Created exam schedule: {exam_date} pair {exam_pair}")
            else:
                print(f"  Exam schedule already exists")

            db.session.commit()

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"\nCreated workloads: {len(created_workloads)}")
        for w in created_workloads:
            print(f"  - {w}")

        print(f"\nCreated schedules: {len(created_schedules)}")
        for s in created_schedules:
            print(f"  - {s}")

        print("\nDone!")

if __name__ == "__main__":
    main()
