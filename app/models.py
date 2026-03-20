from datetime import datetime
import json
from app import db


class AcademicYear(db.Model):
    __tablename__ = 'academic_years'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)  # "2025-2026"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, default=False)

    workloads = db.relationship('Workload', backref='academic_year', lazy='dynamic')
    gup_entries = db.relationship('GUP', backref='academic_year', lazy='dynamic')

    def __repr__(self):
        return f'<AcademicYear {self.name}>'


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10))
    name_ru = db.Column(db.String(100), nullable=False)
    name_kz = db.Column(db.String(100))

    specialties = db.relationship('Specialty', backref='department', lazy='dynamic')
    teachers = db.relationship('Teacher', backref='department', lazy='dynamic')

    def __repr__(self):
        return f'<Department {self.name_ru}>'


class Specialty(db.Model):
    __tablename__ = 'specialties'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)  # "ПО", "АиУ"
    name_ru = db.Column(db.String(150), nullable=False)
    name_kz = db.Column(db.String(150))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))

    groups = db.relationship('Group', backref='specialty', lazy='dynamic')

    def __repr__(self):
        return f'<Specialty {self.code}>'


class Group(db.Model):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)  # "ПО 1-23"
    specialty_id = db.Column(db.Integer, db.ForeignKey('specialties.id'))
    group_number = db.Column(db.Integer)
    enrollment_year = db.Column(db.Integer)
    shift = db.Column(db.Integer, default=1)  # 1 = утренняя (1-4), 2 = дневная (5-8), 3 = смешанная (1-8)
    max_consecutive_pairs = db.Column(db.Integer, default=2)  # Максимум пар подряд (по умолчанию 2)

    workloads = db.relationship('Workload', backref='group', lazy='dynamic')
    gup_entries = db.relationship('GUP', backref='group', lazy='dynamic')
    room_preferences = db.relationship('RoomPreference', backref='group', lazy='dynamic')

    @property
    def course(self):
        current_year = datetime.now().year
        calculated_course = current_year - self.enrollment_year
        return max(1, min(calculated_course, 4))  # От 1 до 4 курса

    @property
    def shift_name(self):
        shift_names = {
            1: "1 смена (утро)",
            2: "2 смена (день)", 
            3: "Смешанная (утро + вечер)"
        }
        return shift_names.get(self.shift, "Не определена")

    @property
    def shift_pairs(self):
        """Return valid pair numbers for this shift"""
        if self.shift == 1:
            return [1, 2, 3, 4]  # 8:30 - 14:50
        elif self.shift == 2:
            return [5, 6, 7]  # 15:00 - 19:20
        elif self.shift == 3:
            return [1, 2, 3, 4, 5, 6, 7]  # 8:30 - 19:20 (смешанная)
        else:
            return [1, 2, 3, 4]  # По умолчанию утренняя

    def get_semester(self, semester_num=1):
        """Get semester number (1 or 2) within academic year"""
        return (self.course - 1) * 2 + semester_num

    def __repr__(self):
        return f'<Group {self.name}>'


class Teacher(db.Model):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))

    workloads = db.relationship('Workload', backref='teacher', lazy='dynamic')
    substitutions = db.relationship('Schedule', backref='substitute_teacher',
                                     foreign_keys='Schedule.substitute_teacher_id', lazy='dynamic')

    def get_substitution_hours(self, start_date=None, end_date=None):
        """Получить часы замен преподавателя за период"""
        from sqlalchemy import and_
        
        query = Schedule.query.filter(
            and_(
                Schedule.substitute_teacher_id == self.id,
                Schedule.status == 'substitution'
            )
        )
        
        if start_date:
            query = query.filter(Schedule.date >= start_date)
        if end_date:
            query = query.filter(Schedule.date <= end_date)
            
        return query.count() * 2  # Каждая пара = 2 часа
    
    def get_vacant_hours(self, start_date=None, end_date=None):
        """Получить вакантные часы (когда преподавателя заменяли) за период"""
        from app.models import VacantHours
        
        query = db.session.query(db.func.sum(VacantHours.hours)).filter(
            VacantHours.original_teacher_id == self.id
        )
        
        if start_date:
            query = query.filter(VacantHours.date >= start_date)
        if end_date:
            query = query.filter(VacantHours.date <= end_date)
            
        return query.scalar() or 0
    
    def get_total_workload_hours(self, academic_year_id=None):
        """Получить общие часы нагрузки преподавателя"""
        query = Workload.query.filter(Workload.teacher_id == self.id)
        
        if academic_year_id:
            query = query.filter(Workload.academic_year_id == academic_year_id)
            
        workloads = query.all()
        return sum(w.total_hours for w in workloads)
    
    def get_conducted_hours(self, start_date=None, end_date=None):
        """Получить фактически проведенные часы (своих предметов)"""
        from sqlalchemy import and_
        
        query = Schedule.query.join(Workload).filter(
            and_(
                Workload.teacher_id == self.id,
                Schedule.status.in_(['done', 'completed']),
                Schedule.substitute_teacher_id.is_(None)  # Только свои пары, не замены
            )
        )
        
        if start_date:
            query = query.filter(Schedule.date >= start_date)
        if end_date:
            query = query.filter(Schedule.date <= end_date)
            
        return query.count() * 2
    
    def get_hours_summary(self, start_date=None, end_date=None, academic_year_id=None):
        """Получить сводку по часам преподавателя"""
        return {
            'total_workload': self.get_total_workload_hours(academic_year_id),
            'conducted_own': self.get_conducted_hours(start_date, end_date),
            'substitutions': self.get_substitution_hours(start_date, end_date),
            'vacant': self.get_vacant_hours(start_date, end_date),
            'total_conducted': self.get_conducted_hours(start_date, end_date) + self.get_substitution_hours(start_date, end_date)
        }

    def __repr__(self):
        return f'<Teacher {self.full_name}>'


class Room(db.Model):
    __tablename__ = 'rooms'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(30), unique=True, nullable=False)
    room_type = db.Column(db.String(30), default='учебная')
    capacity = db.Column(db.Integer, default=30)  # Вместимость аудитории
    equipment = db.Column(db.String(200))  # Оборудование (проектор, компьютеры и т.д.)

    schedules = db.relationship('Schedule', backref='room', lazy='dynamic')
    preferred_for_groups = db.relationship('RoomPreference', foreign_keys='RoomPreference.room_id', backref='room', lazy='dynamic')

    def __repr__(self):
        return f'<Room {self.number}>'


class RoomPreference(db.Model):
    """Модель предпочитаемых аудиторий для групп/дисциплин"""
    __tablename__ = 'room_preferences'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    discipline = db.Column(db.String(100))  # Если для конкретной дисциплины
    priority = db.Column(db.Integer, default=1)  # 1 - высший приоритет
    reason = db.Column(db.String(200))  # Причина предпочтения

    __table_args__ = (
        db.UniqueConstraint('group_id', 'room_id', 'discipline'),
    )

    def __repr__(self):
        return f'<RoomPreference Group:{self.group_id} Room:{self.room_id}>'


class GUP(db.Model):
    __tablename__ = 'gup'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)  # 1-52
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    activity_code = db.Column(db.String(10))  # "К", "П", "::" etc.
    activity_name = db.Column(db.String(100))

    __table_args__ = (
        db.UniqueConstraint('group_id', 'academic_year_id', 'week_number'),
    )

    @property
    def needs_schedule(self):
        """Check if this week type requires schedule generation"""
        return self.activity_code in ["", None, "None", "УП", "ОТ", "ӨО"]

    def __repr__(self):
        return f'<GUP Group:{self.group_id} Week:{self.week_number}>'


class Workload(db.Model):
    __tablename__ = 'workload'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=False)
    discipline = db.Column(db.String(200), nullable=False)
    lesson_type = db.Column(db.String(20), default='theory')  # theory / practice / consultation / exam
    semester = db.Column(db.Integer, nullable=False)  # 1-8
    total_hours = db.Column(db.Integer, nullable=False)
    hours_per_week = db.Column(db.Integer)
    hours_completed = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schedules = db.relationship('Schedule', backref='workload', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def hours_remaining(self):
        return self.total_hours - self.hours_completed

    @property
    def progress_percent(self):
        if self.total_hours == 0:
            return 0
        return int((self.hours_completed / self.total_hours) * 100)

    @property
    def pairs_per_week(self):
        if self.hours_per_week:
            return self.hours_per_week // 2
        return 0
    
    @property
    def hours_completed_actual(self):
        """Фактически проведенные часы для группы/дисциплины (включая замены) - только прошедшие даты"""
        from datetime import date
        completed_schedules = Schedule.query.filter(
            Schedule.workload_id == self.id,
            Schedule.status.in_(['done', 'completed', 'substitution']),
            Schedule.date < date.today()
        ).count()
        return completed_schedules * 2
    
    @property
    def hours_conducted_by_main_teacher(self):
        """Часы, фактически проведенные основным преподавателем (без замен) - только прошедшие даты"""
        from datetime import date
        main_teacher_schedules = Schedule.query.filter(
            Schedule.workload_id == self.id,
            Schedule.status.in_(['done', 'completed']),
            Schedule.substitute_teacher_id.is_(None),
            Schedule.date < date.today()
        ).count()
        return main_teacher_schedules * 2
    
    @property
    def hours_vacant_from_workload(self):
        """Вакантные часы из этой нагрузки (списанные у основного преподавателя)"""
        from app.models import VacantHours
        vacant_sum = db.session.query(db.func.sum(VacantHours.hours)).filter(
            VacantHours.workload_id == self.id
        ).scalar()
        return vacant_sum or 0
    
    @property
    def hours_remaining_for_main_teacher(self):
        """Оставшиеся часы для основного преподавателя (с учетом списанных вакантных)"""
        conducted_by_main = self.hours_conducted_by_main_teacher
        vacant_deducted = self.hours_vacant_from_workload
        return max(0, self.total_hours - conducted_by_main - vacant_deducted)
    
    @property
    def hours_remaining_for_discipline(self):
        """Оставшиеся часы для дисциплины/группы (с учетом всех проведенных)"""
        return max(0, self.total_hours - self.hours_completed_actual)
    
    @property
    def progress_percent_main_teacher(self):
        """Процент выполнения основным преподавателем"""
        if self.total_hours == 0:
            return 0
        return int((self.hours_conducted_by_main_teacher / self.total_hours) * 100)
    
    @property
    def progress_percent_discipline(self):
        """Процент выполнения дисциплины (включая замены)"""
        if self.total_hours == 0:
            return 0
        return int((self.hours_completed_actual / self.total_hours) * 100)
    
    @property
    def progress_percent_adjusted(self):
        """Процент выполнения основным преподавателем (с учетом списанных вакантных часов)"""
        if self.total_hours == 0:
            return 0
        effective_hours = self.hours_conducted_by_main_teacher + self.hours_vacant_from_workload
        return int((effective_hours / self.total_hours) * 100)
    
    def get_substitute_teachers_hours(self):
        """Получить распределение часов по преподавателям-заменителям"""
        from sqlalchemy import func
        
        result = db.session.query(
            Teacher.full_name,
            func.count(Schedule.id).label('pairs_count'),
            (func.count(Schedule.id) * 2).label('hours_count')
        ).join(
            Schedule, Schedule.substitute_teacher_id == Teacher.id
        ).filter(
            Schedule.workload_id == self.id,
            Schedule.status == 'substitution'
        ).group_by(Teacher.id, Teacher.full_name).all()
        
        return [{'teacher': row.full_name, 'pairs': row.pairs_count, 'hours': row.hours_count} for row in result]

    def __repr__(self):
        return f'<Workload {self.discipline} - {self.group.name if self.group else "?"}>'


class Schedule(db.Model):
    __tablename__ = 'schedule'

    id = db.Column(db.Integer, primary_key=True)
    workload_id = db.Column(db.Integer, db.ForeignKey('workload.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))
    date = db.Column(db.Date, nullable=False)
    pair_number = db.Column(db.Integer, nullable=False)  # 1-7
    status = db.Column(db.String(20), default='planned')  # planned, done, cancelled, substitution, completed, rescheduled, vacant
    substitute_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    
    # Поля для переносов
    original_schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'))  # Ссылка на перенесенную пару
    rescheduled_to_id = db.Column(db.Integer, db.ForeignKey('schedule.id'))  # Ссылка на новую пару
    is_makeup = db.Column(db.Boolean, default=False)  # Отработка перенесенной пары
    
    # Поля для отмен и замен
    change_reason = db.Column(db.String(200))  # Причина изменения
    change_type = db.Column(db.String(20))  # substitution, reschedule, cancellation
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('workload_id', 'date', 'pair_number'),
    )

    @property
    def counts_as_hours(self):
        return self.status in ['done', 'completed', 'substitution']
    
    @property
    def is_rescheduled(self):
        return self.status == 'rescheduled'
    
    @property
    def is_cancelled(self):
        return self.status == 'cancelled'
        
    @property
    def is_substitution(self):
        return self.status == 'substitution'
        
    @property
    def original_teacher(self):
        """Возвращает основного преподавателя из нагрузки"""
        return self.workload.teacher if self.workload else None
    
    @property
    def effective_teacher(self):
        """Возвращает преподавателя, который фактически ведет пару (замену или основного)"""
        if self.substitute_teacher:
            return self.substitute_teacher
        return self.original_teacher

    @property
    def time_start(self):
        from config import Config
        return Config.PAIR_TIMES.get(self.pair_number, {}).get('start', '')

    @property
    def time_end(self):
        from config import Config
        return Config.PAIR_TIMES.get(self.pair_number, {}).get('end', '')

    def __repr__(self):
        return f'<Schedule {self.date} Pair:{self.pair_number}>'


class SchedulePeriod(db.Model):
    """Closed/locked schedule periods for timesheet tracking"""
    __tablename__ = 'schedule_periods'

    id = db.Column(db.Integer, primary_key=True)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)  # GUP week number
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='open')  # open, closed, archived
    closed_at = db.Column(db.DateTime)
    closed_by = db.Column(db.String(100))  # Who closed the period
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    academic_year = db.relationship('AcademicYear', backref='schedule_periods')

    __table_args__ = (
        db.UniqueConstraint('academic_year_id', 'week_number'),
    )

    @property
    def is_locked(self):
        return self.status in ['closed', 'archived']

    @property
    def status_name(self):
        names = {
            'open': 'Открыт',
            'closed': 'Закрыт',
            'archived': 'Архив'
        }
        return names.get(self.status, self.status)

    def __repr__(self):
        return f'<SchedulePeriod Week:{self.week_number} Status:{self.status}>'


class ScheduleChange(db.Model):
    """История изменений в расписании для аудита"""
    __tablename__ = 'schedule_changes'

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'), nullable=False)
    change_type = db.Column(db.String(20), nullable=False)  # substitution, reschedule, cancellation, restoration
    
    # Старые значения (для отката)
    old_status = db.Column(db.String(20))
    old_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    old_room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))
    old_date = db.Column(db.Date)
    old_pair_number = db.Column(db.Integer)
    
    # Новые значения
    new_status = db.Column(db.String(20))
    new_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    new_room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))
    new_date = db.Column(db.Date)
    new_pair_number = db.Column(db.Integer)
    
    # Информация об изменении
    reason = db.Column(db.String(200))
    notes = db.Column(db.Text)
    changed_by = db.Column(db.String(100))  # Кто внес изменение
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связанные записи (для переносов)
    related_schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'))  # Связанная пара при переносе
    
    # Relationships
    schedule = db.relationship('Schedule', foreign_keys=[schedule_id], backref='change_history')
    old_teacher = db.relationship('Teacher', foreign_keys=[old_teacher_id])
    new_teacher = db.relationship('Teacher', foreign_keys=[new_teacher_id])
    old_room = db.relationship('Room', foreign_keys=[old_room_id])
    new_room = db.relationship('Room', foreign_keys=[new_room_id])
    related_schedule = db.relationship('Schedule', foreign_keys=[related_schedule_id])
    
    @property
    def change_type_name(self):
        names = {
            'substitution': 'Замена',
            'reschedule': 'Перенос', 
            'cancellation': 'Отмена',
            'restoration': 'Восстановление'
        }
        return names.get(self.change_type, self.change_type)
    
    def __repr__(self):
        return f'<ScheduleChange {self.change_type} for Schedule:{self.schedule_id}>'


class WorkloadTemplate(db.Model):
    """Workload distribution templates for schedule generation"""
    __tablename__ = 'workload_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    
    # Relationships
    workload_id = db.Column(db.Integer, db.ForeignKey('workload.id', ondelete='CASCADE'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=False)
    
    # Parameters
    semester = db.Column(db.Integer, nullable=False)  # 1-8
    total_hours = db.Column(db.Integer, nullable=False)
    
    # JSON distribution data
    distribution_json = db.Column(db.Text, nullable=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))  # Username who created
    
    # Relationships
    workload = db.relationship('Workload', backref='templates')
    group = db.relationship('Group', backref='workload_templates')
    academic_year = db.relationship('AcademicYear', backref='workload_templates')

    __table_args__ = (
        db.UniqueConstraint('workload_id', 'group_id', 'semester', name='unique_workload_template'),
    )

    @property
    def weeks_data(self):
        """Parse distribution JSON to get weeks data"""
        try:
            return json.loads(self.distribution_json)
        except:
            return []

    @property
    def statistics(self):
        """Calculate template statistics"""
        weeks = self.weeks_data
        if not weeks:
            return {'total_distributed': 0, 'weeks_used': 0}
        
        total_hours = sum(week.get('hours', 0) for week in weeks)
        weeks_used = len([w for w in weeks if w.get('hours', 0) > 0])
        
        return {
            'total_distributed': total_hours,
            'weeks_used': weeks_used
        }
    
    def get_slot_constraints(self):
        """Extract slot constraints for scheduler"""
        constraints = {
            'selected': [],
            'preferred': [],
            'avoid': []
        }
        
        weeks = self.weeks_data
        for week_data in weeks:
            week_num = week_data.get('week')
            
            for day_data in week_data.get('schedule', []):
                day = day_data.get('day')
                
                for pair_data in day_data.get('pairs', []):
                    pair = pair_data.get('pair')
                    status = pair_data.get('status')
                    
                    if status in constraints:
                        slot = {
                            'week': week_num,
                            'day': day,
                            'pair': pair,
                            'workload_id': self.workload_id,
                            'discipline': self.workload.discipline if self.workload else '',
                            'teacher_id': self.workload.teacher_id if self.workload else None,
                            'group_id': self.group_id
                        }
                        constraints[status].append(slot)
        
        return constraints
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'workload_id': self.workload_id,
            'group_id': self.group_id,
            'academic_year_id': self.academic_year_id,
            'semester': self.semester,
            'total_hours': self.total_hours,
            'weeks': self.weeks_data,
            'statistics': self.statistics,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'workload': {
                'id': self.workload.id,
                'discipline': self.workload.discipline,
                'teacher_id': self.workload.teacher_id,
                'teacher_name': self.workload.teacher.full_name if self.workload and self.workload.teacher else None
            } if self.workload else None,
            'group': {
                'id': self.group.id,
                'name': self.group.name
            } if self.group else None
        }

    def __repr__(self):
        return f'<WorkloadTemplate {self.name} - {self.group.name if self.group else "?"}>'


class VacantHours(db.Model):
    """Учет вакантных часов преподавателей при заменах"""
    __tablename__ = 'vacant_hours'

    id = db.Column(db.Integer, primary_key=True)
    original_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)  # Кого заменяли
    substitute_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)  # Кто заменял
    workload_id = db.Column(db.Integer, db.ForeignKey('workload.id'), nullable=False)  # Из какой нагрузки
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'), nullable=False)  # Какая пара
    
    hours = db.Column(db.Integer, default=2)  # Количество часов (обычно 2 - одна пара)
    date = db.Column(db.Date, nullable=False)  # Дата проведения
    reason = db.Column(db.String(200))  # Причина замены
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    original_teacher = db.relationship('Teacher', foreign_keys=[original_teacher_id], backref='vacant_hours_as_original')
    substitute_teacher = db.relationship('Teacher', foreign_keys=[substitute_teacher_id], backref='vacant_hours_as_substitute')
    workload = db.relationship('Workload', backref='vacant_hours')
    schedule = db.relationship('Schedule', backref='vacant_hour_record')
    
    @classmethod
    def get_teacher_vacant_summary(cls, teacher_id, start_date=None, end_date=None):
        """Получить сводку по вакантным часам преподавателя"""
        query = cls.query.filter(cls.original_teacher_id == teacher_id)
        
        if start_date:
            query = query.filter(cls.date >= start_date)
        if end_date:
            query = query.filter(cls.date <= end_date)
            
        vacant_records = query.all()
        
        total_hours = sum(record.hours for record in vacant_records)
        by_substitute = {}
        
        for record in vacant_records:
            substitute_name = record.substitute_teacher.full_name
            if substitute_name not in by_substitute:
                by_substitute[substitute_name] = {
                    'hours': 0,
                    'pairs': 0,
                    'teacher': record.substitute_teacher
                }
            by_substitute[substitute_name]['hours'] += record.hours
            by_substitute[substitute_name]['pairs'] += 1
        
        return {
            'total_hours': total_hours,
            'total_pairs': len(vacant_records),
            'by_substitute': by_substitute,
            'records': vacant_records
        }
    
    @classmethod 
    def get_substitute_summary(cls, teacher_id, start_date=None, end_date=None):
        """Получить сводку по заменам преподавателя"""
        query = cls.query.filter(cls.substitute_teacher_id == teacher_id)
        
        if start_date:
            query = query.filter(cls.date >= start_date)
        if end_date:
            query = query.filter(cls.date <= end_date)
            
        substitute_records = query.all()
        
        total_hours = sum(record.hours for record in substitute_records)
        by_original = {}
        
        for record in substitute_records:
            original_name = record.original_teacher.full_name
            discipline = record.workload.discipline
            key = f"{original_name} - {discipline}"
            
            if key not in by_original:
                by_original[key] = {
                    'hours': 0,
                    'pairs': 0,
                    'original_teacher': record.original_teacher,
                    'discipline': discipline
                }
            by_original[key]['hours'] += record.hours
            by_original[key]['pairs'] += 1
        
        return {
            'total_hours': total_hours,
            'total_pairs': len(substitute_records),
            'by_original': by_original,
            'records': substitute_records
        }

    def __repr__(self):
        return f'<VacantHours {self.hours}h Teacher:{self.original_teacher_id} Date:{self.date}>'


# ==================== ЦМК Module Models ====================

class User(db.Model):
    """Пользователь системы с ролью"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='teacher')  # admin, cmk_chair, teacher
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher = db.relationship('Teacher', backref='user_account')

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_chair(self):
        return self.role in ('admin', 'cmk_chair')

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class CMKCommission(db.Model):
    """ЦМК - Цикловая методическая комиссия"""
    __tablename__ = 'cmk_commissions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    chair_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    department = db.relationship('Department', backref='cmk_commissions')
    chair = db.relationship('User', backref='chaired_commissions')
    academic_year = db.relationship('AcademicYear', backref='cmk_commissions')
    members = db.relationship('CMKMember', backref='commission', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<CMKCommission {self.name}>'


class CMKMember(db.Model):
    """Член ЦМК"""
    __tablename__ = 'cmk_members'

    id = db.Column(db.Integer, primary_key=True)
    commission_id = db.Column(db.Integer, db.ForeignKey('cmk_commissions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_in_commission = db.Column(db.String(50), default='member')  # chair, secretary, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='cmk_memberships')

    def __repr__(self):
        return f'<CMKMember User:{self.user_id} Commission:{self.commission_id}>'


class RUP(db.Model):
    """РУП - Рабочий учебный план (на группу, привязан к году поступления)"""
    __tablename__ = 'rup_documents'

    id = db.Column(db.Integer, primary_key=True)
    commission_id = db.Column(db.Integer, db.ForeignKey('cmk_commissions.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    specialty_id = db.Column(db.Integer, db.ForeignKey('specialties.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=False)
    enrollment_year = db.Column(db.Integer)  # Год поступления группы
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text)  # Учебный план (HTML)
    gup_content = db.Column(db.Text)  # ГУП данные (HTML)
    status = db.Column(db.String(20), default='draft')
    version = db.Column(db.Integer, default=1)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    review_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    commission = db.relationship('CMKCommission', backref='rup_documents')
    group = db.relationship('Group', backref='rup_documents')
    specialty = db.relationship('Specialty', backref='rup_documents')
    academic_year = db.relationship('AcademicYear')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])

    @property
    def status_name(self):
        names = {'draft': 'Черновик', 'under_review': 'На рассмотрении',
                 'revision': 'На доработке', 'approved': 'Утверждён'}
        return names.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {'draft': 'secondary', 'under_review': 'warning',
                  'revision': 'danger', 'approved': 'success'}
        return colors.get(self.status, 'secondary')

    def __repr__(self):
        return f'<RUP {self.title}>'


class RUPD(db.Model):
    """РУПД - Рабочая учебная программа дисциплины"""
    __tablename__ = 'rupd_documents'

    id = db.Column(db.Integer, primary_key=True)
    rup_id = db.Column(db.Integer, db.ForeignKey('rup_documents.id'), nullable=False)
    discipline = db.Column(db.String(200), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    goals = db.Column(db.Text)
    competencies = db.Column(db.Text)
    content_plan = db.Column(db.Text)
    literature = db.Column(db.Text)
    assessment = db.Column(db.Text)
    extra_content = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')
    version = db.Column(db.Integer, default=1)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    review_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rup = db.relationship('RUP', backref='rupd_documents')
    teacher = db.relationship('Teacher', backref='rupd_documents')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])

    @property
    def status_name(self):
        names = {'draft': 'Черновик', 'under_review': 'На рассмотрении',
                 'revision': 'На доработке', 'approved': 'Утверждён'}
        return names.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {'draft': 'secondary', 'under_review': 'warning',
                  'revision': 'danger', 'approved': 'success'}
        return colors.get(self.status, 'secondary')

    def __repr__(self):
        return f'<RUPD {self.discipline}>'


class UMK(db.Model):
    """УМК - Учебно-методический комплекс"""
    __tablename__ = 'umk_documents'

    id = db.Column(db.Integer, primary_key=True)
    rup_id = db.Column(db.Integer, db.ForeignKey('rup_documents.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')
    version = db.Column(db.Integer, default=1)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    review_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rup = db.relationship('RUP', backref='umk_documents')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])

    @property
    def status_name(self):
        names = {'draft': 'Черновик', 'under_review': 'На рассмотрении',
                 'revision': 'На доработке', 'approved': 'Утверждён'}
        return names.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {'draft': 'secondary', 'under_review': 'warning',
                  'revision': 'danger', 'approved': 'success'}
        return colors.get(self.status, 'secondary')

    def __repr__(self):
        return f'<UMK {self.title}>'


class UMKD(db.Model):
    """УМКД - Учебно-методический комплекс дисциплины"""
    __tablename__ = 'umkd_documents'

    id = db.Column(db.Integer, primary_key=True)
    umk_id = db.Column(db.Integer, db.ForeignKey('umk_documents.id'), nullable=False)
    rupd_id = db.Column(db.Integer, db.ForeignKey('rupd_documents.id'))
    discipline = db.Column(db.String(200), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    syllabus = db.Column(db.Text)
    lecture_notes = db.Column(db.Text)
    practice_tasks = db.Column(db.Text)
    self_study_tasks = db.Column(db.Text)
    test_materials = db.Column(db.Text)
    extra_content = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')
    version = db.Column(db.Integer, default=1)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    review_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    umk = db.relationship('UMK', backref='umkd_documents')
    rupd = db.relationship('RUPD', backref='umkd_documents')
    teacher = db.relationship('Teacher', backref='umkd_documents')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])

    @property
    def status_name(self):
        names = {'draft': 'Черновик', 'under_review': 'На рассмотрении',
                 'revision': 'На доработке', 'approved': 'Утверждён'}
        return names.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {'draft': 'secondary', 'under_review': 'warning',
                  'revision': 'danger', 'approved': 'success'}
        return colors.get(self.status, 'secondary')

    def __repr__(self):
        return f'<UMKD {self.discipline}>'


class DocumentHistory(db.Model):
    """История изменений документов"""
    __tablename__ = 'document_history'

    id = db.Column(db.Integer, primary_key=True)
    document_type = db.Column(db.String(10), nullable=False)
    document_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(30), nullable=False)
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20))
    comment = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')

    def __repr__(self):
        return f'<DocumentHistory {self.document_type}:{self.document_id} {self.action}>'


class CMKMeeting(db.Model):
    """Протокол заседания ЦМК"""
    __tablename__ = 'cmk_meetings'

    id = db.Column(db.Integer, primary_key=True)
    commission_id = db.Column(db.Integer, db.ForeignKey('cmk_commissions.id'), nullable=False)
    meeting_number = db.Column(db.Integer, nullable=False)
    meeting_date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    agenda = db.Column(db.Text)
    protocol = db.Column(db.Text)
    decisions = db.Column(db.Text)
    attendees_json = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    commission = db.relationship('CMKCommission', backref='meetings')
    created_by = db.relationship('User')

    @property
    def attendees(self):
        try:
            return json.loads(self.attendees_json) if self.attendees_json else []
        except:
            return []

    def __repr__(self):
        return f'<CMKMeeting #{self.meeting_number} {self.meeting_date}>'

