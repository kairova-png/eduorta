from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Group, Specialty

bp = Blueprint('groups', __name__, url_prefix='/groups')


@bp.route('/')
def index():
    """List all groups"""
    specialty_id = request.args.get('specialty_id', type=int)
    course = request.args.get('course', type=int)

    query = Group.query

    if specialty_id:
        query = query.filter_by(specialty_id=specialty_id)

    groups = query.order_by(Group.name).all()

    if course:
        groups = [g for g in groups if g.course == course]

    specialties = Specialty.query.order_by(Specialty.code).all()

    return render_template('groups/index.html',
                           groups=groups,
                           specialties=specialties,
                           selected_specialty=specialty_id,
                           selected_course=course)


@bp.route('/<int:id>')
def view(id):
    """View group details"""
    group = Group.query.get_or_404(id)
    return render_template('groups/view.html', group=group)


@bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create new group"""
    if request.method == 'POST':
        name = request.form.get('name')
        specialty_id = request.form.get('specialty_id', type=int)
        group_number = request.form.get('group_number', type=int)
        enrollment_year = request.form.get('enrollment_year', type=int)

        shift = request.form.get('shift', 1, type=int)
        max_consecutive_pairs = request.form.get('max_consecutive_pairs', 2, type=int)

        if Group.query.filter_by(name=name).first():
            flash('Группа с таким названием уже существует', 'error')
        else:
            group = Group(
                name=name,
                specialty_id=specialty_id,
                group_number=group_number,
                enrollment_year=enrollment_year,
                shift=shift,
                max_consecutive_pairs=max_consecutive_pairs
            )
            db.session.add(group)
            db.session.commit()
            flash('Группа создана', 'success')
            return redirect(url_for('groups.index'))

    specialties = Specialty.query.order_by(Specialty.code).all()
    return render_template('groups/form.html', group=None, specialties=specialties)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """Edit group"""
    group = Group.query.get_or_404(id)

    if request.method == 'POST':
        group.name = request.form.get('name')
        group.specialty_id = request.form.get('specialty_id', type=int)
        group.group_number = request.form.get('group_number', type=int)
        group.enrollment_year = request.form.get('enrollment_year', type=int)
        group.shift = request.form.get('shift', 1, type=int)
        group.max_consecutive_pairs = request.form.get('max_consecutive_pairs', 2, type=int)

        db.session.commit()
        flash('Группа обновлена', 'success')
        return redirect(url_for('groups.index'))

    specialties = Specialty.query.order_by(Specialty.code).all()
    return render_template('groups/form.html', group=group, specialties=specialties)


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """Delete group"""
    group = Group.query.get_or_404(id)
    db.session.delete(group)
    db.session.commit()
    flash('Группа удалена', 'success')
    return redirect(url_for('groups.index'))
