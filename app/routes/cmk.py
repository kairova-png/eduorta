from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from datetime import datetime
from app import db
from app.models import (User, CMKCommission, CMKMember, RUP, RUPD, UMK, UMKD,
                         DocumentHistory, CMKMeeting, Teacher, Department,
                         Specialty, AcademicYear)

bp = Blueprint('cmk', __name__, url_prefix='/cmk')


# ==================== Auth Helpers ====================

def get_current_user():
    user_id = session.get('cmk_user_id')
    if user_id:
        return User.query.get(user_id)
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash('Войдите в систему ЦМК', 'warning')
            return redirect(url_for('cmk.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect(url_for('cmk.login'))
            if user.role not in roles:
                flash('Недостаточно прав доступа', 'error')
                return redirect(url_for('cmk.dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def log_document_action(doc_type, doc_id, action, old_status=None, new_status=None, comment=None):
    user = get_current_user()
    history = DocumentHistory(
        document_type=doc_type,
        document_id=doc_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        comment=comment,
        user_id=user.id if user else 0
    )
    db.session.add(history)


# ==================== Context Processor ====================

@bp.app_context_processor
def inject_cmk_user():
    return dict(cmk_user=get_current_user())


# ==================== Auth Routes ====================

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if get_current_user():
        return redirect(url_for('cmk.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username, is_active=True).first()
        if user and user.check_password(password):
            session['cmk_user_id'] = user.id
            session['cmk_user_role'] = user.role
            session['cmk_user_name'] = user.full_name
            flash(f'Добро пожаловать, {user.full_name}!', 'success')
            return redirect(url_for('cmk.dashboard'))
        else:
            flash('Неверный логин или пароль', 'error')

    return render_template('cmk/login.html')


@bp.route('/logout')
def logout():
    session.pop('cmk_user_id', None)
    session.pop('cmk_user_role', None)
    session.pop('cmk_user_name', None)
    flash('Вы вышли из системы ЦМК', 'info')
    return redirect(url_for('cmk.login'))


# ==================== Dashboard ====================

@bp.route('/')
@login_required
def dashboard():
    user = get_current_user()
    commissions = CMKCommission.query.all()

    # Stats
    stats = {
        'total_rup': RUP.query.count(),
        'total_rupd': RUPD.query.count(),
        'total_umk': UMK.query.count(),
        'total_umkd': UMKD.query.count(),
        'pending_review': (
            RUP.query.filter_by(status='under_review').count() +
            RUPD.query.filter_by(status='under_review').count() +
            UMK.query.filter_by(status='under_review').count() +
            UMKD.query.filter_by(status='under_review').count()
        ),
        'approved': (
            RUP.query.filter_by(status='approved').count() +
            RUPD.query.filter_by(status='approved').count() +
            UMK.query.filter_by(status='approved').count() +
            UMKD.query.filter_by(status='approved').count()
        ),
    }

    # My documents (for teacher)
    my_docs = []
    if user.teacher_id:
        my_docs = RUPD.query.filter_by(teacher_id=user.teacher_id).all()

    return render_template('cmk/dashboard.html', commissions=commissions,
                           stats=stats, my_docs=my_docs)


# ==================== User Management ====================

@bp.route('/users')
@login_required
@role_required('admin')
def users_list():
    users = User.query.order_by(User.full_name).all()
    return render_template('cmk/users/index.html', users=users)


@bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def users_create():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'teacher')
        teacher_id = request.form.get('teacher_id', type=int)

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует', 'error')
        else:
            user = User(username=username, full_name=full_name, role=role,
                        teacher_id=teacher_id if teacher_id else None)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f'Пользователь {full_name} создан', 'success')
            return redirect(url_for('cmk.users_list'))

    teachers = Teacher.query.order_by(Teacher.full_name).all()
    return render_template('cmk/users/form.html', user=None, teachers=teachers)


@bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def users_edit(id):
    user = User.query.get_or_404(id)

    if request.method == 'POST':
        user.full_name = request.form.get('full_name', '').strip()
        user.role = request.form.get('role', 'teacher')
        user.teacher_id = request.form.get('teacher_id', type=int) or None
        user.is_active = 'is_active' in request.form

        new_password = request.form.get('password', '').strip()
        if new_password:
            user.set_password(new_password)

        db.session.commit()
        flash(f'Пользователь {user.full_name} обновлён', 'success')
        return redirect(url_for('cmk.users_list'))

    teachers = Teacher.query.order_by(Teacher.full_name).all()
    return render_template('cmk/users/form.html', user=user, teachers=teachers)


@bp.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def users_delete(id):
    user = User.query.get_or_404(id)
    current = get_current_user()
    if user.id == current.id:
        flash('Нельзя удалить самого себя', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'Пользователь {user.full_name} удалён', 'success')
    return redirect(url_for('cmk.users_list'))


# ==================== Commission Management ====================

@bp.route('/commissions')
@login_required
def commissions_list():
    commissions = CMKCommission.query.all()
    return render_template('cmk/commissions/index.html', commissions=commissions)


@bp.route('/commissions/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'cmk_chair')
def commissions_create():
    if request.method == 'POST':
        commission = CMKCommission(
            name=request.form.get('name', '').strip(),
            department_id=request.form.get('department_id', type=int) or None,
            chair_id=request.form.get('chair_id', type=int) or None,
            academic_year_id=request.form.get('academic_year_id', type=int) or None,
            description=request.form.get('description', '').strip()
        )
        db.session.add(commission)
        db.session.commit()
        flash(f'ЦМК "{commission.name}" создана', 'success')
        return redirect(url_for('cmk.commissions_view', id=commission.id))

    departments = Department.query.all()
    users = User.query.filter(User.role.in_(['admin', 'cmk_chair'])).all()
    years = AcademicYear.query.order_by(AcademicYear.id.desc()).all()
    return render_template('cmk/commissions/form.html', commission=None,
                           departments=departments, users=users, years=years)


@bp.route('/commissions/<int:id>')
@login_required
def commissions_view(id):
    commission = CMKCommission.query.get_or_404(id)
    return render_template('cmk/commissions/view.html', commission=commission)


@bp.route('/commissions/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'cmk_chair')
def commissions_edit(id):
    commission = CMKCommission.query.get_or_404(id)

    if request.method == 'POST':
        commission.name = request.form.get('name', '').strip()
        commission.department_id = request.form.get('department_id', type=int) or None
        commission.chair_id = request.form.get('chair_id', type=int) or None
        commission.academic_year_id = request.form.get('academic_year_id', type=int) or None
        commission.description = request.form.get('description', '').strip()
        db.session.commit()
        flash('ЦМК обновлена', 'success')
        return redirect(url_for('cmk.commissions_view', id=id))

    departments = Department.query.all()
    users = User.query.filter(User.role.in_(['admin', 'cmk_chair'])).all()
    years = AcademicYear.query.order_by(AcademicYear.id.desc()).all()
    return render_template('cmk/commissions/form.html', commission=commission,
                           departments=departments, users=users, years=years)


@bp.route('/commissions/<int:id>/add-member', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def commissions_add_member(id):
    commission = CMKCommission.query.get_or_404(id)
    user_id = request.form.get('user_id', type=int)
    role_in = request.form.get('role_in_commission', 'member')

    if user_id:
        existing = CMKMember.query.filter_by(commission_id=id, user_id=user_id).first()
        if existing:
            flash('Пользователь уже является членом ЦМК', 'warning')
        else:
            member = CMKMember(commission_id=id, user_id=user_id, role_in_commission=role_in)
            db.session.add(member)
            db.session.commit()
            flash('Член ЦМК добавлен', 'success')

    return redirect(url_for('cmk.commissions_view', id=id))


@bp.route('/commissions/<int:id>/remove-member/<int:member_id>', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def commissions_remove_member(id, member_id):
    member = CMKMember.query.get_or_404(member_id)
    db.session.delete(member)
    db.session.commit()
    flash('Член ЦМК удалён', 'success')
    return redirect(url_for('cmk.commissions_view', id=id))


# ==================== RUP ====================

@bp.route('/rup')
@login_required
def rup_list():
    rups = RUP.query.order_by(RUP.updated_at.desc()).all()
    return render_template('cmk/documents/rup_list.html', rups=rups)


@bp.route('/rup/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'cmk_chair')
def rup_create():
    user = get_current_user()
    if request.method == 'POST':
        rup = RUP(
            commission_id=request.form.get('commission_id', type=int),
            specialty_id=request.form.get('specialty_id', type=int),
            academic_year_id=request.form.get('academic_year_id', type=int),
            title=request.form.get('title', '').strip(),
            content=request.form.get('content', ''),
            created_by_id=user.id
        )
        db.session.add(rup)
        db.session.commit()
        log_document_action('rup', rup.id, 'created', new_status='draft')
        db.session.commit()
        flash('РУП создан', 'success')
        return redirect(url_for('cmk.rup_view', id=rup.id))

    commissions = CMKCommission.query.all()
    specialties = Specialty.query.all()
    years = AcademicYear.query.order_by(AcademicYear.id.desc()).all()
    return render_template('cmk/documents/rup_form.html', rup=None,
                           commissions=commissions, specialties=specialties, years=years)


@bp.route('/rup/<int:id>')
@login_required
def rup_view(id):
    rup = RUP.query.get_or_404(id)
    history = DocumentHistory.query.filter_by(document_type='rup', document_id=id)\
        .order_by(DocumentHistory.created_at.desc()).all()
    return render_template('cmk/documents/rup_view.html', rup=rup, history=history)


@bp.route('/rup/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def rup_edit(id):
    rup = RUP.query.get_or_404(id)
    user = get_current_user()

    if rup.status == 'approved' and not user.is_admin:
        flash('Утверждённый документ нельзя редактировать', 'error')
        return redirect(url_for('cmk.rup_view', id=id))

    if request.method == 'POST':
        rup.title = request.form.get('title', '').strip()
        rup.content = request.form.get('content', '')
        rup.commission_id = request.form.get('commission_id', type=int)
        rup.specialty_id = request.form.get('specialty_id', type=int)
        rup.academic_year_id = request.form.get('academic_year_id', type=int)
        log_document_action('rup', rup.id, 'updated')
        db.session.commit()
        flash('РУП обновлён', 'success')
        return redirect(url_for('cmk.rup_view', id=id))

    commissions = CMKCommission.query.all()
    specialties = Specialty.query.all()
    years = AcademicYear.query.order_by(AcademicYear.id.desc()).all()
    return render_template('cmk/documents/rup_form.html', rup=rup,
                           commissions=commissions, specialties=specialties, years=years)


@bp.route('/rup/<int:id>/submit', methods=['POST'])
@login_required
def rup_submit(id):
    rup = RUP.query.get_or_404(id)
    old = rup.status
    rup.status = 'under_review'
    log_document_action('rup', id, 'submitted', old, 'under_review')
    db.session.commit()
    flash('РУП отправлен на рассмотрение', 'success')
    return redirect(url_for('cmk.rup_view', id=id))


@bp.route('/rup/<int:id>/approve', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def rup_approve(id):
    rup = RUP.query.get_or_404(id)
    user = get_current_user()
    old = rup.status
    rup.status = 'approved'
    rup.approved_by_id = user.id
    rup.approved_at = datetime.utcnow()
    log_document_action('rup', id, 'approved', old, 'approved')
    db.session.commit()
    flash('РУП утверждён', 'success')
    return redirect(url_for('cmk.rup_view', id=id))


@bp.route('/rup/<int:id>/reject', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def rup_reject(id):
    rup = RUP.query.get_or_404(id)
    old = rup.status
    rup.status = 'revision'
    rup.review_comment = request.form.get('comment', '')
    log_document_action('rup', id, 'rejected', old, 'revision', rup.review_comment)
    db.session.commit()
    flash('РУП отправлен на доработку', 'warning')
    return redirect(url_for('cmk.rup_view', id=id))


# ==================== RUPD ====================

@bp.route('/rupd')
@login_required
def rupd_list():
    user = get_current_user()
    if user.is_chair:
        rupds = RUPD.query.order_by(RUPD.updated_at.desc()).all()
    else:
        rupds = RUPD.query.filter_by(teacher_id=user.teacher_id).order_by(RUPD.updated_at.desc()).all()
    return render_template('cmk/documents/rupd_list.html', rupds=rupds)


@bp.route('/rupd/create', methods=['GET', 'POST'])
@login_required
def rupd_create():
    user = get_current_user()
    if request.method == 'POST':
        rupd = RUPD(
            rup_id=request.form.get('rup_id', type=int),
            discipline=request.form.get('discipline', '').strip(),
            teacher_id=user.teacher_id or request.form.get('teacher_id', type=int),
            goals=request.form.get('goals', ''),
            competencies=request.form.get('competencies', ''),
            content_plan=request.form.get('content_plan', ''),
            literature=request.form.get('literature', ''),
            assessment=request.form.get('assessment', ''),
            extra_content=request.form.get('extra_content', ''),
            created_by_id=user.id
        )
        db.session.add(rupd)
        db.session.commit()
        log_document_action('rupd', rupd.id, 'created', new_status='draft')
        db.session.commit()
        flash('РУПД создан', 'success')
        return redirect(url_for('cmk.rupd_view', id=rupd.id))

    rups = RUP.query.all()
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    rup_id = request.args.get('rup_id', type=int)
    return render_template('cmk/documents/rupd_form.html', rupd=None,
                           rups=rups, teachers=teachers, preselect_rup_id=rup_id)


@bp.route('/rupd/<int:id>')
@login_required
def rupd_view(id):
    rupd = RUPD.query.get_or_404(id)
    history = DocumentHistory.query.filter_by(document_type='rupd', document_id=id)\
        .order_by(DocumentHistory.created_at.desc()).all()
    return render_template('cmk/documents/rupd_view.html', rupd=rupd, history=history)


@bp.route('/rupd/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def rupd_edit(id):
    rupd = RUPD.query.get_or_404(id)
    user = get_current_user()

    if rupd.status == 'approved' and not user.is_admin:
        flash('Утверждённый документ нельзя редактировать', 'error')
        return redirect(url_for('cmk.rupd_view', id=id))

    if not user.is_chair and rupd.teacher_id != user.teacher_id:
        flash('Вы можете редактировать только свои документы', 'error')
        return redirect(url_for('cmk.rupd_view', id=id))

    if request.method == 'POST':
        rupd.discipline = request.form.get('discipline', '').strip()
        rupd.goals = request.form.get('goals', '')
        rupd.competencies = request.form.get('competencies', '')
        rupd.content_plan = request.form.get('content_plan', '')
        rupd.literature = request.form.get('literature', '')
        rupd.assessment = request.form.get('assessment', '')
        rupd.extra_content = request.form.get('extra_content', '')
        log_document_action('rupd', rupd.id, 'updated')
        db.session.commit()
        flash('РУПД обновлён', 'success')
        return redirect(url_for('cmk.rupd_view', id=id))

    rups = RUP.query.all()
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    return render_template('cmk/documents/rupd_form.html', rupd=rupd,
                           rups=rups, teachers=teachers, preselect_rup_id=None)


@bp.route('/rupd/<int:id>/submit', methods=['POST'])
@login_required
def rupd_submit(id):
    rupd = RUPD.query.get_or_404(id)
    old = rupd.status
    rupd.status = 'under_review'
    log_document_action('rupd', id, 'submitted', old, 'under_review')
    db.session.commit()
    flash('РУПД отправлен на рассмотрение', 'success')
    return redirect(url_for('cmk.rupd_view', id=id))


@bp.route('/rupd/<int:id>/approve', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def rupd_approve(id):
    rupd = RUPD.query.get_or_404(id)
    user = get_current_user()
    old = rupd.status
    rupd.status = 'approved'
    rupd.approved_by_id = user.id
    rupd.approved_at = datetime.utcnow()
    log_document_action('rupd', id, 'approved', old, 'approved')
    db.session.commit()
    flash('РУПД утверждён', 'success')
    return redirect(url_for('cmk.rupd_view', id=id))


@bp.route('/rupd/<int:id>/reject', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def rupd_reject(id):
    rupd = RUPD.query.get_or_404(id)
    old = rupd.status
    rupd.status = 'revision'
    rupd.review_comment = request.form.get('comment', '')
    log_document_action('rupd', id, 'rejected', old, 'revision', rupd.review_comment)
    db.session.commit()
    flash('РУПД отправлен на доработку', 'warning')
    return redirect(url_for('cmk.rupd_view', id=id))


# ==================== UMK ====================

@bp.route('/umk')
@login_required
def umk_list():
    umks = UMK.query.order_by(UMK.updated_at.desc()).all()
    return render_template('cmk/documents/umk_list.html', umks=umks)


@bp.route('/umk/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'cmk_chair')
def umk_create():
    user = get_current_user()
    if request.method == 'POST':
        umk = UMK(
            rup_id=request.form.get('rup_id', type=int),
            title=request.form.get('title', '').strip(),
            content=request.form.get('content', ''),
            created_by_id=user.id
        )
        db.session.add(umk)
        db.session.commit()
        log_document_action('umk', umk.id, 'created', new_status='draft')
        db.session.commit()
        flash('УМК создан', 'success')
        return redirect(url_for('cmk.umk_view', id=umk.id))

    rups = RUP.query.all()
    return render_template('cmk/documents/umk_form.html', umk=None, rups=rups)


@bp.route('/umk/<int:id>')
@login_required
def umk_view(id):
    umk = UMK.query.get_or_404(id)
    return render_template('cmk/documents/umk_view.html', umk=umk)


@bp.route('/umk/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def umk_edit(id):
    umk = UMK.query.get_or_404(id)
    if request.method == 'POST':
        umk.title = request.form.get('title', '').strip()
        umk.content = request.form.get('content', '')
        log_document_action('umk', umk.id, 'updated')
        db.session.commit()
        flash('УМК обновлён', 'success')
        return redirect(url_for('cmk.umk_view', id=id))

    rups = RUP.query.all()
    return render_template('cmk/documents/umk_form.html', umk=umk, rups=rups)


@bp.route('/umk/<int:id>/submit', methods=['POST'])
@login_required
def umk_submit(id):
    umk = UMK.query.get_or_404(id)
    old = umk.status
    umk.status = 'under_review'
    log_document_action('umk', id, 'submitted', old, 'under_review')
    db.session.commit()
    flash('УМК отправлен на рассмотрение', 'success')
    return redirect(url_for('cmk.umk_view', id=id))


@bp.route('/umk/<int:id>/approve', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def umk_approve(id):
    umk = UMK.query.get_or_404(id)
    user = get_current_user()
    old = umk.status
    umk.status = 'approved'
    umk.approved_by_id = user.id
    umk.approved_at = datetime.utcnow()
    log_document_action('umk', id, 'approved', old, 'approved')
    db.session.commit()
    flash('УМК утверждён', 'success')
    return redirect(url_for('cmk.umk_view', id=id))


@bp.route('/umk/<int:id>/reject', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def umk_reject(id):
    umk = UMK.query.get_or_404(id)
    old = umk.status
    umk.status = 'revision'
    umk.review_comment = request.form.get('comment', '')
    log_document_action('umk', id, 'rejected', old, 'revision', umk.review_comment)
    db.session.commit()
    flash('УМК отправлен на доработку', 'warning')
    return redirect(url_for('cmk.umk_view', id=id))


# ==================== UMKD ====================

@bp.route('/umkd')
@login_required
def umkd_list():
    user = get_current_user()
    if user.is_chair:
        umkds = UMKD.query.order_by(UMKD.updated_at.desc()).all()
    else:
        umkds = UMKD.query.filter_by(teacher_id=user.teacher_id).order_by(UMKD.updated_at.desc()).all()
    return render_template('cmk/documents/umkd_list.html', umkds=umkds)


@bp.route('/umkd/create', methods=['GET', 'POST'])
@login_required
def umkd_create():
    user = get_current_user()
    if request.method == 'POST':
        umkd = UMKD(
            umk_id=request.form.get('umk_id', type=int),
            rupd_id=request.form.get('rupd_id', type=int) or None,
            discipline=request.form.get('discipline', '').strip(),
            teacher_id=user.teacher_id or request.form.get('teacher_id', type=int),
            syllabus=request.form.get('syllabus', ''),
            lecture_notes=request.form.get('lecture_notes', ''),
            practice_tasks=request.form.get('practice_tasks', ''),
            self_study_tasks=request.form.get('self_study_tasks', ''),
            test_materials=request.form.get('test_materials', ''),
            extra_content=request.form.get('extra_content', ''),
            created_by_id=user.id
        )
        db.session.add(umkd)
        db.session.commit()
        log_document_action('umkd', umkd.id, 'created', new_status='draft')
        db.session.commit()
        flash('УМКД создан', 'success')
        return redirect(url_for('cmk.umkd_view', id=umkd.id))

    umks = UMK.query.all()
    rupds = RUPD.query.all()
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    return render_template('cmk/documents/umkd_form.html', umkd=None,
                           umks=umks, rupds=rupds, teachers=teachers)


@bp.route('/umkd/<int:id>')
@login_required
def umkd_view(id):
    umkd = UMKD.query.get_or_404(id)
    history = DocumentHistory.query.filter_by(document_type='umkd', document_id=id)\
        .order_by(DocumentHistory.created_at.desc()).all()
    return render_template('cmk/documents/umkd_view.html', umkd=umkd, history=history)


@bp.route('/umkd/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def umkd_edit(id):
    umkd = UMKD.query.get_or_404(id)
    user = get_current_user()

    if umkd.status == 'approved' and not user.is_admin:
        flash('Утверждённый документ нельзя редактировать', 'error')
        return redirect(url_for('cmk.umkd_view', id=id))

    if not user.is_chair and umkd.teacher_id != user.teacher_id:
        flash('Вы можете редактировать только свои документы', 'error')
        return redirect(url_for('cmk.umkd_view', id=id))

    if request.method == 'POST':
        umkd.discipline = request.form.get('discipline', '').strip()
        umkd.syllabus = request.form.get('syllabus', '')
        umkd.lecture_notes = request.form.get('lecture_notes', '')
        umkd.practice_tasks = request.form.get('practice_tasks', '')
        umkd.self_study_tasks = request.form.get('self_study_tasks', '')
        umkd.test_materials = request.form.get('test_materials', '')
        umkd.extra_content = request.form.get('extra_content', '')
        log_document_action('umkd', umkd.id, 'updated')
        db.session.commit()
        flash('УМКД обновлён', 'success')
        return redirect(url_for('cmk.umkd_view', id=id))

    umks = UMK.query.all()
    rupds = RUPD.query.all()
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    return render_template('cmk/documents/umkd_form.html', umkd=umkd,
                           umks=umks, rupds=rupds, teachers=teachers)


@bp.route('/umkd/<int:id>/submit', methods=['POST'])
@login_required
def umkd_submit(id):
    umkd = UMKD.query.get_or_404(id)
    old = umkd.status
    umkd.status = 'under_review'
    log_document_action('umkd', id, 'submitted', old, 'under_review')
    db.session.commit()
    flash('УМКД отправлен на рассмотрение', 'success')
    return redirect(url_for('cmk.umkd_view', id=id))


@bp.route('/umkd/<int:id>/approve', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def umkd_approve(id):
    umkd = UMKD.query.get_or_404(id)
    user = get_current_user()
    old = umkd.status
    umkd.status = 'approved'
    umkd.approved_by_id = user.id
    umkd.approved_at = datetime.utcnow()
    log_document_action('umkd', id, 'approved', old, 'approved')
    db.session.commit()
    flash('УМКД утверждён', 'success')
    return redirect(url_for('cmk.umkd_view', id=id))


@bp.route('/umkd/<int:id>/reject', methods=['POST'])
@login_required
@role_required('admin', 'cmk_chair')
def umkd_reject(id):
    umkd = UMKD.query.get_or_404(id)
    old = umkd.status
    umkd.status = 'revision'
    umkd.review_comment = request.form.get('comment', '')
    log_document_action('umkd', id, 'rejected', old, 'revision', umkd.review_comment)
    db.session.commit()
    flash('УМКД отправлен на доработку', 'warning')
    return redirect(url_for('cmk.umkd_view', id=id))


# ==================== Meetings ====================

@bp.route('/meetings')
@login_required
def meetings_list():
    meetings = CMKMeeting.query.order_by(CMKMeeting.meeting_date.desc()).all()
    return render_template('cmk/meetings/index.html', meetings=meetings)


@bp.route('/meetings/create', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'cmk_chair')
def meetings_create():
    user = get_current_user()
    if request.method == 'POST':
        meeting = CMKMeeting(
            commission_id=request.form.get('commission_id', type=int),
            meeting_number=request.form.get('meeting_number', type=int) or 1,
            meeting_date=datetime.strptime(request.form.get('meeting_date'), '%Y-%m-%d').date(),
            title=request.form.get('title', '').strip(),
            agenda=request.form.get('agenda', ''),
            protocol=request.form.get('protocol', ''),
            decisions=request.form.get('decisions', ''),
            created_by_id=user.id
        )
        db.session.add(meeting)
        db.session.commit()
        flash('Заседание создано', 'success')
        return redirect(url_for('cmk.meetings_view', id=meeting.id))

    commissions = CMKCommission.query.all()
    return render_template('cmk/meetings/form.html', meeting=None, commissions=commissions)


@bp.route('/meetings/<int:id>')
@login_required
def meetings_view(id):
    meeting = CMKMeeting.query.get_or_404(id)
    return render_template('cmk/meetings/view.html', meeting=meeting)


@bp.route('/meetings/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'cmk_chair')
def meetings_edit(id):
    meeting = CMKMeeting.query.get_or_404(id)
    if request.method == 'POST':
        meeting.title = request.form.get('title', '').strip()
        meeting.meeting_number = request.form.get('meeting_number', type=int) or 1
        meeting.meeting_date = datetime.strptime(request.form.get('meeting_date'), '%Y-%m-%d').date()
        meeting.agenda = request.form.get('agenda', '')
        meeting.protocol = request.form.get('protocol', '')
        meeting.decisions = request.form.get('decisions', '')
        db.session.commit()
        flash('Заседание обновлено', 'success')
        return redirect(url_for('cmk.meetings_view', id=id))

    commissions = CMKCommission.query.all()
    return render_template('cmk/meetings/form.html', meeting=meeting, commissions=commissions)
