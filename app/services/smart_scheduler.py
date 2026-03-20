"""
Умный генератор расписания v2.0
Простой и понятный подход к созданию качественного расписания
"""

from datetime import datetime, timedelta, date
from app import db
from app.models import Schedule, Workload, Group, Teacher, Room, GUP, RoomPreference, WorkloadTemplate
from collections import defaultdict
import random
import json


class SmartScheduleGenerator:
    """
    Умный генератор расписания
    
    Основные принципы:
    1. Сначала планируем всю неделю целиком
    2. Равномерно распределяем пары по дням
    3. Избегаем слишком много пар подряд
    4. Оцениваем качество и улучшаем
    """
    
    def __init__(self, group_id, semester, academic_year_id, template_ids=None, workload_ids=None):
        self.group_id = group_id
        self.semester = semester
        self.academic_year_id = academic_year_id
        self.template_ids = template_ids or []
        self.workload_ids = workload_ids or []  # Specific workloads to generate for
        
        # Загружаем данные
        self.group = Group.query.get(group_id)
        self.workloads = []
        self.rooms = []
        self.room_preferences = {}  # Предпочтения аудиторий из мастера
        self.workload_templates = {}  # Шаблоны нагрузки
        
        # Результаты работы
        self.created_schedules = []
        self.errors = []
        self.warnings = []
        self.quality_score = 0
        
        print(f"Создан умный генератор для группы {self.group.name}, шаблоны: {self.template_ids}")
    
    def generate(self):
        """Главная функция генерации"""
        try:
            print("Начинаем умную генерацию расписания...")
            
            # Шаг 1: Подготовка данных
            self._load_data()
            
            # Шаг 2: Получаем недели для работы
            weeks = self._get_work_weeks()
            print(f"Найдено {len(weeks)} недель для генерации")
            
            # Шаг 3: Генерируем для каждой недели
            for week in weeks:
                print(f"Обрабатываем неделю {week.week_number} ({week.start_date})")
                self._generate_smart_week(week)
            
            # Шаг 4: Оцениваем качество
            self._assess_quality()
            
            # Шаг 5: Пробуем улучшить
            self._try_improvements()
            
            print(f"Генерация завершена! Качество: {self.quality_score}/100")
            return True
            
        except Exception as e:
            self.errors.append(f"Критическая ошибка: {str(e)}")
            print(f"Ошибка генерации: {e}")
            return False
    
    def _load_data(self):
        """Загружаем нужные данные"""
        # Загружаем нагрузки для группы и семестра
        query = Workload.query.filter(
            Workload.group_id == self.group_id,
            Workload.semester == self.semester,
            Workload.academic_year_id == self.academic_year_id
        )
        
        # Если указаны конкретные нагрузки, фильтруем только их
        if self.workload_ids:
            query = query.filter(Workload.id.in_(self.workload_ids))
            
        self.workloads = query.all()
        
        print(f"Загружено {len(self.workloads)} дисциплин")
        for wl in self.workloads:
            print(f"   - {wl.discipline}: {wl.total_hours}ч")
        
        # Загружаем доступные аудитории
        self.rooms = Room.query.all()
        print(f"Доступно {len(self.rooms)} аудиторий")
        
        # Загружаем предпочтения аудиторий из мастера генерации
        self._load_room_preferences()
        
        # Загружаем шаблоны нагрузки
        self._load_workload_templates()
    
    def _load_room_preferences(self):
        """Загружаем предпочтения аудиторий из schedule-wizard"""
        preferences = RoomPreference.query.filter_by(group_id=self.group_id).all()
        
        for pref in preferences:
            # Если дисциплина не указана, применяем ко всем
            discipline_key = pref.discipline or 'general'
            
            if discipline_key not in self.room_preferences:
                self.room_preferences[discipline_key] = []
            
            self.room_preferences[discipline_key].append({
                'room_id': pref.room_id,
                'priority': pref.priority,  # 1 = высший приоритет
                'reason': pref.reason,
                'room': Room.query.get(pref.room_id)
            })
        
        # Сортируем по приоритету (1 = высший)
        for discipline in self.room_preferences:
            self.room_preferences[discipline].sort(key=lambda x: x['priority'])
        
        if self.room_preferences:
            print(f"Загружены предпочтения аудиторий для {len(self.room_preferences)} категорий")
            for discipline, prefs in self.room_preferences.items():
                rooms_info = ", ".join([f"{p['room'].number}(п.{p['priority']})" for p in prefs[:3]])
                print(f"   - {discipline}: {rooms_info}")
        else:
            print("Предпочтения аудиторий не найдены")
    
    def _load_workload_templates(self):
        """Загружаем шаблоны нагрузки"""
        if self.template_ids:
            # Старый способ - по ID шаблонов
            templates = WorkloadTemplate.query.filter(
                WorkloadTemplate.id.in_(self.template_ids),
                WorkloadTemplate.group_id == self.group_id,
                WorkloadTemplate.semester == self.semester
            ).all()
        elif self.workload_ids:
            # Новый способ - по ID нагрузок
            templates = WorkloadTemplate.query.filter(
                WorkloadTemplate.workload_id.in_(self.workload_ids),
                WorkloadTemplate.group_id == self.group_id,
                WorkloadTemplate.semester == self.semester
            ).all()
        else:
            print("Шаблоны нагрузки не указаны")
            return
        
        # ИСПРАВЛЕНИЕ: Поддерживаем МНОЖЕСТВЕННЫЕ шаблоны для одной недели
        for template in templates:
            try:
                weeks_data = json.loads(template.distribution_json or '[]')
                for week_data in weeks_data:
                    week_num = week_data.get('week')
                    preferences = week_data.get('preferences', {})
                    
                    if week_num and preferences:
                        # Если неделя уже есть, добавляем к существующим шаблонам
                        if week_num not in self.workload_templates:
                            self.workload_templates[week_num] = {}
                        
                        # Добавляем шаблон для этой нагрузки
                        self.workload_templates[week_num][template.workload_id] = {
                            'workload_id': template.workload_id,
                            'preferences': preferences,
                            'template_name': template.name
                        }
                        
            except (json.JSONDecodeError, KeyError) as e:
                self.warnings.append(f"Ошибка загрузки шаблона {template.name}: {e}")
                continue
        
        if self.workload_templates:
            total_templates = sum(len(week_templates) for week_templates in self.workload_templates.values())
            print(f"Загружены шаблоны: {total_templates} шаблонов для {len(self.workload_templates)} недель")
            for week_num, week_templates in list(self.workload_templates.items())[:3]:
                template_names = [t['template_name'] for t in week_templates.values()]
                print(f"   - Неделя {week_num}: {', '.join(template_names)}")
        else:
            print("Рабочие шаблоны не найдены")
    
    def _get_work_weeks(self):
        """Получаем недели в которые нужно генерировать расписание"""
        weeks = GUP.query.filter(
            GUP.group_id == self.group_id,
            GUP.academic_year_id == self.academic_year_id
        ).order_by(GUP.week_number).all()

        # Собираем номера недель, для которых есть шаблоны
        template_week_numbers = set(self.workload_templates.keys())

        # Фильтруем: недели с needs_schedule ИЛИ недели с шаблонами
        work_weeks = []
        for week in weeks:
            if week.needs_schedule:
                work_weeks.append(week)
            elif week.week_number in template_week_numbers:
                # Неделя не учебная, но пользователь явно разместил пары в шаблоне
                work_weeks.append(week)
                print(f"  [+] Неделя {week.week_number} ({week.activity_code}) включена по шаблону")

        return work_weeks
    
    def _generate_smart_week(self, gup_week):
        """Умная генерация одной недели"""
        # Получаем рабочие дни (Пн-Пт)
        work_days = self._get_work_days(gup_week)
        if not work_days:
            return
        
        print(f"   Рабочих дней: {len(work_days)}")
        
        # Подсчитываем сколько пар нужно разместить
        pairs_needed = self._calculate_pairs_needed(gup_week.week_number)
        if not pairs_needed:
            print("   Пар для размещения не найдено")
            return
        
        print(f"   Нужно разместить: {sum(pairs_needed.values())} пар")
        
        # УМНОЕ ПЛАНИРОВАНИЕ: распределяем пары равномерно
        week_plan = self._create_week_plan(pairs_needed, work_days, gup_week.week_number)
        
        # Размещаем по плану
        self._place_according_to_plan(week_plan, work_days)
    
    def _get_work_days(self, gup_week):
        """Получаем рабочие дни недели (Пн-Пт)"""
        work_days = []

        current_date = gup_week.start_date
        while current_date <= gup_week.end_date:
            # Только рабочие дни (Пн-Пт)
            if current_date.weekday() < 5:
                work_days.append(current_date)
            current_date += timedelta(days=1)

        return work_days
    
    def _calculate_pairs_needed(self, week_number):
        """
        Подсчитываем сколько пар нужно для каждой дисциплины на основе шаблонов
        
        НОВАЯ ЛОГИКА:
        1. Проверяем есть ли шаблон для этой недели
        2. Если есть - используем данные из шаблона
        3. Если нет - возвращаемся к старой логике
        """
        pairs_needed = {}
        
        # Проверяем наличие шаблонов для этой недели
        if week_number in self.workload_templates:
            week_templates = self.workload_templates[week_number]
            template_names = [t['template_name'] for t in week_templates.values()]
            print(f"     [+] Используем шаблоны: {', '.join(template_names)}")
            
            # Извлекаем предпочтения из ВСЕХ шаблонов этой недели
            for workload in self.workloads:
                # Ищем шаблон для этой конкретной нагрузки
                if workload.id in week_templates:
                    template_data = week_templates[workload.id]
                    preferences = template_data.get('preferences', {})
                    
                    # Считаем общее количество пар на эту неделю из шаблона
                    total_pairs_this_week = 0
                    for day_key, day_prefs in preferences.items():
                        for slot_key, status in day_prefs.items():
                            if status == "selected":
                                total_pairs_this_week += 1
                    
                    if total_pairs_this_week > 0:
                        # Проверяем что пары еще не существуют в расписании
                        existing_pairs = Schedule.query.filter(
                            Schedule.workload_id == workload.id,
                            Schedule.date >= self._get_week_start(week_number),
                            Schedule.date <= self._get_week_end(week_number)
                        ).count()
                        
                        # Добавляем только те пары, которых еще нет
                        pairs_to_add = max(0, total_pairs_this_week - existing_pairs)
                        
                        if pairs_to_add > 0:
                            pairs_needed[workload.id] = pairs_to_add
                            print(f"     - {workload.discipline}: {pairs_to_add} пар (по шаблону {template_data['template_name']})")
            
            return pairs_needed
        
        # Если шаблоны загружены, но для этой недели шаблона нет — пропускаем
        # (генерируем ТОЛЬКО по шаблонам, не используем старую логику)
        if self.workload_templates:
            print(f"     - Неделя {week_number} не в шаблоне, пропускаем")
            return pairs_needed

        # Старая логика — только если шаблонов вообще нет
        print(f"     ! Шаблоны не загружены, используем стандартную логику")

        for workload in self.workloads:
            # Считаем уже существующие пары
            existing_pairs = Schedule.query.filter_by(workload_id=workload.id).count()
            existing_hours = existing_pairs * 2

            # Сколько часов еще нужно
            remaining_hours = workload.total_hours - existing_hours
            remaining_pairs = remaining_hours // 2

            if remaining_pairs > 0:
                # Ограничиваем количество пар в неделю
                pairs_per_week = workload.pairs_per_week or 2
                pairs_this_week = min(pairs_per_week, remaining_pairs)

                if pairs_this_week > 0:
                    pairs_needed[workload.id] = pairs_this_week
                    print(f"     - {workload.discipline}: {pairs_this_week} пар (стандартная логика)")

        return pairs_needed
    
    def _get_week_start(self, week_number):
        """Получить дату начала недели по номеру"""
        gup_week = GUP.query.filter_by(
            academic_year_id=self.academic_year_id,
            week_number=week_number
        ).first()
        return gup_week.start_date if gup_week else None
    
    def _get_week_end(self, week_number):
        """Получить дату конца недели по номеру"""
        gup_week = GUP.query.filter_by(
            academic_year_id=self.academic_year_id,
            week_number=week_number
        ).first()
        return gup_week.end_date if gup_week else None
    
    def _create_week_plan(self, pairs_needed, work_days, week_number=None):
        """
        УМНОЕ ПЛАНИРОВАНИЕ НЕДЕЛИ
        
        НОВАЯ ЛОГИКА:
        1. Если есть шаблон - используем его точное распределение
        2. Если нет шаблона - возвращаемся к старой логике равномерного распределения
        """
        total_pairs = sum(pairs_needed.values())
        days_count = len(work_days)
        
        print(f"   Планируем размещение {total_pairs} пар на {days_count} дней")
        
        # Проверяем наличие шаблонов для этой недели
        week_templates = None
        if week_number and week_number in self.workload_templates:
            week_templates = self.workload_templates[week_number]
            template_names = [t['template_name'] for t in week_templates.values()]
            print(f"   [+] Используем шаблоны: {', '.join(template_names)}")
            
            # ПРОСТОЕ ТОЧНОЕ РАЗМЕЩЕНИЕ ПО ШАБЛОНУ
            return self._create_multi_template_based_plan(week_templates, work_days, pairs_needed)
        
        # СТАРАЯ ЛОГИКА: Равномерное распределение (если нет шаблона)
        print(f"   ! Шаблон для недели {week_number} не найден, используем равномерное распределение")

        # Создаем план для каждого дня в формате {day: {pair_number: workload_id}}
        precise_schedule = {}

        # Получаем доступные пары для группы
        valid_pairs = self.group.shift_pairs or [1, 2, 3, 4]
        max_consecutive = self.group.max_consecutive_pairs or 2

        # Распределяем пары равномерно по дням
        pairs_per_day = total_pairs // days_count
        extra_pairs = total_pairs % days_count

        print(f"   Базово {pairs_per_day} пар в день, {extra_pairs} дополнительных")

        # Создаем список всех пар которые нужно разместить
        all_pairs_to_place = []
        for workload_id, count in pairs_needed.items():
            for _ in range(count):
                all_pairs_to_place.append(workload_id)

        # Перемешиваем для разнообразия
        random.shuffle(all_pairs_to_place)

        # Распределяем по дням
        pair_index = 0
        for i, day in enumerate(work_days):
            # Базовое количество + возможная добавочная пара
            target_pairs = pairs_per_day + (1 if i < extra_pairs else 0)

            precise_schedule[day] = {}
            slot_index = 0
            added = 0

            while added < target_pairs and pair_index < len(all_pairs_to_place) and slot_index < len(valid_pairs):
                workload_id = all_pairs_to_place[pair_index]
                pair_number = valid_pairs[slot_index]

                # Проверяем не слишком ли много пар этой дисциплины в день
                discipline_count_in_day = sum(1 for wid in precise_schedule[day].values() if wid == workload_id)
                if discipline_count_in_day >= max_consecutive:
                    # Ищем другую дисциплину
                    found_other = False
                    for j in range(pair_index + 1, len(all_pairs_to_place)):
                        other_workload_id = all_pairs_to_place[j]
                        other_count = sum(1 for wid in precise_schedule[day].values() if wid == other_workload_id)
                        if other_count < max_consecutive:
                            # Меняем местами
                            all_pairs_to_place[pair_index], all_pairs_to_place[j] = all_pairs_to_place[j], all_pairs_to_place[pair_index]
                            workload_id = all_pairs_to_place[pair_index]
                            found_other = True
                            break

                    if not found_other:
                        # Не нашли подходящую, пропускаем этот слот
                        slot_index += 1
                        continue

                precise_schedule[day][pair_number] = workload_id
                pair_index += 1
                slot_index += 1
                added += 1

            print(f"     {day.strftime('%a')}: {len(precise_schedule[day])} пар")

        return precise_schedule
    
    def _create_multi_template_based_plan(self, week_templates, work_days, pairs_needed):
        """
        ПРОСТОЕ ТОЧНОЕ РАЗМЕЩЕНИЕ ПО ШАБЛОНУ
        
        Просто смотрим где в шаблоне отмечены "selected" слоты 
        и размещаем пары ТОЧНО в эти слоты.
        
        week_templates - шаблоны для всех нагрузок на этой неделе
        """
        # Создаем план с конкретным временем для каждой пары
        precise_schedule = {}  # {day: {pair_number: workload_id}}
        
        print(f"   [+] ТОЧНОЕ размещение по {len(week_templates)} шаблонам")
        
        # Проходим по каждому дню недели
        for day in work_days:
            weekday = day.weekday()  # 0 = понедельник
            day_key = str(weekday)
            
            print(f"     День {weekday} ({day.strftime('%d.%m')})")
            precise_schedule[day] = {}
            
            # Проходим по всем шаблонам
            for workload_id, template_data in week_templates.items():
                preferences = template_data.get('preferences', {})
                template_name = template_data.get('template_name', 'Unknown')
                
                # Если в шаблоне есть этот день
                if day_key in preferences:
                    day_prefs = preferences[day_key]
                    
                    # Проходим по каждому слоту
                    for slot_str, status in day_prefs.items():
                        if status == "selected":
                            pair_number = int(slot_str)
                            
                            # Проверяем что слот свободен
                            if pair_number not in precise_schedule[day]:
                                precise_schedule[day][pair_number] = workload_id
                                print(f"       + {self._get_workload_name(workload_id)} ({template_name}) -> пара {pair_number}")
                            else:
                                existing_workload = precise_schedule[day][pair_number]
                                print(f"       ! Конфликт в паре {pair_number}: {self._get_workload_name(workload_id)} vs {self._get_workload_name(existing_workload)}")
            
            pairs_count = len(precise_schedule[day])
            print(f"     Итого на день {weekday}: {pairs_count} пар")
        
        return precise_schedule
    
    def _create_template_based_plan(self, template_data, work_days, pairs_needed):
        """
        Создаем план недели на основе шаблона нагрузки (старая функция для совместимости)
        
        template_data содержит данные из WorkloadTemplate:
        {
            'workload_id': 766,
            'preferences': {
                "0": {"1": "selected", "2": "selected"},  # день 0 (пн), пары 1,2
                "1": {"1": "selected", "2": "selected"}   # день 1 (вт), пары 1,2
            },
            'template_name': 'Название шаблона'
        }
        """
        # Конвертируем в новый формат и используем новую функцию
        workload_id = template_data.get('workload_id')
        week_templates = {workload_id: template_data}
        return self._create_multi_template_based_plan(week_templates, work_days, pairs_needed)
    
    def _get_workload_name(self, workload_id):
        """Получаем название дисциплины для логирования"""
        try:
            from app.models import Workload
            workload = Workload.query.get(workload_id)
            return workload.discipline if workload else f"ID:{workload_id}"
        except:
            return f"ID:{workload_id}"
    
    def _place_according_to_plan(self, precise_schedule, work_days):
        """ТОЧНОЕ РАЗМЕЩЕНИЕ по шаблону (precise_schedule)"""
        
        for day, day_schedule in precise_schedule.items():
            print(f"   Размещаем на {day}: {len(day_schedule)} пар ТОЧНО по шаблону")
            
            # Проверяем уже существующие пары на этот день
            existing_pairs = {}
            existing_schedules = Schedule.query.filter(
                Schedule.date == day
            ).join(Workload).filter(
                Workload.group_id == self.group_id
            ).all()
            
            for schedule in existing_schedules:
                existing_pairs[schedule.pair_number] = schedule.workload_id
            
            # Размещаем пары ТОЧНО в заданные слоты
            for pair_number, workload_id in day_schedule.items():
                
                # Проверяем не занят ли слот
                if pair_number in existing_pairs:
                    existing_workload_id = existing_pairs[pair_number]
                    if existing_workload_id == workload_id:
                        print(f"     Пара {pair_number}: {self._get_workload_name(workload_id)} уже размещена")
                        continue
                    else:
                        # Получаем детали существующей пары
                        existing_workload = Workload.query.get(existing_workload_id)
                        existing_teacher = existing_workload.teacher.full_name if existing_workload and existing_workload.teacher else 'N/A'
                        existing_disc = existing_workload.discipline if existing_workload else 'N/A'
                        new_disc = self._get_workload_name(workload_id)

                        conflict_msg = (f"Конфликт в паре {pair_number} на {day.strftime('%d.%m')}: "
                                       f"слот занят дисциплиной '{existing_disc}' ({existing_teacher}), "
                                       f"не удалось разместить '{new_disc}'")
                        print(f"     [!] {conflict_msg}")
                        self.warnings.append(conflict_msg)
                        continue

                # Проверяем доступность преподавателя и аудитории
                if self._can_place_pair(workload_id, day, pair_number):
                    # Создаем пару ТОЧНО в этом слоте
                    self._create_schedule_entry(workload_id, day, pair_number)
                    print(f"     + Пара {pair_number}: {self._get_workload_name(workload_id)} - РАЗМЕЩЕНО")
                else:
                    # Получаем детальную информацию о конфликтах
                    workload = Workload.query.get(workload_id)
                    conflict_details = self._get_conflict_details(workload_id, day, pair_number)

                    if conflict_details:
                        details_str = "; ".join(conflict_details)
                        conflict_msg = f"Не удалось разместить '{workload.discipline}' в пару {pair_number} на {day.strftime('%d.%m')}: {details_str}"
                    else:
                        conflict_msg = f"Не удалось разместить '{workload.discipline}' в пару {pair_number} на {day.strftime('%d.%m')}"

                    self.warnings.append(conflict_msg)
                    print(f"     [!] {conflict_msg}")
    
    def _can_place_pair(self, workload_id, day, pair_num):
        """Проверяем можно ли разместить пару в указанное время"""
        workload = Workload.query.get(workload_id)

        # Проверяем преподавателя
        teacher_conflict = Schedule.query.filter(
            Schedule.date == day,
            Schedule.pair_number == pair_num
        ).join(Workload).filter(
            Workload.teacher_id == workload.teacher_id
        ).first()

        if teacher_conflict:
            return False

        # Проверяем есть ли свободная аудитория
        available_rooms = self._get_available_rooms(day, pair_num)
        if not available_rooms:
            return False

        return True

    def _get_conflict_details(self, workload_id, day, pair_num):
        """Получаем детальную информацию о конфликтах"""
        workload = Workload.query.get(workload_id)
        conflicts = []

        # 1. Проверяем конфликт преподавателя
        teacher_conflict = Schedule.query.filter(
            Schedule.date == day,
            Schedule.pair_number == pair_num
        ).join(Workload).filter(
            Workload.teacher_id == workload.teacher_id
        ).first()

        if teacher_conflict:
            conflict_workload = teacher_conflict.workload
            conflict_group = conflict_workload.group.name if conflict_workload.group else 'N/A'
            teacher_name = workload.teacher.full_name if workload.teacher else 'N/A'
            conflicts.append(
                f"Преподаватель {teacher_name} занят (ведёт {conflict_workload.discipline} у {conflict_group})"
            )

        # 2. Проверяем конфликт группы (другая дисциплина у этой же группы)
        group_conflict = Schedule.query.filter(
            Schedule.date == day,
            Schedule.pair_number == pair_num
        ).join(Workload).filter(
            Workload.group_id == workload.group_id,
            Workload.id != workload_id
        ).first()

        if group_conflict:
            conflict_workload = group_conflict.workload
            group_name = workload.group.name if workload.group else 'N/A'
            conflict_teacher = conflict_workload.teacher.full_name if conflict_workload.teacher else 'N/A'
            conflicts.append(
                f"Группа {group_name} занята ({conflict_workload.discipline} с {conflict_teacher})"
            )

        # 3. Проверяем доступность аудиторий
        available_rooms = self._get_available_rooms(day, pair_num)
        if not available_rooms:
            # Показываем какие аудитории заняты
            occupied = Schedule.query.filter(
                Schedule.date == day,
                Schedule.pair_number == pair_num,
                Schedule.room_id.isnot(None)
            ).all()

            if occupied:
                room_info = []
                for s in occupied[:3]:  # Показываем до 3 занятых аудиторий
                    room_name = s.room.number if s.room else 'N/A'
                    occ_group = s.workload.group.name if s.workload and s.workload.group else 'N/A'
                    room_info.append(f"{room_name} ({occ_group})")

                if len(occupied) > 3:
                    room_info.append(f"и ещё {len(occupied) - 3}")

                conflicts.append(f"Нет свободных аудиторий. Заняты: {', '.join(room_info)}")
            else:
                conflicts.append("Нет доступных аудиторий в системе")

        return conflicts
    
    def _get_available_rooms(self, day, pair_num):
        """Получаем список свободных аудиторий"""
        occupied_rooms = Schedule.query.filter(
            Schedule.date == day,
            Schedule.pair_number == pair_num,
            Schedule.room_id.isnot(None)
        ).all()
        
        occupied_room_ids = [s.room_id for s in occupied_rooms]
        
        available = [room for room in self.rooms if room.id not in occupied_room_ids]
        return available
    
    def _create_schedule_entry(self, workload_id, day, pair_num):
        """Создаем запись в расписании"""
        workload = Workload.query.get(workload_id)
        
        # Выбираем лучшую аудитории
        available_rooms = self._get_available_rooms(day, pair_num)
        room = self._choose_best_room(workload, available_rooms)
        
        # Создаем запись
        schedule = Schedule(
            workload_id=workload_id,
            room_id=room.id if room else None,
            date=day,
            pair_number=pair_num,
            status='planned'
        )
        
        db.session.add(schedule)
        self.created_schedules.append(schedule)
    
    def _choose_best_room(self, workload, available_rooms):
        """Выбираем лучшую аудиторию из доступных с учетом предпочтений"""
        if not available_rooms:
            return None
        
        # Получаем предпочтения для конкретной дисциплины
        discipline_prefs = self.room_preferences.get(workload.discipline, [])
        
        # Если нет предпочтений для дисциплины, используем общие
        if not discipline_prefs:
            discipline_prefs = self.room_preferences.get('general', [])
        
        # Если есть предпочтения, пробуем найти предпочитаемую аудиторию среди доступных
        if discipline_prefs:
            available_room_ids = {room.id for room in available_rooms}
            
            # Проходим по предпочтениям в порядке приоритета (1 = высший)
            for pref in discipline_prefs:
                if pref['room_id'] in available_room_ids:
                    preferred_room = next(room for room in available_rooms if room.id == pref['room_id'])
                    print(f"      Выбрана предпочитаемая аудитория {preferred_room.number} для {workload.discipline}")
                    return preferred_room
            
            print(f"      Предпочитаемые аудитории заняты, берем доступную")
        
        # Если предпочтений нет или они недоступны, берем первую доступную
        return available_rooms[0]
    
    def _assess_quality(self):
        """Оцениваем качество созданного расписания"""
        print("Оцениваем качество расписания...")
        
        quality_score = 100
        
        # Проверяем равномерность распределения
        evenness_penalty = self._check_distribution_evenness()
        quality_score -= evenness_penalty
        
        # Проверяем количество "окон"
        gaps_penalty = self._count_gaps()
        quality_score -= gaps_penalty
        
        # Проверяем использование предпочитаемых аудиторий
        room_bonus = self._check_room_preferences()
        quality_score += room_bonus
        
        self.quality_score = max(0, quality_score)
        print(f"   Итоговое качество: {self.quality_score}/100")
        
        if evenness_penalty > 0:
            print(f"   Неравномерность: -{evenness_penalty} баллов")
        if gaps_penalty > 0:
            print(f"   Окна в расписании: -{gaps_penalty} баллов")
        if room_bonus > 0:
            print(f"   Хорошие аудитории: +{room_bonus} баллов")
    
    def _check_distribution_evenness(self):
        """Проверяем равномерность распределения по дням"""
        # TODO: Реализовать проверку равномерности
        return 0
    
    def _count_gaps(self):
        """Считаем количество "окон" в расписании"""
        # TODO: Реализовать подсчет окон
        return 0
    
    def _check_room_preferences(self):
        """Проверяем использование предпочитаемых аудиторий"""
        if not self.room_preferences or not self.created_schedules:
            return 0
        
        total_schedules = len(self.created_schedules)
        preferred_used = 0
        
        for schedule in self.created_schedules:
            if schedule.room_id and schedule.workload:
                # Проверяем, использована ли предпочитаемая аудитория
                discipline_prefs = self.room_preferences.get(schedule.workload.discipline, [])
                if not discipline_prefs:
                    discipline_prefs = self.room_preferences.get('general', [])
                
                # Если эта аудитория в списке предпочтений
                for pref in discipline_prefs:
                    if pref['room_id'] == schedule.room_id:
                        preferred_used += 1
                        break
        
        if total_schedules > 0:
            preference_score = (preferred_used / total_schedules) * 100
            penalty = max(0, 20 - preference_score)  # Штраф до 20 баллов
            print(f"   Предпочтения аудиторий: {preferred_used}/{total_schedules} ({preference_score:.1f}%), штраф: {penalty:.1f}")
            return penalty
        
        return 0
    
    def _try_improvements(self):
        """Пробуем улучшить расписание"""
        print("Ищем возможности для улучшения...")
        
        if self.quality_score >= 80:
            print("   Расписание уже хорошего качества")
            return
        
        # TODO: Реализовать алгоритмы улучшения
        print("   Алгоритмы улучшения в разработке")
    
    def save_results(self):
        """Сохраняем результаты в базу данных"""
        try:
            db.session.commit()
            print(f"Сохранено {len(self.created_schedules)} новых пар")
            return True
        except Exception as e:
            db.session.rollback()
            self.errors.append(f"Ошибка сохранения: {str(e)}")
            print(f"Ошибка сохранения: {e}")
            return False