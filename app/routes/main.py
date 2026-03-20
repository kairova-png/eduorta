from flask import Blueprint, render_template
from app.models import Group, Teacher, Room, Workload, Schedule, AcademicYear

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Main dashboard"""
    stats = {
        'groups': Group.query.count(),
        'teachers': Teacher.query.count(),
        'rooms': Room.query.count(),
        'workloads': Workload.query.count(),
        'scheduled': Schedule.query.filter(Schedule.status == 'planned').count(),
        'completed': Schedule.query.filter(Schedule.status.in_(['done', 'completed'])).count(),
    }

    # Get current academic year
    current_year = AcademicYear.query.filter_by(is_current=True).first()

    return render_template('index.html', stats=stats, current_year=current_year)
