#!/usr/bin/env python3
"""
Проверяем ГУП недели 20-26 для группы БНГС 1-25
"""

from app import create_app, db
from app.models import Group, GUP

def check_weeks_20_26():
    """Проверяем недели 20-26"""
    app = create_app()
    
    with app.app_context():
        print("ПРОВЕРКА ГУП НЕДЕЛЬ 20-26")
        print("=" * 50)
        
        # Ищем группу БНГС 1-25
        group = Group.query.filter(Group.name.like('%БНГС 1-25%')).first()
        if not group:
            print("Группа не найдена")
            return
        
        print(f"Группа: {group.name} (ID: {group.id})")
        
        # Проверяем недели 20-26
        for week_num in range(20, 27):
            gup_week = GUP.query.filter_by(
                group_id=group.id,
                week_number=week_num,
                academic_year_id=1
            ).first()
            
            if gup_week:
                print(f"Неделя {week_num} ({gup_week.start_date} - {gup_week.end_date}):")
                print(f"  activity_code: '{gup_week.activity_code}'")
                print(f"  needs_schedule: {gup_week.needs_schedule}")
                print(f"  Логика: activity_code in ['', None, 'УП', 'ОТ', 'ӨО'] = {gup_week.activity_code in ['', None, 'УП', 'ОТ', 'ӨО']}")
            else:
                print(f"Неделя {week_num}: НЕ НАЙДЕНА В ГУП!")
        
        print("\n" + "=" * 50)
        print("ПРОВЕРКА НЕДЕЛЬ 27-30 ДЛЯ СРАВНЕНИЯ:")
        for week_num in range(27, 31):
            gup_week = GUP.query.filter_by(
                group_id=group.id,
                week_number=week_num,
                academic_year_id=1
            ).first()
            
            if gup_week:
                print(f"Неделя {week_num}: activity_code='{gup_week.activity_code}', needs_schedule={gup_week.needs_schedule}")

if __name__ == "__main__":
    check_weeks_20_26()