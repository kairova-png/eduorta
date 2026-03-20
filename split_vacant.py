"""Split Вакант into separate teachers per group to avoid conflicts."""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from collections import defaultdict
from app import create_app, db
from app.models import Workload, Group, Teacher

app = create_app()

with app.app_context():
    vacant = Teacher.query.filter_by(full_name='Вакант').first()
    print(f'Original Вакант id={vacant.id}')

    # Get all vacant workloads grouped by group name
    wls = Workload.query.filter_by(teacher_id=vacant.id).all()
    by_group = defaultdict(list)
    for wl in wls:
        gname = wl.group.name if wl.group else '?'
        by_group[gname].append(wl)

    groups_sorted = sorted(by_group.keys())
    print(f'Groups with vacant workloads: {groups_sorted}')

    # Keep original Вакант for the first group, create new ones for the rest
    # Assign: first group keeps Вакант (id=83)
    first_group = groups_sorted[0]
    print(f'\n{first_group}: keeping Вакант (id={vacant.id})')

    vacant_counter = 1
    for gname in groups_sorted[1:]:
        new_name = f'Вакант {vacant_counter}'
        # Check if already exists
        existing = Teacher.query.filter_by(full_name=new_name).first()
        if existing:
            new_teacher = existing
            print(f'{gname}: reusing {new_name} (id={existing.id})')
        else:
            new_teacher = Teacher(full_name=new_name)
            db.session.add(new_teacher)
            db.session.flush()  # get the id
            print(f'{gname}: created {new_name} (id={new_teacher.id})')

        # Reassign workloads
        for wl in by_group[gname]:
            wl.teacher_id = new_teacher.id
            print(f'  reassigned wl.id={wl.id} -> {new_name}')

        vacant_counter += 1

    db.session.commit()
    print('\nDone! All vacant workloads split.')

    # Verify
    print('\n=== Verification ===')
    all_vacants = Teacher.query.filter(Teacher.full_name.like('Вакант%')).all()
    for v in all_vacants:
        wl_count = Workload.query.filter_by(teacher_id=v.id).count()
        print(f'{v.full_name} (id={v.id}): {wl_count} workloads')
