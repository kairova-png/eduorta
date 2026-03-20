#!/usr/bin/env python3
"""
Отладка payload для Google Sheets
"""

import sys
import os
import json
from datetime import date, datetime, timedelta

# Добавляем путь к приложению
sys.path.append(os.path.dirname(__file__))

from app import create_app
from app.services.google_sheets_simple import SimpleGoogleSheetsSync
from config import Config

def debug_payload():
    """Показываем точный payload который отправляется в Google Apps Script"""
    
    # Создаем приложение для контекста
    app = create_app()
    
    with app.app_context():
        print("Отладка payload для Google Apps Script")
        print("=" * 50)
        
        # Создаем экземпляр сервиса
        service = SimpleGoogleSheetsSync()
        
        # Настраиваем тестовую дату (текущая неделя)
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # Понедельник
        week_end = week_start + timedelta(days=4)  # Пятница
        
        print(f"Создаем payload для недели: {week_start} - {week_end}")
        
        try:
            # Получаем данные расписания
            weekly_data = service._get_weekly_schedule_data(week_start, week_end)
            print(f"Найдено {len(weekly_data)} групп")
            
            if not weekly_data:
                print("Нет данных для создания payload")
                return
                
            # Группируем по курсам
            sheets_data = service._group_by_course_and_shift(weekly_data, week_start, week_end)
            print(f"Создано {len(sheets_data)} листов")
            
            # Создаем payload как в оригинальном коде
            payload = {
                'action': 'sync_excel_format',
                'week_start': week_start.isoformat(),
                'week_end': week_end.isoformat(),
                'sheets': sheets_data,
                'timestamp': datetime.now().isoformat()
            }
            
            print("\n" + "=" * 50)
            print("PAYLOAD ДЛЯ GOOGLE APPS SCRIPT:")
            print("=" * 50)
            
            # Красиво выводим структуру payload
            print(json.dumps(payload, ensure_ascii=True, indent=2))
            
            print("\n" + "=" * 50)
            print("КРАТКАЯ СТРУКТУРА:")
            print("=" * 50)
            
            print(f"Action: {payload.get('action')}")
            print(f"Week: {payload.get('week_start')} - {payload.get('week_end')}")
            
            if 'sheets' in payload:
                print(f"Sheets count: {len(payload['sheets'])}")
                for sheet_key, sheet_data in payload['sheets'].items():
                    print(f"  {sheet_key}:")
                    print(f"    title: {sheet_data.get('title', 'MISSING!')}")
                    print(f"    course: {sheet_data.get('course', 'MISSING!')}")
                    print(f"    groups: {len(sheet_data.get('groups', []))}")
                    print(f"    table_structure: {bool(sheet_data.get('table_structure'))}")
                    
        except Exception as e:
            print(f"Ошибка создания payload: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_payload()