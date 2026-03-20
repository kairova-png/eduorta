#!/usr/bin/env python3
"""
Тестирование умного генератора расписания
"""

from app import create_app, db
from app.models import Group
from app.services.smart_scheduler import SmartScheduleGenerator

def test_smart_generator():
    """Тестируем новый умный генератор"""
    app = create_app()
    
    with app.app_context():
        print("ТЕСТИРОВАНИЕ УМНОГО ГЕНЕРАТОРА РАСПИСАНИЯ")
        print("=" * 50)
        
        # Ищем группу для тестирования
        group = Group.query.filter(Group.name.like('%БНГС 1-25%')).first()
        
        if not group:
            print("Группа БНГС 1-25 не найдена")
            return
        
        print(f"Тестируем на группе: {group.name}")
        print(f"Смена: {group.shift} (пары: {group.shift_pairs})")
        print(f"Макс. пар подряд: {group.max_consecutive_pairs}")
        
        # Создаем умный генератор
        generator = SmartScheduleGenerator(
            group_id=group.id,
            semester=2,  # 2 семестр
            academic_year_id=1  # Текущий учебный год
        )
        
        print("\nЗАПУСК ГЕНЕРАЦИИ...")
        print("-" * 30)
        
        # Запускаем генерацию
        success = generator.generate()
        
        print("\nРЕЗУЛЬТАТЫ:")
        print("-" * 20)
        print(f"Успех: {success}")
        print(f"Качество: {generator.quality_score}/100")
        print(f"Создано пар: {len(generator.created_schedules)}")
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
        
        # Предлагаем сохранить
        if success and generator.created_schedules:
            save_choice = input(f"\nСохранить {len(generator.created_schedules)} новых пар? (y/N): ")
            if save_choice.lower() == 'y':
                if generator.save_results():
                    print("Результаты сохранены!")
                else:
                    print("Ошибка сохранения")
            else:
                print("Результаты не сохранены")
        
        print("\nТестирование завершено!")

if __name__ == "__main__":
    test_smart_generator()