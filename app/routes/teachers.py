from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Teacher, Department

bp = Blueprint('teachers', __name__, url_prefix='/teachers')


@bp.route('/')
def index():
    """List all teachers"""
    department_id = request.args.get('department_id', type=int)
    search = request.args.get('search', '')

    query = Teacher.query

    if department_id:
        query = query.filter_by(department_id=department_id)

    if search:
        query = query.filter(Teacher.full_name.ilike(f'%{search}%'))

    teachers = query.order_by(Teacher.full_name).all()
    departments = Department.query.order_by(Department.name_ru).all()

    return render_template('teachers/index.html',
                           teachers=teachers,
                           departments=departments,
                           selected_department=department_id,
                           search=search)


@bp.route('/<int:id>')
def view(id):
    """View teacher details and workload"""
    teacher = Teacher.query.get_or_404(id)
    return render_template('teachers/view.html', teacher=teacher)


@bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create new teacher"""
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        department_id = request.form.get('department_id', type=int)

        teacher = Teacher(
            full_name=full_name,
            department_id=department_id if department_id else None
        )
        db.session.add(teacher)
        db.session.commit()
        flash('Преподаватель добавлен', 'success')
        return redirect(url_for('teachers.index'))

    departments = Department.query.order_by(Department.name_ru).all()
    return render_template('teachers/form.html', teacher=None, departments=departments)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """Edit teacher"""
    teacher = Teacher.query.get_or_404(id)

    if request.method == 'POST':
        teacher.full_name = request.form.get('full_name')
        department_id = request.form.get('department_id', type=int)
        teacher.department_id = department_id if department_id else None

        db.session.commit()
        flash('Преподаватель обновлён', 'success')
        return redirect(url_for('teachers.index'))

    departments = Department.query.order_by(Department.name_ru).all()
    return render_template('teachers/form.html', teacher=teacher, departments=departments)


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """Delete teacher"""
    teacher = Teacher.query.get_or_404(id)
    db.session.delete(teacher)
    db.session.commit()
    flash('Преподаватель удалён', 'success')
    return redirect(url_for('teachers.index'))
