from datetime import datetime, timedelta
from app import db
from app.models import Workload, Schedule, GUP, Room, Teacher, Group, SchedulePeriod, ScheduleChange, VacantHours, RoomPreference
from config import Config


def is_week_locked(academic_year_id, week_number):
    """Check if a week is locked for editing"""
    period = SchedulePeriod.query.filter_by(
        academic_year_id=academic_year_id,
        week_number=week_number
    ).first()
    return period and period.is_locked


def get_locked_weeks(academic_year_id):
    """Get list of locked week numbers for an academic year"""
    periods = SchedulePeriod.query.filter_by(
        academic_year_id=academic_year_id
    ).filter(SchedulePeriod.status.in_(['closed', 'archived'])).all()
    return [p.week_number for p in periods]


class ScheduleGenerator:
    """Service for generating class schedules"""

    def __init__(self, group_id, semester, academic_year_id, generation_mode='remaining'):
        self.group_id = group_id
        self.semester = semester
        self.academic_year_id = academic_year_id
        self.generation_mode = generation_mode  # 'remaining', 'full_replan', 'force_reset'
        self.group = Group.query.get(group_id)
        self.workloads = []
        self.rooms = []
        self.room_preferences = {}  # {discipline: [room_ids], None: [room_ids]}
        self.errors = []
        self.warnings = []
        self.created_count = 0
        self.deleted_count = 0
        # Get valid pair numbers based on group shift
        self.valid_pairs = self.group.shift_pairs if self.group else [1, 2, 3, 4]
        # Time preferences
        self.time_preferences = {}
        self.follow_gup = True  # Default to follow GUP
    
    def set_room_preferences(self, preferences):
        """Установка предпочтений аудиторий из списка RoomPreference"""
        self.room_preferences = {}
        
        for pref in preferences:
            discipline = pref.discipline  # None для общих предпочтений
            if discipline not in self.room_preferences:
                self.room_preferences[discipline] = []
            self.room_preferences[discipline].append({
                'room_id': pref.room_id,
                'priority': pref.priority,
                'reason': pref.reason
            })
        
        # Сортируем по приоритету (1 = высший)
        for discipline in self.room_preferences:
            self.room_preferences[discipline].sort(key=lambda x: x['priority'])
    
    def set_time_preferences(self, time_settings):
        """Set time preferences including GUP following"""
        self.time_preferences = time_settings
        self.follow_gup = time_settings.get('follow_gup', True)
    
    def _get_preferred_rooms_for_workload(self, workload):
        """Получение списка предпочитаемых аудиторий для нагрузки"""
        preferred_rooms = []
        
        # Сначала проверяем предпочтения для конкретной дисциплины
        if workload.discipline in self.room_preferences:
            preferred_rooms.extend([r['room_id'] for r in self.room_preferences[workload.discipline]])
        
        # Затем добавляем общие предпочтения группы
        if None in self.room_preferences:
            for room_pref in self.room_preferences[None]:
                if room_pref['room_id'] not in preferred_rooms:
                    preferred_rooms.append(room_pref['room_id'])
        
        return preferred_rooms

    def generate(self):
        """Main generation method"""
        # Get workloads for the group and semester
        self.workloads = Workload.query.filter_by(
            group_id=self.group_id,
            semester=self.semester,
            academic_year_id=self.academic_year_id
        ).all()

        if not self.workloads:
            self.errors.append("Нет нагрузок для генерации")
            return False

        # Отладочная информация о нагрузках
        print(f"\nDEBUG: Found {len(self.workloads)} workloads for group {self.group_id}, semester {self.semester}")
        for wl in self.workloads:
            completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status.in_(['done', 'completed', 'substitution'])
            ).count()
            actual_completed_hours = completed_pairs * 2
            remaining_hours = wl.total_hours - actual_completed_hours
            
            print(f"  {wl.discipline}: {wl.total_hours}ч всего, {actual_completed_hours}ч выполнено, {remaining_hours}ч остатка")

        # Get available rooms
        self.rooms = Room.query.all()
        if not self.rooms:
            self.errors.append("Нет аудиторий в базе")
            return False

        # Get locked weeks
        locked_weeks = get_locked_weeks(self.academic_year_id)

        # Get GUP weeks that need schedule
        all_gup_weeks = GUP.query.filter_by(
            group_id=self.group_id,
            academic_year_id=self.academic_year_id
        ).filter(GUP.activity_code.in_(['', None, 'УП', 'ОТ', 'ӨО'])).order_by(GUP.week_number).all()

        if not all_gup_weeks:
            self.errors.append("Нет учебных недель в ГУП")
            return False

        # Filter GUP weeks by semester period
        from datetime import date
        gup_weeks = []
        today = date.today()
        
        if self.semester in [1, 3, 5, 7]:
            # Нечетный семестр (сентябрь-январь)
            if today.month >= 9:
                # Текущий учебный год: сентябрь текущего года - январь следующего
                semester_start = date(today.year, 9, 1)
                semester_end = date(today.year + 1, 1, 31)
            else:
                # Завершение предыдущего года или подготовка к новому
                semester_start = date(today.year - 1, 9, 1)
                semester_end = date(today.year, 1, 31)
        else:
            # Четный семестр (январь-июнь)
            if today.month >= 1 and today.month <= 6:
                # Текущий семестр (включая январь после зимних каникул)
                semester_start = date(today.year, 1, 1)
                semester_end = date(today.year, 6, 30)
            else:
                # Планируем следующий четный семестр (июль-декабрь)
                semester_start = date(today.year + 1, 1, 1)
                semester_end = date(today.year + 1, 6, 30)
        
        # Фильтруем недели по периоду семестра и признаку needs_schedule
        for week in all_gup_weeks:
            in_period = week.start_date >= semester_start and week.end_date <= semester_end
            needs_schedule = week.needs_schedule
            if in_period and needs_schedule:
                gup_weeks.append(week)
        
        # DEBUG: Semester period logged
        # DEBUG: Weeks filtered

        if not gup_weeks:
            self.errors.append(f"Нет учебных недель в ГУП для семестра {self.semester} (период {semester_start} - {semester_end})")
            return False

        # Filter out locked weeks
        open_gup_weeks = [w for w in gup_weeks if w.week_number not in locked_weeks]
        skipped_weeks = len(gup_weeks) - len(open_gup_weeks)

        if skipped_weeks > 0:
            self.errors.append(f"Пропущено закрытых недель: {skipped_weeks}")

        if not open_gup_weeks:
            self.errors.append("Все учебные недели закрыты для редактирования")
            return False

        # DEBUG: Open weeks found

        # Smart deletion based on generation mode
        self._clean_existing_schedule(open_gup_weeks)

        db.session.commit()

        # Generate schedule for each open week
        for gup_week in open_gup_weeks:
            self._generate_week(gup_week)

        # Final update of completed hours after generation
        if self.generation_mode == 'remaining':
            self._update_completed_hours_for_remaining()

        # Итоговый анализ неразмещенных дисциплин
        self._analyze_final_placement()

        db.session.commit()
        return True

    def _generate_week(self, gup_week):
        """Generate schedule for one week"""
        if not gup_week.start_date:
            return

        # Get working days (Mon-Fri) - only future dates
        from datetime import date
        today = date.today()

        current_date = gup_week.start_date
        week_days = []
        while current_date <= gup_week.end_date:
            if current_date.weekday() < 5 and current_date >= today:  # Mon-Fri, future only
                week_days.append(current_date)
            current_date += timedelta(days=1)

        if not week_days:
            return

        # Calculate how many pairs each workload needs per week
        # Based on ACTUAL remaining hours from schedule, not cached hours_completed
        workload_pairs = []
        for wl in self.workloads:
            # Подсчет фактически выполненных часов из расписания
            completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status.in_(['done', 'completed', 'substitution'])
            ).count()
            actual_completed_hours = completed_pairs * 2
            
            # ИСПРАВЛЕНО: Учитываем ВСЕ пары (включая запланированные)
            total_existing_pairs = Schedule.query.filter_by(workload_id=wl.id).count()
            total_existing_hours = total_existing_pairs * 2
            
            remaining_hours = wl.total_hours - total_existing_hours
            remaining_pairs = remaining_hours // 2

            if remaining_pairs <= 0:
                continue  # Skip if no remaining hours

            # Use hours_per_week if set, otherwise distribute remaining
            pairs_per_week = wl.pairs_per_week or 1
            pairs_needed = min(pairs_per_week, remaining_pairs)

            workload_pairs.append({
                'workload': wl,
                'pairs_needed': pairs_needed,
                'pairs_assigned': 0,
                'remaining_pairs': remaining_pairs,
                'actual_completed_hours': actual_completed_hours  # Для отладки
            })

        # УМНОЕ ПЛАНИРОВАНИЕ НЕДЕЛИ (вместо примитивного поиска)
        print(f"      Включен умный алгоритм планирования")
        
        # Track teacher and room occupation per day/pair (includes existing DB records)
        occupied = {}  # {(date, pair): {'teachers': set(), 'rooms': set()}}

        # Pre-load existing schedule entries for this week to check conflicts
        for date in week_days:
            for pair_num in self.valid_pairs:
                key = (date, pair_num)
                occupied[key] = {'teachers': set(), 'rooms': set(), 'groups': set()}

                # Get existing schedules for this date/pair
                existing = Schedule.query.join(Workload).filter(
                    Schedule.date == date,
                    Schedule.pair_number == pair_num
                ).all()

                for ex in existing:
                    occupied[key]['teachers'].add(ex.workload.teacher_id)
                    if ex.room_id:
                        occupied[key]['rooms'].add(ex.room_id)
                    # Добавляем группу для отслеживания пар подряд
                    if ex.workload.group_id:
                        occupied[key]['groups'].add(ex.workload.group_id)

        # ШАГ 1: СОЗДАЕМ ПЛАН НЕДЕЛИ (равномерное распределение)
        week_plan = self._create_smart_week_plan(workload_pairs, week_days)
        
        # ШАГ 2: РАЗМЕЩАЕМ ПО ПЛАНУ (с проверками конфликтов)
        self._place_pairs_according_to_plan(week_plan, occupied, workload_pairs)

        # Анализ неразмещенных пар после генерации недели
        week_date_str = gup_week.start_date.strftime('%d.%m.%Y')
        for wp in workload_pairs:
            if wp['pairs_assigned'] < wp['pairs_needed']:
                unplaced = wp['pairs_needed'] - wp['pairs_assigned']
                discipline = wp['workload'].discipline
                teacher = wp['workload'].teacher.full_name if wp['workload'].teacher else "Нет преподавателя"
                
                # Анализ причин неразмещения
                reasons = []
                
                # Проверка доступности преподавателя
                teacher_conflicts = 0
                room_conflicts = 0
                for date in week_days:
                    for pair_num in self.valid_pairs:
                        key = (date, pair_num)
                        if wp['workload'].teacher_id in occupied[key]['teachers']:
                            teacher_conflicts += 1
                        if len(occupied[key]['rooms']) >= len(self.rooms):
                            room_conflicts += 1
                
                if teacher_conflicts > len(week_days) * len(self.valid_pairs) * 0.7:
                    reasons.append("преподаватель сильно занят")
                if room_conflicts > len(week_days) * len(self.valid_pairs) * 0.5:
                    reasons.append("нехватка аудиторий")
                if not reasons:
                    reasons.append("недостаточно слотов в неделе")
                
                warning_msg = (f"⚠️  Неделя {week_date_str}: {discipline} - "
                             f"НЕ размещено {unplaced} пар (из {wp['pairs_needed']}). "
                             f"Преподаватель: {teacher}. "
                             f"Причины: {', '.join(reasons)}")
                self.warnings.append(warning_msg)

    def _clean_existing_schedule(self, open_gup_weeks):
        """Smart cleanup of existing schedule based on generation mode"""
        
        for wl in self.workloads:
            for gup_week in open_gup_weeks:
                if not (gup_week.start_date and gup_week.end_date):
                    continue
                
                # Get existing schedules in this week
                existing_schedules = Schedule.query.filter(
                    Schedule.workload_id == wl.id,
                    Schedule.date >= gup_week.start_date,
                    Schedule.date <= gup_week.end_date
                ).all()
                
                if not existing_schedules:
                    continue
                
                if self.generation_mode == 'remaining':
                    # SAFE: Delete only planned classes
                    deletable_statuses = ['planned']
                    protected_count = 0
                    
                elif self.generation_mode == 'full_replan':
                    # CAREFUL: Delete all except completed and substitutions
                    deletable_statuses = ['planned', 'cancelled', 'rescheduled']
                    protected_count = 0
                    
                elif self.generation_mode == 'force_reset':
                    # DANGEROUS: Delete all (admin only)
                    deletable_statuses = ['planned', 'cancelled', 'rescheduled', 'done', 'completed', 'substitution']
                    protected_count = 0
                    
                else:
                    self.errors.append(f"Unknown generation mode: {self.generation_mode}")
                    return
                
                # Count and deletion
                protected_count = 0
                for schedule in existing_schedules:
                    if schedule.status in deletable_statuses:
                        try:
                            ScheduleChange.query.filter_by(schedule_id=schedule.id).delete()
                            db.session.delete(schedule)
                            self.deleted_count += 1
                        except Exception as e:
                            pass
                    else:
                        protected_count += 1
                
                # Предупреждения
                if protected_count > 0 and self.generation_mode == 'remaining':
                    self.warnings.append(f"Защищено {protected_count} завершенных пар для {wl.discipline}")
        
        # Пересчет выполненных часов если необходимо
        if self.generation_mode in ['full_replan', 'force_reset']:
            self._recalculate_completed_hours()
        elif self.generation_mode == 'remaining':
            # В режиме остатков также нужно обновить счетчик часов
            self._update_completed_hours_for_remaining()
    
    def _recalculate_completed_hours(self):
        """Recalculate hours_completed based on actual completed schedules"""
        for wl in self.workloads:
            if self.generation_mode == 'force_reset':
                # Полный сброс
                wl.hours_completed = 0
            elif self.generation_mode == 'full_replan':
                # Пересчет на основе оставшихся завершенных
                completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                    Schedule.status.in_(['done', 'completed', 'substitution'])
                ).count()
                wl.hours_completed = completed_pairs * 2

    def _update_completed_hours_for_remaining(self):
        """Update hours_completed for remaining mode - only recalculate if necessary"""
        for wl in self.workloads:
            # Пересчет на основе всех завершенных пар
            completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status.in_(['done', 'completed', 'substitution'])
            ).count()
            new_completed_hours = completed_pairs * 2
            
            # Обновляем только если изменилось значение
            if wl.hours_completed != new_completed_hours:
                wl.hours_completed = new_completed_hours
                wl.updated_at = datetime.utcnow()

    def _analyze_final_placement(self):
        """Анализ итогового размещения дисциплин с рекомендациями"""
        unplaced_disciplines = []
        total_unplaced_hours = 0
        
        for wl in self.workloads:
            # Подсчет фактически выполненных часов из расписания
            completed_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status.in_(['done', 'completed', 'substitution'])
            ).count()
            actual_completed_hours = completed_pairs * 2
            
            # Подсчет запланированных часов
            planned_pairs = Schedule.query.filter_by(workload_id=wl.id).filter(
                Schedule.status == 'planned'
            ).count()
            planned_hours = planned_pairs * 2
            
            total_hours_in_schedule = actual_completed_hours + planned_hours
            remaining_hours = wl.total_hours - total_hours_in_schedule
            
            if remaining_hours > 0:
                teacher_name = wl.teacher.full_name if wl.teacher else "Нет преподавателя"
                
                # Анализ возможных решений
                recommendations = []
                
                # Проверка hours_per_week
                if wl.hours_per_week and wl.hours_per_week < 4:
                    recommendations.append(f"увеличить hours_per_week с {wl.hours_per_week} до 4-6")
                
                # Проверка занятости преподавателя  
                from datetime import date, timedelta
                today = date.today()
                next_month = today + timedelta(days=30)
                
                teacher_busy_count = 0
                if wl.teacher:
                    teacher_busy_count = Schedule.query.join(Workload).filter(
                        Workload.teacher_id == wl.teacher_id,
                        Schedule.date >= today,
                        Schedule.date <= next_month
                    ).count()
                
                if teacher_busy_count > 40:  # Очень занятый преподаватель
                    recommendations.append("найти дополнительного преподавателя или перераспределить нагрузку")
                
                # Проверка доступности недель
                gup_weeks = GUP.query.filter_by(
                    group_id=self.group_id,
                    academic_year_id=self.academic_year_id
                ).filter(GUP.activity_code.in_(['', None, 'УП', 'ОТ', 'ӨО'])).count()
                
                if gup_weeks < 15:
                    recommendations.append("добавить учебные недели в ГУП")
                
                if not recommendations:
                    recommendations.append("увеличить количество пар в неделю или добавить учебные недели")
                
                unplaced_disciplines.append({
                    'discipline': wl.discipline,
                    'teacher': teacher_name,
                    'remaining_hours': remaining_hours,
                    'total_hours': wl.total_hours,
                    'recommendations': recommendations
                })
                total_unplaced_hours += remaining_hours
        
        # Создание отчета
        if unplaced_disciplines:
            self.errors.append(f"🚨 КРИТИЧНО: {len(unplaced_disciplines)} дисциплин не помещаются в семестр!")
            self.errors.append(f"📊 Общий недостаток: {total_unplaced_hours} часов ({total_unplaced_hours // 2} пар)")
            
            for disc in unplaced_disciplines:
                percentage = round(disc['remaining_hours'] / disc['total_hours'] * 100, 1)
                error_msg = (f"❌ {disc['discipline']} - "
                           f"НЕ РАЗМЕЩЕНО: {disc['remaining_hours']}ч ({percentage}% от плана). "
                           f"Преподаватель: {disc['teacher']}")
                self.errors.append(error_msg)
                
                for rec in disc['recommendations']:
                    self.warnings.append(f"💡 Рекомендация для '{disc['discipline']}': {rec}")
        
        # Успешное размещение
        successfully_placed = len(self.workloads) - len(unplaced_disciplines)
        if successfully_placed > 0:
            self.warnings.append(f"✅ Успешно размещено: {successfully_placed} дисциплин")

    def _create_smart_week_plan(self, workload_pairs, week_days):
        """
        УМНОЕ ПЛАНИРОВАНИЕ НЕДЕЛИ
        
        Создает план размещения пар по дням недели с равномерным распределением
        вместо примитивного поиска первого свободного слота.
        """
        import random
        
        total_pairs = sum(wp['pairs_needed'] for wp in workload_pairs)
        days_count = len(week_days)
        
        print(f"      Планируем {total_pairs} пар на {days_count} дней")
        
        if total_pairs == 0:
            return {day: [] for day in week_days}
        
        # Создаем план для каждого дня
        daily_plan = {day: [] for day in week_days}
        
        # Получаем ограничение на пары подряд
        max_consecutive = self.group.max_consecutive_pairs or 2
        
        # Равномерно распределяем пары по дням
        pairs_per_day = total_pairs // days_count
        extra_pairs = total_pairs % days_count
        
        print(f"      Базово {pairs_per_day} пар в день, {extra_pairs} дополнительных")
        
        # Создаем список всех пар которые нужно разместить
        all_pairs_to_place = []
        for wp in workload_pairs:
            for _ in range(wp['pairs_needed']):
                all_pairs_to_place.append({
                    'workload_id': wp['workload'].id,
                    'discipline': wp['workload'].discipline,
                    'workload_obj': wp['workload']
                })
        
        # Перемешиваем для разнообразия
        random.shuffle(all_pairs_to_place)
        
        # Распределяем по дням
        pair_index = 0
        for i, day in enumerate(week_days):
            # Базовое количество + возможная добавочная пара
            target_pairs = pairs_per_day + (1 if i < extra_pairs else 0)
            
            # Добавляем пары в день с учетом ограничений
            day_pairs = []
            added = 0
            
            while added < target_pairs and pair_index < len(all_pairs_to_place):
                pair_to_add = all_pairs_to_place[pair_index]
                
                # Проверяем не слишком ли много пар этой дисциплины в день
                discipline_count_in_day = sum(1 for p in day_pairs if p['discipline'] == pair_to_add['discipline'])
                if discipline_count_in_day >= max_consecutive:
                    # Ищем другую дисциплину
                    found_other = False
                    for j in range(pair_index + 1, len(all_pairs_to_place)):
                        other_pair = all_pairs_to_place[j]
                        other_count = sum(1 for p in day_pairs if p['discipline'] == other_pair['discipline'])
                        if other_count < max_consecutive:
                            # Меняем местами
                            all_pairs_to_place[pair_index], all_pairs_to_place[j] = all_pairs_to_place[j], all_pairs_to_place[pair_index]
                            pair_to_add = all_pairs_to_place[pair_index]
                            found_other = True
                            break
                    
                    if not found_other:
                        # Не нашли подходящую, пропускаем этот день
                        break
                
                day_pairs.append(pair_to_add)
                pair_index += 1
                added += 1
            
            daily_plan[day] = day_pairs
            day_str = day.strftime('%a %d.%m')
            disciplines = [p['discipline'][:15] for p in day_pairs]
            print(f"        {day_str}: {len(day_pairs)} пар ({', '.join(disciplines) if disciplines else 'пусто'})")
        
        return daily_plan
    
    def _place_pairs_according_to_plan(self, week_plan, occupied, workload_pairs):
        """
        РАЗМЕЩЕНИЕ ПАР СОГЛАСНО ПЛАНУ
        
        Размещает пары согласно созданному плану недели с проверкой всех конфликтов.
        """
        print(f"      Размещаем пары согласно плану")
        
        for day, day_pairs in week_plan.items():
            if not day_pairs:
                continue
                
            print(f"        {day.strftime('%a %d.%m')}: размещаем {len(day_pairs)} пар")
            
            # Размещаем пары этого дня
            pair_slot = 0
            for pair_plan in day_pairs:
                workload_obj = pair_plan['workload_obj']
                placed = False
                
                # Ищем свободный слот для этой пары
                for pair_num in self.valid_pairs[pair_slot:]:
                    key = (day, pair_num)
                    
                    # Проверяем доступность преподавателя
                    teacher_id = workload_obj.teacher_id
                    if teacher_id in occupied[key]['teachers']:
                        continue
                    
                    # Проверяем лимит пар подряд
                    group_id = workload_obj.group_id
                    if self._check_consecutive_pairs_limit(day, pair_num, group_id, occupied):
                        continue
                    
                    # Ищем свободную аудиторию
                    room_id = self._find_available_room(workload_obj, key, occupied)
                    if not room_id:
                        continue
                    
                    # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - СОЗДАЕМ ПАРУ
                    self._create_schedule_entry_smart(workload_obj, day, pair_num, room_id, occupied, workload_pairs)
                    pair_slot = self.valid_pairs.index(pair_num) + 1
                    placed = True
                    
                    print(f"          РАЗМЕЩЕНО: {pair_plan['discipline'][:20]} -> пара {pair_num}")
                    break
                
                if not placed:
                    print(f"          НЕ РАЗМЕЩЕНО: {pair_plan['discipline']}")
                    self.warnings.append(f"Не удалось разместить {pair_plan['discipline']} на {day.strftime('%d.%m')}")
    
    def _find_available_room(self, workload_obj, key, occupied):
        """Находит доступную аудиторию с учетом предпочтений"""
        preferred_rooms = self._get_preferred_rooms_for_workload(workload_obj)
        
        # Сначала пробуем предпочитаемые аудитории
        if preferred_rooms:
            for room_id_pref in preferred_rooms:
                if room_id_pref not in occupied[key]['rooms']:
                    # Проверяем что аудитория существует
                    room_obj = next((r for r in self.rooms if r.id == room_id_pref), None)
                    if room_obj:
                        return room_id_pref
        
        # Если предпочитаемые заняты, ищем любую свободную
        for room in self.rooms:
            if room.id not in occupied[key]['rooms']:
                return room.id
        
        return None
    
    def _create_schedule_entry_smart(self, workload_obj, day, pair_num, room_id, occupied, workload_pairs):
        """Создает запись в расписании и обновляет статистику"""
        # Создаем запись
        schedule = Schedule(
            workload_id=workload_obj.id,
            room_id=room_id,
            date=day,
            pair_number=pair_num,
            status='planned'
        )
        db.session.add(schedule)
        self.created_count += 1

        # Обновляем occupied
        key = (day, pair_num)
        occupied[key]['teachers'].add(workload_obj.teacher_id)
        occupied[key]['rooms'].add(room_id)
        self._track_group_in_occupied(occupied, day, pair_num, workload_obj.group_id)
        
        # Обновляем статистику workload_pairs
        for wp in workload_pairs:
            if wp['workload'].id == workload_obj.id:
                wp['pairs_assigned'] += 1
                break

    def _check_consecutive_pairs_limit(self, date, pair_number, group_id, occupied):
        """
        Проверяет, не превышен ли лимит пар подряд для группы
        
        Args:
            date: Дата
            pair_number: Номер пары
            group_id: ID группы
            occupied: Словарь занятых слотов
            
        Returns:
            bool: True если лимит превышен (нельзя ставить), False если можно
        """
        from app.models import Group
        
        # Получаем настройку группы
        group = Group.query.get(group_id)
        if not group or not group.max_consecutive_pairs:
            return False  # Если настройка не задана, ограничений нет
        
        max_consecutive = group.max_consecutive_pairs
        
        # Подсчитываем сколько пар подряд уже занято для этой группы
        consecutive_count = 0
        
        # Проверяем назад от текущей пары
        check_pair = pair_number - 1
        while check_pair >= 1:
            key = (date, check_pair)
            if key in occupied and any(wl_group_id == group_id for wl_group_id in occupied[key].get('groups', [])):
                consecutive_count += 1
                check_pair -= 1
            else:
                break
        
        # Проверяем вперед от текущей пары
        check_pair = pair_number + 1
        while check_pair <= 7:  # Максимум 7 пар
            key = (date, check_pair)
            if key in occupied and any(wl_group_id == group_id for wl_group_id in occupied[key].get('groups', [])):
                consecutive_count += 1
                check_pair += 1
            else:
                break
        
        # Если добавим текущую пару, будет consecutive_count + 1
        total_consecutive = consecutive_count + 1
        
        return total_consecutive > max_consecutive

    def _track_group_in_occupied(self, occupied, date, pair_number, group_id):
        """Добавляет группу в отслеживание занятых слотов"""
        key = (date, pair_number)
        if key not in occupied:
            occupied[key] = {'teachers': set(), 'rooms': set(), 'groups': set()}
        if 'groups' not in occupied[key]:
            occupied[key]['groups'] = set()
        occupied[key]['groups'].add(group_id)

    def get_result(self):
        """Return generation result"""
        return {
            'success': len(self.errors) == 0,
            'created_count': self.created_count,
            'deleted_count': self.deleted_count,
            'errors': self.errors,
            'warnings': self.warnings,
            'generation_mode': self.generation_mode
        }


def check_teacher_conflict(teacher_id, date, pair_number, exclude_schedule_id=None):
    """Check if teacher is already assigned at this time"""
    query = Schedule.query.join(Workload).filter(
        Workload.teacher_id == teacher_id,
        Schedule.date == date,
        Schedule.pair_number == pair_number
    )
    if exclude_schedule_id:
        query = query.filter(Schedule.id != exclude_schedule_id)
    return query.first() is not None


def check_room_conflict(room_id, date, pair_number, exclude_schedule_id=None):
    """Check if room is already occupied at this time"""
    query = Schedule.query.filter(
        Schedule.room_id == room_id,
        Schedule.date == date,
        Schedule.pair_number == pair_number
    )
    if exclude_schedule_id:
        query = query.filter(Schedule.id != exclude_schedule_id)
    return query.first() is not None


def check_group_conflict(group_id, date, pair_number, exclude_schedule_id=None):
    """Check if group already has a class at this time"""
    query = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date == date,
        Schedule.pair_number == pair_number
    )
    if exclude_schedule_id:
        query = query.filter(Schedule.id != exclude_schedule_id)
    return query.first() is not None


def get_available_rooms(date, pair_number):
    """Get list of available rooms at specific time"""
    occupied_rooms = db.session.query(Schedule.room_id).filter(
        Schedule.date == date,
        Schedule.pair_number == pair_number
    ).all()
    occupied_ids = [r[0] for r in occupied_rooms]

    return Room.query.filter(~Room.id.in_(occupied_ids)).all() if occupied_ids else Room.query.all()



def update_hours_completed(workload_id):
    """Update hours_completed based on schedule entries"""
    workload = Workload.query.get(workload_id)
    if not workload:
        return

    completed_pairs = Schedule.query.filter_by(workload_id=workload_id).filter(
        Schedule.status.in_(['done', 'completed', 'substitution'])
    ).count()

    workload.hours_completed = completed_pairs * 2  # 1 pair = 2 hours
    db.session.commit()
