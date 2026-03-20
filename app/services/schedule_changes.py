"""
Сервис для управления изменениями в расписании
Поддерживает замены, переносы и отмены пар с учетом нагрузки преподавателей
"""

from datetime import datetime, date
from sqlalchemy import and_
from app import db
from app.models import Schedule, ScheduleChange, Workload, Teacher, VacantHours


class ScheduleChangeService:
    
    @staticmethod
    def create_substitution(schedule_id, substitute_teacher_id, reason, changed_by, notes=None):
        """
        Создать замену преподавателя
        
        Args:
            schedule_id: ID занятия для замены
            substitute_teacher_id: ID преподавателя-заменителя
            reason: Причина замены
            changed_by: Кто вносит изменение
            notes: Дополнительные заметки
            
        Returns:
            dict: Результат операции
        """
        try:
            schedule = Schedule.query.get(schedule_id)
            if not schedule:
                return {'success': False, 'error': 'Занятие не найдено'}
                
            substitute_teacher = Teacher.query.get(substitute_teacher_id)
            if not substitute_teacher:
                return {'success': False, 'error': 'Преподаватель-заменитель не найден'}
            
            # Проверяем, что заменитель не тот же преподаватель
            if schedule.workload.teacher_id == substitute_teacher_id:
                return {'success': False, 'error': 'Нельзя заменить преподавателя самим собой'}
            
            # Проверяем конфликты с заменителем
            conflict = Schedule.query.filter(
                and_(
                    Schedule.date == schedule.date,
                    Schedule.pair_number == schedule.pair_number,
                    Schedule.workload.has(teacher_id=substitute_teacher_id),
                    Schedule.status.in_(['planned', 'done', 'substitution'])
                )
            ).first()
            
            if conflict:
                return {'success': False, 'error': f'У преподавателя {substitute_teacher.full_name} уже есть занятие в это время'}
            
            # Сохраняем исходное состояние
            old_status = schedule.status
            old_teacher_id = schedule.workload.teacher_id
            
            # Создаем запись об изменении
            change_record = ScheduleChange(
                schedule_id=schedule_id,
                change_type='substitution',
                old_status=old_status,
                old_teacher_id=old_teacher_id,
                new_status='substitution',
                new_teacher_id=substitute_teacher_id,
                reason=reason,
                notes=notes,
                changed_by=changed_by
            )
            
            # Создаем запись о вакантных часах
            vacant_hour_record = VacantHours(
                original_teacher_id=schedule.workload.teacher_id,
                substitute_teacher_id=substitute_teacher_id,
                workload_id=schedule.workload_id,
                schedule_id=schedule_id,
                date=schedule.date,
                reason=reason,
                hours=2
            )
            
            # Обновляем занятие
            schedule.status = 'substitution'
            schedule.substitute_teacher_id = substitute_teacher_id
            schedule.change_reason = reason
            schedule.change_type = 'substitution'
            schedule.updated_at = datetime.utcnow()
            
            # ВАЖНО: Уменьшаем нагрузку основного преподавателя
            workload = schedule.workload
            if workload.total_hours >= 2:
                workload.total_hours -= 2
                workload.updated_at = datetime.utcnow()
            
            # Создаем или обновляем нагрузку замен для заменяющего преподавателя
            substitute_workload = Workload.query.filter_by(
                teacher_id=substitute_teacher_id,
                group_id=workload.group_id,
                discipline=f"ЗАМЕНА: {workload.discipline}",
                lesson_type=workload.lesson_type,
                semester=workload.semester,
                academic_year_id=workload.academic_year_id
            ).first()
            
            if substitute_workload:
                # Увеличиваем часы существующей нагрузки замен
                substitute_workload.total_hours += 2
                substitute_workload.hours_completed += 2  # Замена считается выполненной
                substitute_workload.updated_at = datetime.utcnow()
            else:
                # Создаем новую нагрузку замен
                substitute_workload = Workload(
                    teacher_id=substitute_teacher_id,
                    group_id=workload.group_id,
                    academic_year_id=workload.academic_year_id,
                    discipline=f"ЗАМЕНА: {workload.discipline}",
                    lesson_type=workload.lesson_type,
                    semester=workload.semester,
                    total_hours=2,
                    hours_completed=2,  # Замена считается выполненной
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(substitute_workload)
            
            db.session.add(change_record)
            db.session.add(vacant_hour_record)
            db.session.commit()
            
            return {
                'success': True, 
                'message': f'Замена назначена: {substitute_teacher.full_name}',
                'change_id': change_record.id
            }
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Ошибка при создании замены: {str(e)}'}
    
    @staticmethod
    def reschedule_class(schedule_id, new_date, new_pair_number, new_room_id, reason, changed_by, notes=None):
        """
        Перенести занятие на другое время
        
        Args:
            schedule_id: ID занятия для переноса
            new_date: Новая дата
            new_pair_number: Новый номер пары
            new_room_id: ID новой аудитории (опционально)
            reason: Причина переноса
            changed_by: Кто вносит изменение
            notes: Дополнительные заметки
            
        Returns:
            dict: Результат операции
        """
        try:
            schedule = Schedule.query.get(schedule_id)
            if not schedule:
                return {'success': False, 'error': 'Занятие не найдено'}
                
            # Проверяем, что новое время отличается от текущего
            if schedule.date == new_date and schedule.pair_number == new_pair_number:
                return {'success': False, 'error': 'Новое время должно отличаться от текущего'}
            
            # Проверяем конфликты с преподавателем
            teacher_conflict = Schedule.query.filter(
                and_(
                    Schedule.date == new_date,
                    Schedule.pair_number == new_pair_number,
                    Schedule.workload.has(teacher_id=schedule.workload.teacher_id),
                    Schedule.status.in_(['planned', 'done', 'substitution']),
                    Schedule.id != schedule_id
                )
            ).first()
            
            if teacher_conflict:
                return {'success': False, 'error': f'У преподавателя уже есть занятие в это время'}
            
            # Проверяем конфликты с группой
            group_conflict = Schedule.query.filter(
                and_(
                    Schedule.date == new_date,
                    Schedule.pair_number == new_pair_number,
                    Schedule.workload.has(group_id=schedule.workload.group_id),
                    Schedule.status.in_(['planned', 'done', 'substitution']),
                    Schedule.id != schedule_id
                )
            ).first()
            
            if group_conflict:
                return {'success': False, 'error': f'У группы уже есть занятие в это время'}
            
            # Проверяем конфликты с аудиторией
            if new_room_id:
                room_conflict = Schedule.query.filter(
                    and_(
                        Schedule.date == new_date,
                        Schedule.pair_number == new_pair_number,
                        Schedule.room_id == new_room_id,
                        Schedule.status.in_(['planned', 'done', 'substitution']),
                        Schedule.id != schedule_id
                    )
                ).first()
                
                if room_conflict:
                    return {'success': False, 'error': f'Аудитория уже занята в это время'}
            
            # Сохраняем исходное состояние
            old_date = schedule.date
            old_pair_number = schedule.pair_number
            old_room_id = schedule.room_id
            old_status = schedule.status

            # Создаем запись об изменении (история)
            change_record = ScheduleChange(
                schedule_id=schedule_id,
                change_type='reschedule',
                old_status=old_status,
                old_date=old_date,
                old_pair_number=old_pair_number,
                old_room_id=old_room_id,
                new_status='planned',
                new_date=new_date,
                new_pair_number=new_pair_number,
                new_room_id=new_room_id or old_room_id,
                reason=reason,
                notes=notes,
                changed_by=changed_by
            )

            # Перемещаем занятие на новую дату/пару
            schedule.date = new_date
            schedule.pair_number = new_pair_number
            if new_room_id:
                schedule.room_id = new_room_id
            schedule.status = 'planned'
            schedule.change_reason = reason
            schedule.change_type = 'reschedule'
            schedule.updated_at = datetime.utcnow()

            db.session.add(change_record)
            db.session.commit()

            return {
                'success': True,
                'message': f'Занятие перенесено на {new_date.strftime("%d.%m.%Y")} пара {new_pair_number}',
                'change_id': change_record.id
            }
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Ошибка при переносе занятия: {str(e)}'}
    
    @staticmethod
    def cancel_class(schedule_id, reason, changed_by, return_to_workload=True, notes=None, free_slot=False):
        """
        Отменить занятие

        Args:
            schedule_id: ID занятия для отмены
            reason: Причина отмены
            changed_by: Кто вносит изменение
            return_to_workload: Вернуть ли часы в нагрузку
            notes: Дополнительные заметки
            free_slot: Освободить слот (удалить запись) или оставить карточку

        Returns:
            dict: Результат операции
        """
        try:
            schedule = Schedule.query.get(schedule_id)
            if not schedule:
                return {'success': False, 'error': 'Занятие не найдено'}

            if schedule.status in ['cancelled', 'done', 'completed']:
                return {'success': False, 'error': f'Занятие уже {schedule.status}'}

            old_status = schedule.status

            # ВАЖНО: Если отменяем замену, нужно обработать VacantHours
            if old_status == 'substitution':
                vacant_record = VacantHours.query.filter_by(schedule_id=schedule_id).first()
                if vacant_record:
                    print(f"Отменяем замену, обрабатываем VacantHours для schedule {schedule_id}")

                    # Возвращаем часы основному преподавателю
                    workload = schedule.workload
                    workload.total_hours += vacant_record.hours
                    workload.updated_at = datetime.utcnow()

                    # Уменьшаем нагрузку заменителя
                    substitute_workload = Workload.query.filter_by(
                        teacher_id=vacant_record.substitute_teacher_id,
                        group_id=workload.group_id,
                        discipline=f"ЗАМЕНА: {workload.discipline}",
                        lesson_type=workload.lesson_type,
                        semester=workload.semester,
                        academic_year_id=workload.academic_year_id
                    ).first()

                    if substitute_workload:
                        if substitute_workload.total_hours <= 2:
                            db.session.delete(substitute_workload)
                            print(f"Удалена нагрузка замен для преподавателя {vacant_record.substitute_teacher_id}")
                        else:
                            substitute_workload.total_hours -= vacant_record.hours
                            substitute_workload.hours_completed -= vacant_record.hours
                            substitute_workload.updated_at = datetime.utcnow()
                            print(f"Уменьшена нагрузка замен на {vacant_record.hours} часов")

                    db.session.delete(vacant_record)
                    print("VacantHours запись удалена при отмене замены")

            # Если нужно вернуть часы в нагрузку
            if return_to_workload and schedule.workload:
                if old_status in ['done', 'completed', 'substitution']:
                    if schedule.workload.hours_completed >= 2:
                        schedule.workload.hours_completed -= 2
                        schedule.workload.updated_at = datetime.utcnow()

            if free_slot:
                # Освободить слот: сохраняем историю, удаляем запись
                # Сначала удаляем все связанные schedule_changes
                ScheduleChange.query.filter_by(schedule_id=schedule_id).delete()
                ScheduleChange.query.filter_by(related_schedule_id=schedule_id).delete()

                # Очищаем ссылки в других записях расписания
                Schedule.query.filter_by(original_schedule_id=schedule_id).update({'original_schedule_id': None})
                Schedule.query.filter_by(rescheduled_to_id=schedule_id).update({'rescheduled_to_id': None})

                # Удаляем связанные vacant_hours
                VacantHours.query.filter_by(schedule_id=schedule_id).delete()

                # Удаляем запись расписания
                db.session.delete(schedule)
                db.session.commit()

                return {
                    'success': True,
                    'message': f'Занятие отменено, слот освобождён. {"Часы возвращены в нагрузку" if return_to_workload else "Часы не возвращены"}',
                }
            else:
                # Обычная отмена: карточка остаётся с пометкой "отменена"
                change_record = ScheduleChange(
                    schedule_id=schedule_id,
                    change_type='cancellation',
                    old_status=old_status,
                    new_status='cancelled',
                    reason=reason,
                    notes=f"Возврат в нагрузку: {'Да' if return_to_workload else 'Нет'}. {notes or ''}",
                    changed_by=changed_by
                )

                schedule.status = 'cancelled'
                schedule.change_reason = reason
                schedule.change_type = 'cancellation'
                schedule.updated_at = datetime.utcnow()

                db.session.add(change_record)
                db.session.commit()

                return {
                    'success': True,
                    'message': f'Занятие отменено. {"Часы возвращены в нагрузку" if return_to_workload else "Часы не возвращены"}',
                    'change_id': change_record.id
                }

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Ошибка при отмене занятия: {str(e)}'}
    
    @staticmethod
    def restore_class(schedule_id, changed_by, notes=None):
        """
        Восстановить отмененное или перенесенное занятие
        
        Args:
            schedule_id: ID занятия для восстановления
            changed_by: Кто вносит изменение
            notes: Дополнительные заметки
            
        Returns:
            dict: Результат операции
        """
        try:
            schedule = Schedule.query.get(schedule_id)
            if not schedule:
                return {'success': False, 'error': 'Занятие не найдено'}
                
            if schedule.status not in ['cancelled', 'rescheduled', 'substitution']:
                return {'success': False, 'error': f'Занятие не может быть восстановлено (статус: {schedule.status})'}
            
            old_status = schedule.status
            
            # ВАЖНО: Проверяем VacantHours независимо от статуса!
            # Могут быть ситуации когда замену отменили, но VacantHours остались
            vacant_record = VacantHours.query.filter_by(schedule_id=schedule_id).first()
            if vacant_record:
                print(f"Найдена VacantHours запись для schedule {schedule_id}, восстанавливаем замену...")
                
                # Возвращаем часы в нагрузку основного преподавателя
                workload = schedule.workload
                workload.total_hours += vacant_record.hours
                workload.updated_at = datetime.utcnow()
                
                # ИСПРАВЛЕНО: Теперь НЕ создаем отдельные замещающие нагрузки
                # Поэтому при восстановлении только возвращаем часы основной нагрузке
                # Старые замещающие нагрузки (если есть) можно удалить для очистки
                
                old_substitute_workloads = Workload.query.filter(
                    Workload.teacher_id == vacant_record.substitute_teacher_id,
                    Workload.group_id == workload.group_id,
                    Workload.discipline.like(f"ЗАМЕНА%{workload.discipline}%"),
                    Workload.semester == workload.semester
                ).all()
                
                # Удаляем старые записи замен из нагрузок (очистка от предыдущих версий)
                for old_substitute_workload in old_substitute_workloads:
                    print(f"Удаляем устаревшую замещающую нагрузку: {old_substitute_workload.discipline}")
                    db.session.delete(old_substitute_workload)
                
                db.session.delete(vacant_record)
                print("VacantHours запись удалена")
            
            # Если восстанавливаем перенесенное занятие, нужно удалить отработку
            if old_status == 'rescheduled' and schedule.rescheduled_to_id:
                makeup_schedule = Schedule.query.get(schedule.rescheduled_to_id)
                if makeup_schedule and makeup_schedule.status == 'planned':
                    db.session.delete(makeup_schedule)
            
            # Создаем запись об изменении
            change_record = ScheduleChange(
                schedule_id=schedule_id,
                change_type='restoration',
                old_status=old_status,
                new_status='planned',
                reason='Восстановление занятия',
                notes=notes,
                changed_by=changed_by
            )
            
            # Восстанавливаем занятие
            schedule.status = 'planned'
            schedule.substitute_teacher_id = None
            schedule.change_reason = None
            schedule.change_type = None
            schedule.original_schedule_id = None
            schedule.rescheduled_to_id = None
            schedule.is_makeup = False
            schedule.updated_at = datetime.utcnow()
            
            db.session.add(change_record)
            db.session.commit()
            
            return {
                'success': True, 
                'message': 'Занятие восстановлено',
                'change_id': change_record.id
            }
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': f'Ошибка при восстановлении занятия: {str(e)}'}
    
    @staticmethod
    def get_change_history(schedule_id):
        """
        Получить историю изменений занятия
        
        Args:
            schedule_id: ID занятия
            
        Returns:
            list: Список изменений
        """
        return ScheduleChange.query.filter_by(schedule_id=schedule_id).order_by(ScheduleChange.changed_at.desc()).all()
    
    @staticmethod
    def get_teacher_substitutions(teacher_id, start_date=None, end_date=None):
        """
        Получить замены преподавателя за период
        
        Args:
            teacher_id: ID преподавателя
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
            
        Returns:
            list: Список занятий с заменами
        """
        query = Schedule.query.filter(
            and_(
                Schedule.substitute_teacher_id == teacher_id,
                Schedule.status == 'substitution'
            )
        )
        
        if start_date:
            query = query.filter(Schedule.date >= start_date)
        if end_date:
            query = query.filter(Schedule.date <= end_date)
            
        return query.order_by(Schedule.date, Schedule.pair_number).all()
    
    @staticmethod
    def get_teacher_vacant_hours(teacher_id, start_date=None, end_date=None):
        """
        Получить вакантные часы преподавателя (когда его заменяли)
        
        Args:
            teacher_id: ID преподавателя
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
            
        Returns:
            list: Список занятий где преподавателя заменяли
        """
        query = Schedule.query.join(Workload).filter(
            and_(
                Workload.teacher_id == teacher_id,
                Schedule.status == 'substitution',
                Schedule.substitute_teacher_id.isnot(None),
                Schedule.substitute_teacher_id != teacher_id
            )
        )
        
        if start_date:
            query = query.filter(Schedule.date >= start_date)
        if end_date:
            query = query.filter(Schedule.date <= end_date)
            
        return query.order_by(Schedule.date, Schedule.pair_number).all()
    @staticmethod
    def complete_schedule(schedule_id, notes=None):
        """
        Завершить занятие (отметить как последнюю пару)
        
        Args:
            schedule_id: ID занятия
            notes: Примечания к завершению
            
        Returns:
            bool: Успех операции
        """
        try:
            schedule = Schedule.query.get(schedule_id)
            if not schedule:
                return False
            
            # Устанавливаем статус "completed"
            schedule.status = 'completed'
            schedule.change_reason = notes or 'Отмечена как последняя пара'
            schedule.change_type = 'completed'
            
            # Создаем запись об изменении
            change = ScheduleChange(
                schedule_id=schedule_id,
                change_type='Завершение',
                reason=notes or 'Отмечена как последняя пара',
                changed_by='Система',  # TODO: получать текущего пользователя
                notes=notes
            )
            
            db.session.add(change)
            db.session.commit()
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка при завершении занятия: {e}")
            return False
