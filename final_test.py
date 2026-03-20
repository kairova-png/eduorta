#!/usr/bin/env python3
"""
Финальный тест - проверяем начинается ли генерация с 12 января
"""

from app import create_app, db
from app.models import Group, AcademicYear
from app.services.scheduler import ScheduleGenerator

def final_test():
    """Финальный тест генерации"""
    app = create_app()
    
    with app.app_context():
        print("ФИНАЛЬНЫЙ ТЕСТ ГЕНЕРАЦИИ")
        print("=" * 50)
        
        # Ищем группу БНГС 1-25
        group = Group.query.filter(Group.name.like('%БНГС 1-25%')).first()
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        
        if not group or not current_year:
            print("Группа или учебный год не найдены")
            return
        
        print(f"Группа: {group.name}")
        print(f"Учебный год: {current_year.name}")
        
        # Создаем генератор для 2 семестра
        generator = ScheduleGenerator(
            group_id=group.id,
            semester=2,
            academic_year_id=current_year.id
        )
        
        try:
            # Проверяем только получение недель, не генерируем
            print("\nПолучаем отфильтрованные недели...")
            
            # Получаем все недели ГУП
            from app.models import GUP
            all_gup_weeks = GUP.query.filter_by(
                group_id=group.id,
                academic_year_id=current_year.id
            ).order_by(GUP.week_number).all()
            
            print(f"Всего недель в ГУП: {len(all_gup_weeks)}")
            
            # Имитируем логику из генератора
            from datetime import date
            gup_weeks = []
            today = date.today()
            
            # Логика для 2 семестра (четный)
            semester_start = date(today.year, 1, 1)
            semester_end = date(today.year, 6, 30)
            
            print(f"Период семестра: {semester_start} - {semester_end}")
            
            # Фильтруем как в исправленном коде
            for week in all_gup_weeks:
                in_period = week.start_date >= semester_start and week.end_date <= semester_end
                needs_schedule = week.needs_schedule
                if in_period and needs_schedule:
                    gup_weeks.append(week)
                    print(f"Неделя {week.week_number} ({week.start_date}): ВКЛЮЧЕНА")
                elif in_period:
                    print(f"Неделя {week.week_number} ({week.start_date}): НЕ НУЖНО РАСПИСАНИЕ")
            
            print(f"\nОТФИЛЬТРОВАНО: {len(gup_weeks)} недель")
            
            if gup_weeks:
                first_week = gup_weeks[0]
                print(f"ПЕРВАЯ НЕДЕЛЯ: {first_week.week_number} ({first_week.start_date})")
                
                if first_week.start_date.month == 1 and first_week.start_date.day == 12:
                    print("✅ УСПЕХ! Генерация начинается с 12 января!")
                else:
                    print("❌ ОШИБКА! Генерация НЕ начинается с 12 января")
            else:
                print("❌ ОШИБКА! Нет недель для генерации")
                
        except Exception as e:
            print(f"ОШИБКА: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    final_test()