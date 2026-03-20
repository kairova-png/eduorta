from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from datetime import datetime
import os
import json
from werkzeug.utils import secure_filename
from app import db
from app.models import AcademicYear
from app.services.importer import import_college_data, import_gup, import_college_from_file, import_gup_from_file
from config import Config

bp = Blueprint('settings', __name__, url_prefix='/settings')

ALLOWED_EXTENSIONS = {'json'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/')
def index():
    """Settings main page"""
    years = AcademicYear.query.order_by(AcademicYear.name.desc()).all()
    return render_template('settings/index.html', years=years)


@bp.route('/year/create', methods=['GET', 'POST'])
def create_year():
    """Create academic year"""
    if request.method == 'POST':
        name = request.form.get('name')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        is_current = request.form.get('is_current') == 'on'

        # If setting as current, unset others
        if is_current:
            AcademicYear.query.update({AcademicYear.is_current: False})

        year = AcademicYear(
            name=name,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current
        )
        db.session.add(year)
        db.session.commit()

        flash('Учебный год создан', 'success')
        return redirect(url_for('settings.index'))

    return render_template('settings/year_form.html', year=None)


@bp.route('/year/<int:id>/set-current', methods=['POST'])
def set_current_year(id):
    """Set academic year as current"""
    AcademicYear.query.update({AcademicYear.is_current: False})

    year = AcademicYear.query.get_or_404(id)
    year.is_current = True
    db.session.commit()

    flash(f'Учебный год {year.name} установлен как текущий', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/import', methods=['GET', 'POST'])
def import_data():
    """Import data from JSON files"""
    from app.models import Group, Teacher, Room, GUP

    if request.method == 'POST':
        import_type = request.form.get('import_type')

        # Handle clear actions
        if import_type == 'clear_gup':
            GUP.query.delete()
            db.session.commit()
            flash('Все записи ГУП удалены', 'success')
            return redirect(url_for('settings.import_data'))

        # Check if file was uploaded
        if 'file' not in request.files:
            flash('Файл не выбран', 'error')
            return redirect(url_for('settings.import_data'))

        file = request.files['file']

        if file.filename == '':
            flash('Файл не выбран', 'error')
            return redirect(url_for('settings.import_data'))

        if not allowed_file(file.filename):
            flash('Разрешены только JSON файлы', 'error')
            return redirect(url_for('settings.import_data'))

        try:
            # Read JSON from uploaded file
            content = file.read().decode('utf-8')
            data = json.loads(content)

            if import_type == 'college':
                result = import_college_from_file(data)
                flash(f'Импортировано: {result["departments"]} кафедр, '
                      f'{result["specialties"]} специальностей, '
                      f'{result["groups"]} групп, '
                      f'{result["teachers"]} преподавателей, '
                      f'{result["rooms"]} аудиторий', 'success')

            elif import_type == 'gup':
                count = import_gup_from_file(data)
                flash(f'Импортировано {count} записей ГУП', 'success')

        except json.JSONDecodeError:
            flash('Ошибка: неверный формат JSON', 'error')
        except Exception as e:
            flash(f'Ошибка импорта: {str(e)}', 'error')

        return redirect(url_for('settings.import_data'))

    # Get current stats
    stats = {
        'groups': Group.query.count(),
        'teachers': Teacher.query.count(),
        'rooms': Room.query.count(),
        'gup': GUP.query.count()
    }

    return render_template('settings/import.html', stats=stats)


@bp.route('/template/<template_type>')
def download_template(template_type):
    """Download template JSON file"""
    if template_type == 'college':
        template = {
            "metadata": {
                "college": "Название колледжа",
                "description": "Шаблон для импорта справочников"
            },
            "departments": [
                {
                    "name_ru": "Название кафедры на русском",
                    "name_kz": "Название кафедры на казахском"
                }
            ],
            "specialties": [
                {
                    "code": "ПО",
                    "name_ru": "Программное обеспечение",
                    "name_kz": "Бағдарламалық қамтамасыз ету",
                    "department": "Название кафедры на русском"
                }
            ],
            "groups": [
                {
                    "name": "ПО 1-25",
                    "specialty_code": "ПО",
                    "group_number": 1,
                    "enrollment_year": 2025
                }
            ],
            "teachers": [
                {
                    "full_name": "Иванов И.И."
                }
            ],
            "rooms": [
                {
                    "number": "301",
                    "type": "учебная"
                },
                {
                    "number": "Спортзал",
                    "type": "спортзал"
                }
            ]
        }
        filename = 'template_college_data.json'

    elif template_type == 'gup':
        template = {
            "academic_year": "2025-2026",
            "academic_year_start": "2025-09-01",
            "academic_year_end": "2026-08-31",
            "legend": {
                "symbols": {
                    "": {"ru": "Теоретическое обучение", "kz": "Теориялық оқыту"},
                    "::": {"ru": "Промежуточная аттестация", "kz": "Аралық аттестация"},
                    "К": {"ru": "Каникулы", "kz": "Каникулдар"},
                    "П": {"ru": "Производственная практика", "kz": "Кәсіби практика"},
                    "УП": {"ru": "Учебная практика", "kz": "Оқу тәжірибесі"},
                    "И": {"ru": "Итоговая аттестация", "kz": "Қорытынды аттестация"}
                }
            },
            "weeks": {
                "1": {"week_number": 1, "start_date": "2025-09-01", "end_date": "2025-09-07"},
                "2": {"week_number": 2, "start_date": "2025-09-08", "end_date": "2025-09-14"}
            },
            "groups": [
                {
                    "group_name": "ПО 1-25",
                    "course": 1,
                    "schedule": {
                        "1": {"code_ru": "", "code_kz": "", "activity_ru": "Теоретическое обучение"},
                        "2": {"code_ru": "", "code_kz": "", "activity_ru": "Теоретическое обучение"},
                        "17": {"code_ru": "::", "code_kz": "::", "activity_ru": "Промежуточная аттестация"},
                        "18": {"code_ru": "К", "code_kz": "К", "activity_ru": "Каникулы"}
                    }
                }
            ]
        }
        filename = 'template_gup.json'

    else:
        flash('Неизвестный тип шаблона', 'error')
        return redirect(url_for('settings.import_data'))

    # Save template to temp file and send
    import tempfile
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    return send_file(temp_path, as_attachment=True, download_name=filename)


@bp.route('/backup')
def backup():
    """Database backup info"""
    db_path = os.path.join(Config.basedir, 'instance', 'college.db')
    db_exists = os.path.exists(db_path)
    db_size = os.path.getsize(db_path) if db_exists else 0

    return render_template('settings/backup.html',
                           db_path=db_path,
                           db_exists=db_exists,
                           db_size=db_size)


@bp.route('/backup/download')
def download_backup():
    """Download database backup"""
    db_path = os.path.join(Config.basedir, 'instance', 'college.db')
    if os.path.exists(db_path):
        backup_name = f'college_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        return send_file(db_path, as_attachment=True, download_name=backup_name)
    flash('База данных не найдена', 'error')
    return redirect(url_for('settings.backup'))
