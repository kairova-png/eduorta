#!/usr/bin/env python3
"""
Тестирование улучшенного генератора расписания
"""

from app import create_app, db
from app.models import Group, AcademicYear
from app.services.scheduler import ScheduleGenerator

def test_improved_generator():
    """Тестируем улучшенный генератор"""
    app = create_app()
    
    with app.app_context():
        print("ТЕСТИРОВАНИЕ УЛУЧШЕННОГО ГЕНЕРАТОРА")
        print("=" * 50)
        
        # Ищем группу для тестирования
        group = Group.query.filter(Group.name.like('%БНГС 1-25%')).first()
        
        if not group:
            print("Группа БНГС 1-25 не найдена, попробуем любую группу")
            group = Group.query.first()
        
        if not group:
            print("Ошибка: Нет групп в базе данных")
            return
        
        print(f"Тестируем на группе: {group.name}")
        print(f"Смена: {group.shift} (пары: {group.shift_pairs})")
        print(f"Макс. пар подряд: {group.max_consecutive_pairs}")
        
        # Получаем текущий учебный год
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            print("Ошибка: Не установлен текущий учебный год")
            return
        
        print("\nЗАПУСК ГЕНЕРАЦИИ...")
        print("-" * 30)
        
        # Создаем генератор (используем улучшенную версию)
        generator = ScheduleGenerator(
            group_id=group.id,
            semester=2,  # 2 семестр
            academic_year_id=current_year.id,
            generation_mode='remaining'
        )
        
        # Запускаем генерацию
        try:
            success = generator.generate()
            
            print("\nРЕЗУЛЬТАТЫ:")
            print("-" * 20)
            print(f"Успех: {success}")
            print(f"Создано пар: {generator.created_count}")
            print(f"Удалено пар: {generator.deleted_count}")
            print(f"Предупреждений: {len(generator.warnings)}")
            print(f"Ошибок: {len(generator.errors)}")
            
            if generator.warnings:
                print("\nПредупреждения:")
                for warning in generator.warnings:
                    print(f"  {warning}")
            
            if generator.errors:
                print("\nОшибки:")
                for error in generator.errors:
                    print(f"  {error}")
            
            # Не сохраняем результат автоматически для тестирования
            print("\nТестирование завершено! (результаты НЕ сохранены)")
            
        except Exception as e:
            print(f"\nОШИБКА ГЕНЕРАЦИИ: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_improved_generator()