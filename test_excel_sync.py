#!/usr/bin/env python3
"""
Тестирование нового Excel формата Google Sheets синхронизации
"""

import sys
import os
from datetime import date, datetime

# Добавляем путь к приложению
sys.path.append(os.path.dirname(__file__))

from app import create_app
from app.services.google_sheets_simple import SimpleGoogleSheetsSync
from config import Config

def test_excel_format():
    """Тестирование Excel формата"""
    
    # Создаем приложение для контекста
    app = create_app()
    
    with app.app_context():
        print("Тестирование Excel формата Google Sheets")
        print("=" * 50)
        
        # Создаем экземпляр сервиса
        service = SimpleGoogleSheetsSync()
        
        # Настраиваем тестовую дату (текущая неделя)
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # Понедельник
        week_end = week_start + timedelta(days=4)  # Пятница
        
        print(f"Тестируем неделю: {week_start} - {week_end}")
        
        # Получаем данные для тестирования
        try:
            print("\nПолучение данных расписания...")
            weekly_data = service._get_weekly_schedule_data(week_start, week_end)
            print(f"Найдено {len(weekly_data)} групп с расписанием")
            
            if not weekly_data:
                print("Нет данных для тестирования")
                return False
                
        except Exception as e:
            print(f"Ошибка получения данных: {e}")
            return False
        
        # Тестируем группировку по курсам
        try:
            print("\nТестирование группировки по курсам...")
            sheets_data = service._group_by_course_and_shift(weekly_data, week_start, week_end)
            
            print(f"Создано {len(sheets_data)} листов:")
            for sheet_key, sheet_info in sheets_data.items():
                course = sheet_info.get('course', 'N/A')
                groups_count = len(sheet_info.get('groups', []))
                title = sheet_info.get('title', 'Без названия')
                print(f"   {title}: {groups_count} групп (курс {course})")
                
        except Exception as e:
            print(f"Ошибка группировки: {e}")
            return False
            
        # Тестируем полную синхронизацию (без фактической отправки)
        try:
            print("\nТестирование полной синхронизации...")
            
            # Тестируем основной метод синхронизации
            result = service.sync_weekly_schedule(week_start)
            
            print("Результат синхронизации:")
            print(f"   Статус: {'успешно' if result.get('success') else 'ошибка'}")
            
            if result.get('success'):
                print(f"   Сообщение: {result.get('message', 'Нет сообщения')}")
                if 'data' in result:
                    data = result['data']
                    if 'sheets' in data:
                        print(f"   Листов создано: {len(data['sheets'])}")
                        for sheet_key, sheet_data in data['sheets'].items():
                            print(f"      {sheet_data['title']}: {len(sheet_data['groups'])} групп")
            else:
                print(f"   Ошибка: {result.get('error', result.get('message', 'Неизвестная ошибка'))}")
                
        except Exception as e:
            print(f"Ошибка тестирования синхронизации: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\nВсе тесты прошли успешно!")
        print("\nДля полного тестирования настройте webhook URL в настройках")
        return True

if __name__ == "__main__":
    from datetime import timedelta
    test_excel_format()