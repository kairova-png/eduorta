#!/usr/bin/env python3
"""
Тест отладки генератора для понимания фильтрации недель
"""

from app import create_app, db
from app.models import Group, AcademicYear
from app.services.scheduler import ScheduleGenerator

def test_debug_weeks():
    """Тестируем какие недели фильтруются"""
    app = create_app()
    
    with app.app_context():
        print("ОТЛАДКА ФИЛЬТРАЦИИ НЕДЕЛЬ")
        print("=" * 50)
        
        # Ищем группу БНГС 1-25
        group = Group.query.filter(Group.name.like('%БНГС 1-25%')).first()
        
        if not group:
            print("Группа БНГС 1-25 не найдена")
            return
        
        print(f"Найдена группа: {group.name} (ID: {group.id})")
        
        # Получаем текущий учебный год
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            print("Ошибка: Не установлен текущий учебный год")
            return
        
        print(f"Текущий учебный год: {current_year.name} (ID: {current_year.id})")
        
        # Создаем генератор для 2 семестра
        generator = ScheduleGenerator(
            group_id=group.id,
            semester=2,
            academic_year_id=current_year.id
        )
        
        # Вызываем основной метод генерации для просмотра отладки
        print("\nВЫЗЫВАЕМ generate()...")
        print("-" * 50)
        
        try:
            result = generator.generate()
            print(f"\nВОЗВРАЩЕН РЕЗУЛЬТАТ: {result}")
            print(f"Создано пар: {generator.created_count}")
            print(f"Ошибки: {generator.errors}")
            print(f"Предупреждения: {generator.warnings}")
        except Exception as e:
            print(f"ОШИБКА: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_debug_weeks()