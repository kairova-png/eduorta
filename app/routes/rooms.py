from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from app.models import Room

bp = Blueprint('rooms', __name__, url_prefix='/rooms')


@bp.route('/')
def index():
    """List all rooms"""
    room_type = request.args.get('type', '')

    query = Room.query

    if room_type:
        query = query.filter_by(room_type=room_type)

    rooms = query.order_by(Room.number).all()

    # Get unique room types
    room_types = db.session.query(Room.room_type).distinct().all()
    room_types = [r[0] for r in room_types]

    return render_template('rooms/index.html',
                           rooms=rooms,
                           room_types=room_types,
                           selected_type=room_type)


@bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create new room"""
    if request.method == 'POST':
        number = request.form.get('number')
        room_type = request.form.get('room_type', 'учебная')

        if Room.query.filter_by(number=number).first():
            flash('Аудитория с таким номером уже существует', 'error')
        else:
            room = Room(number=number, room_type=room_type)
            db.session.add(room)
            db.session.commit()
            flash('Аудитория добавлена', 'success')
            return redirect(url_for('rooms.index'))

    return render_template('rooms/form.html', room=None)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """Edit room"""
    room = Room.query.get_or_404(id)

    if request.method == 'POST':
        room.number = request.form.get('number')
        room.room_type = request.form.get('room_type', 'учебная')

        db.session.commit()
        flash('Аудитория обновлена', 'success')
        return redirect(url_for('rooms.index'))

    return render_template('rooms/form.html', room=room)


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """Delete room"""
    room = Room.query.get_or_404(id)
    db.session.delete(room)
    db.session.commit()
    flash('Аудитория удалена', 'success')
    return redirect(url_for('rooms.index'))
