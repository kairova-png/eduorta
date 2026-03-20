#!/usr/bin/env python
"""Migrate CMK tables and re-populate with per-group RUPs + GUP data."""

import os
os.environ.setdefault('FLASK_ENV', 'development')

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import (
    User, CMKCommission, CMKMember, RUP, RUPD, UMK, UMKD,
    DocumentHistory, CMKMeeting,
    Teacher, Department, Specialty, AcademicYear, Workload, Group, GUP
)
from datetime import datetime, date
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print("=== CMK Migration & Data Population ===\n")

    # 1. Drop CMK tables and recreate
    cmk_tables = [
        'document_history', 'cmk_meetings', 'umkd_documents', 'umk_documents',
        'rupd_documents', 'rup_documents', 'cmk_members', 'cmk_commissions', 'users'
    ]

    print("1. Dropping old CMK tables...")
    with db.engine.connect() as conn:
        for table_name in cmk_tables:
            try:
                conn.execute(db.text(f'DROP TABLE IF EXISTS {table_name}'))
                print(f"   Dropped: {table_name}")
            except Exception as e:
                print(f"   Skip {table_name}: {e}")
        conn.commit()

    print("\n2. Creating all tables...")
    db.create_all()
    print("   Done.")

    # 3. Get existing data stats
    departments = Department.query.all()
    specialties = Specialty.query.all()
    groups = Group.query.order_by(Group.name).all()
    teachers = Teacher.query.all()
    years = AcademicYear.query.all()
    current_year = AcademicYear.query.filter_by(is_current=True).first() or (years[0] if years else None)

    print(f"\n3. Existing data:")
    print(f"   Departments: {len(departments)}")
    print(f"   Specialties: {len(specialties)}")
    print(f"   Groups: {len(groups)}")
    print(f"   Teachers: {len(teachers)}")
    print(f"   Academic years: {len(years)}")
    print(f"   Current year: {current_year.name if current_year else 'None'}")

    # 4. Create admin user
    print("\n4. Creating users...")
    admin = User(
        username='admin',
        full_name='Администратор системы',
        role='admin',
        is_active=True
    )
    admin.set_password('admin123')
    db.session.add(admin)
    db.session.flush()
    print(f"   Admin: admin / admin123 (id={admin.id})")

    # Create chair users per department
    chair_users = []
    for i, dept in enumerate(departments):
        # Find a teacher from this department to be chair
        dept_teacher = Teacher.query.filter_by(department_id=dept.id).first()
        chair = User(
            username=f'chair_{dept.code or dept.id}',
            full_name=f'Председатель ЦМК {dept.name_ru}',
            role='cmk_chair',
            teacher_id=dept_teacher.id if dept_teacher else None,
            is_active=True
        )
        chair.set_password('chair123')
        db.session.add(chair)
        chair_users.append((chair, dept))

    db.session.flush()
    print(f"   Created {len(chair_users)} chair users")

    # Create teacher users (one per teacher who has workload)
    teacher_ids_with_workload = db.session.query(Workload.teacher_id).distinct().all()
    teacher_ids_with_workload = [t[0] for t in teacher_ids_with_workload]

    teacher_users = {}
    for tid in teacher_ids_with_workload:
        teacher = Teacher.query.get(tid)
        if not teacher:
            continue
        # Generate username from name
        name_parts = teacher.full_name.split()
        username = f't_{tid}'

        tuser = User(
            username=username,
            full_name=teacher.full_name,
            role='teacher',
            teacher_id=tid,
            is_active=True
        )
        tuser.set_password('teacher123')
        db.session.add(tuser)
        teacher_users[tid] = tuser

    db.session.flush()
    print(f"   Created {len(teacher_users)} teacher users")

    # 5. Create CMK Commissions (one per department)
    print("\n5. Creating commissions...")
    commissions = {}
    for chair_user, dept in chair_users:
        commission = CMKCommission(
            name=f'ЦМК {dept.name_ru}',
            department_id=dept.id,
            chair_id=chair_user.id,
            academic_year_id=current_year.id if current_year else None,
            description=f'Цикловая методическая комиссия отделения "{dept.name_ru}"'
        )
        db.session.add(commission)
        commissions[dept.id] = commission

    db.session.flush()
    print(f"   Created {len(commissions)} commissions")

    # Add members to commissions
    for tid, tuser in teacher_users.items():
        teacher = Teacher.query.get(tid)
        if teacher and teacher.department_id in commissions:
            member = CMKMember(
                commission_id=commissions[teacher.department_id].id,
                user_id=tuser.id,
                role_in_commission='member'
            )
            db.session.add(member)

    db.session.flush()
    print("   Added members to commissions")

    # 6. Create RUPs - one per group that has workload
    print("\n6. Creating RUPs (per group)...")

    groups_with_workload = db.session.query(Workload.group_id).distinct().all()
    groups_with_workload = [g[0] for g in groups_with_workload]

    rup_count = 0
    rupd_count = 0
    umk_count = 0
    umkd_count = 0

    for group_id in groups_with_workload:
        group = Group.query.get(group_id)
        if not group:
            continue

        # Determine commission for this group (by specialty -> department)
        dept_id = None
        if group.specialty and group.specialty.department_id:
            dept_id = group.specialty.department_id

        if dept_id not in commissions:
            # Use first commission as fallback
            dept_id = list(commissions.keys())[0] if commissions else None

        if dept_id is None:
            continue

        commission = commissions[dept_id]
        academic_year_id = current_year.id if current_year else years[0].id

        # Get workloads for this group
        workloads = Workload.query.filter_by(
            group_id=group_id, academic_year_id=academic_year_id
        ).order_by(Workload.semester, Workload.discipline).all()

        if not workloads:
            continue

        # Generate RUP content
        specialty = group.specialty
        year_obj = AcademicYear.query.get(academic_year_id)

        # Build content HTML
        html = f'<h2>Рабочий учебный план</h2>'
        html += f'<p><strong>Группа:</strong> {group.name}</p>'
        html += f'<p><strong>Специальность:</strong> {specialty.code if specialty else ""} — {specialty.name_ru if specialty else ""}</p>'
        html += f'<p><strong>Курс:</strong> {group.course}</p>'
        html += f'<p><strong>Год поступления:</strong> {group.enrollment_year}</p>'
        html += f'<p><strong>Учебный год:</strong> {year_obj.name if year_obj else ""}</p>'

        total_disciplines = len(set(w.discipline for w in workloads))
        total_hours = sum(w.total_hours for w in workloads)
        html += f'<p><strong>Всего дисциплин:</strong> {total_disciplines}</p>'
        html += f'<p><strong>Общая нагрузка:</strong> {total_hours} часов</p>'
        html += '<hr>'

        semesters = {}
        for w in workloads:
            semesters.setdefault(w.semester, []).append(w)

        lesson_types = {'theory': 'Теория', 'practice': 'Практика', 'consultation': 'Конс.', 'exam': 'Экзамен'}

        for sem in sorted(semesters.keys()):
            sw = semesters[sem]
            sem_total = sum(w.total_hours for w in sw)
            html += f'<h3>Семестр {sem}</h3>'
            html += '<table border="1" cellpadding="5" style="width:100%;border-collapse:collapse;">'
            html += '<tr style="background:#eee;"><th>№</th><th>Дисциплина</th><th>Преподаватель</th>'
            html += '<th>Тип</th><th>Всего часов</th><th>Ч/нед</th></tr>'
            for i, w in enumerate(sw, 1):
                html += f'<tr><td>{i}</td><td>{w.discipline}</td>'
                html += f'<td>{w.teacher.full_name if w.teacher else "—"}</td>'
                html += f'<td>{lesson_types.get(w.lesson_type, w.lesson_type)}</td>'
                html += f'<td>{w.total_hours}</td><td>{w.hours_per_week or "—"}</td></tr>'
            html += f'<tr style="background:#eee;font-weight:bold;"><td colspan="4">Итого</td><td>{sem_total}</td><td></td></tr>'
            html += '</table><br>'

        # Build GUP content
        gup_entries = GUP.query.filter_by(
            group_id=group_id, academic_year_id=academic_year_id
        ).order_by(GUP.week_number).all()

        gup_html = '<h2>График учебного процесса (ГУП)</h2>'
        gup_html += f'<p><strong>Группа:</strong> {group.name}</p>'

        if gup_entries:
            gup_html += '<table border="1" cellpadding="5" style="width:100%;border-collapse:collapse;">'
            gup_html += '<tr style="background:#eee;"><th>Неделя</th><th>Даты</th><th>Код</th><th>Вид деятельности</th></tr>'

            activity_colors = {
                'К': '#e7f3ff', 'П': '#fff3cd', 'ПП': '#e1f7fe',
                '::': '#fff4e6', '*': '#f8f9fa', 'Э': '#f8d7da',
            }
            study_weeks = 0
            for g in gup_entries:
                code = g.activity_code or ''
                name = g.activity_name or 'Учебные занятия'
                color = activity_colors.get(code, '#ffffff')
                dates = ''
                if g.start_date and g.end_date:
                    dates = f'{g.start_date.strftime("%d.%m")} - {g.end_date.strftime("%d.%m")}'
                gup_html += f'<tr style="background:{color};"><td>{g.week_number}</td>'
                gup_html += f'<td>{dates}</td><td><strong>{code}</strong></td><td>{name}</td></tr>'
                if g.needs_schedule:
                    study_weeks += 1

            gup_html += '</table>'
            gup_html += f'<p><strong>Учебных недель:</strong> {study_weeks} из {len(gup_entries)}</p>'
        else:
            gup_html += '<p>Нет данных ГУП</p>'

        # Create RUP
        rup = RUP(
            commission_id=commission.id,
            group_id=group_id,
            specialty_id=group.specialty_id,
            academic_year_id=academic_year_id,
            enrollment_year=group.enrollment_year,
            title=f'РУП {group.name} ({group.enrollment_year} г.п.)',
            content=html,
            gup_content=gup_html,
            status='draft',
            created_by_id=admin.id
        )
        db.session.add(rup)
        db.session.flush()
        rup_count += 1

        # Create RUPD for each discipline+teacher
        seen_disciplines = set()
        for w in workloads:
            key = (w.discipline, w.teacher_id)
            if key in seen_disciplines:
                continue
            seen_disciplines.add(key)

            creator_id = teacher_users.get(w.teacher_id, admin).id if w.teacher_id in teacher_users else admin.id

            rupd = RUPD(
                rup_id=rup.id,
                discipline=w.discipline,
                teacher_id=w.teacher_id,
                goals=f'<p><strong>Дисциплина:</strong> {w.discipline}</p>'
                      f'<p><strong>Преподаватель:</strong> {w.teacher.full_name if w.teacher else ""}</p>'
                      f'<p><strong>Группа:</strong> {group.name}</p>'
                      f'<p><strong>Семестр:</strong> {w.semester}</p>'
                      f'<p><strong>Всего часов:</strong> {w.total_hours}</p>'
                      f'<p><strong>Часов/нед:</strong> {w.hours_per_week or "—"}</p>',
                created_by_id=creator_id
            )
            db.session.add(rupd)
            rupd_count += 1

        # Create UMK for this RUP
        umk = UMK(
            rup_id=rup.id,
            title=f'УМК {group.name}',
            content=f'<h2>Учебно-методический комплекс</h2>'
                    f'<p><strong>Группа:</strong> {group.name}</p>'
                    f'<p><strong>Специальность:</strong> {specialty.code if specialty else ""} — {specialty.name_ru if specialty else ""}</p>',
            created_by_id=admin.id
        )
        db.session.add(umk)
        db.session.flush()
        umk_count += 1

        # Create UMKD for each discipline+teacher
        seen_umkd = set()
        for w in workloads:
            key = (w.discipline, w.teacher_id)
            if key in seen_umkd:
                continue
            seen_umkd.add(key)

            creator_id = teacher_users.get(w.teacher_id, admin).id if w.teacher_id in teacher_users else admin.id

            # Find matching RUPD
            matching_rupd = RUPD.query.filter_by(
                rup_id=rup.id, discipline=w.discipline, teacher_id=w.teacher_id
            ).first()

            umkd = UMKD(
                umk_id=umk.id,
                rupd_id=matching_rupd.id if matching_rupd else None,
                discipline=w.discipline,
                teacher_id=w.teacher_id,
                syllabus=f'<p>Силлабус дисциплины "{w.discipline}"</p>',
                created_by_id=creator_id
            )
            db.session.add(umkd)
            umkd_count += 1

    # 7. Create meetings
    print("\n7. Creating sample meetings...")
    meeting_count = 0
    for dept_id, commission in commissions.items():
        for i in range(1, 3):
            meeting = CMKMeeting(
                commission_id=commission.id,
                meeting_number=i,
                meeting_date=date(2025, 9 + i, 15),
                title=f'Заседание ЦМК №{i}',
                agenda=f'<p>Повестка заседания №{i}</p>',
                protocol=f'<p>Протокол заседания №{i}</p>',
                decisions=f'<p>Решения заседания №{i}</p>',
                created_by_id=admin.id
            )
            db.session.add(meeting)
            meeting_count += 1

    # 8. Log actions
    print("\n8. Creating document history...")
    db.session.flush()

    for rup in RUP.query.all():
        hist = DocumentHistory(
            document_type='rup',
            document_id=rup.id,
            action='created',
            new_status='draft',
            user_id=admin.id
        )
        db.session.add(hist)

    # Commit everything
    db.session.commit()

    print("\n=== DONE ===")
    print(f"   Users: {User.query.count()} (1 admin + {len(chair_users)} chairs + {len(teacher_users)} teachers)")
    print(f"   Commissions: {len(commissions)}")
    print(f"   RUPs: {rup_count}")
    print(f"   RUPDs: {rupd_count}")
    print(f"   UMKs: {umk_count}")
    print(f"   UMKDs: {umkd_count}")
    print(f"   Meetings: {meeting_count}")
    print(f"\n   Login: admin / admin123")
    print(f"   Chair login: chair_<dept_code> / chair123")
    print(f"   Teacher login: t_<teacher_id> / teacher123")
