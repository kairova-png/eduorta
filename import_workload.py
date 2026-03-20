#!/usr/bin/env python3
"""
Скрипт импорта нагрузки из Excel файла ALL_workload_detailed.xlsx
"""

import pandas as pd
import re
import sys
sys.path.insert(0, '.')

from app import create_app, db
from app.models import Teacher, Group, Workload, AcademicYear

# Маппинг ошибочных имён преподавателей на правильные
TEACHER_NAME_MAPPING = {
    'Айбарұлы Ғ.': 'Айбарұлы Г.',
    'Багитова А.': 'Багытова А.',
    'Галымжанов А.': 'Ғалымжанов А.',  # новый преподаватель
    'Елеусінов Е.': 'Елеусинов Е.',
    'Кадргалиева А..': 'Кадргалиева А.',
    'Кайыров А..': 'Кайыров А.',
    'Нурланұлы С.': 'Нұрланұлы С.',
    'Отеуов Д.': 'Өтеуов Д.',
    'Сагындыккызы Д.': 'Сагындыкова Д.',
    'Султангалиева А..': 'Султангалиева А.',
    'Сырымбетулы Ш.': 'Сырымбетұлы Ш.',
    'Утеш М .': 'Утеш М.',
    'Өтеуов Д': 'Өтеуов Д.',
}

# Новые преподаватели, которых нужно добавить
NEW_TEACHERS = [
    'Ғалымжанов А.',
    'Кайыргалиева Ф.',
    'Сейтхазиев Е.',
]

# Паттерн для нормальной группы
GROUP_PATTERN = re.compile(r'^([А-Яа-яӘәІіҢңҒғҮүҰұҚқӨөҺһA-Za-z]+)\s+(\d+)-(\d{2})$')

# Паттерн для извлечения группы из комментария
GROUP_IN_COMMENT_PATTERN = re.compile(r'([А-Яа-яӘәІіҢңҒғҮүҰұҚқӨөҺһA-Za-z]+\s+\d+-\d{2})')


def normalize_teacher_name(name):
    """Нормализует имя преподавателя"""
    if pd.isna(name):
        return None
    name = str(name).strip()
    return TEACHER_NAME_MAPPING.get(name, name)


def extract_group_name(value):
    """Извлекает название группы из значения (может быть комментарием)"""
    if pd.isna(value):
        return None
    value = str(value).strip()

    # Проверяем, нормальная ли это группа
    if GROUP_PATTERN.match(value):
        return value

    # Пытаемся извлечь группу из комментария
    match = GROUP_IN_COMMENT_PATTERN.search(value)
    if match:
        return match.group(1)

    return None


def get_semester_for_group(group_name, current_year=2025):
    """Определяет семестр по группе (осенний семестр)"""
    match = GROUP_PATTERN.match(group_name)
    if not match:
        return 1

    enrollment_year = int('20' + match.group(3))
    course = current_year - enrollment_year + 1

    # Осенний семестр: 1 курс -> 1, 2 курс -> 3, 3 курс -> 5, 4 курс -> 7
    semester = (course - 1) * 2 + 1
    return min(semester, 7)  # Максимум 7 семестр


def import_workload(excel_path, dry_run=True):
    """
    Импортирует нагрузку из Excel

    Args:
        excel_path: путь к Excel файлу
        dry_run: если True, только показывает что будет сделано, не сохраняет
    """
    app = create_app()

    with app.app_context():
        # Получаем текущий учебный год
        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not academic_year:
            print("ОШИБКА: Нет текущего учебного года!")
            return

        print(f"Учебный год: {academic_year.name}")
        print(f"Режим: {'DRY RUN (без сохранения)' if dry_run else 'РЕАЛЬНЫЙ ИМПОРТ'}")
        print()

        # Загружаем существующие данные
        teachers_db = {t.full_name: t for t in Teacher.query.all()}
        groups_db = {g.name: g for g in Group.query.all()}

        # Добавляем новых преподавателей
        if not dry_run:
            for name in NEW_TEACHERS:
                if name not in teachers_db:
                    teacher = Teacher(full_name=name)
                    db.session.add(teacher)
                    print(f"+ Добавлен преподаватель: {name}")
            db.session.commit()
            # Перезагружаем
            teachers_db = {t.full_name: t for t in Teacher.query.all()}

        # Читаем Excel
        df = pd.read_excel(excel_path, sheet_name='По дисциплинам')
        print(f"Загружено строк: {len(df)}")
        print()

        # Статистика
        stats = {
            'total': 0,
            'imported': 0,
            'skipped_no_group': 0,
            'skipped_no_teacher': 0,
            'skipped_group_not_found': 0,
            'errors': []
        }

        workloads_to_add = []

        for idx, row in df.iterrows():
            stats['total'] += 1

            # Извлекаем данные
            teacher_name_raw = row.get('Преподаватель')
            group_raw = row.get('Группа')
            discipline = row.get('Дисциплина')
            total_hours = row.get('План (всего)')
            hours_completed = row.get('Итого факт')

            # Нормализуем имя преподавателя
            teacher_name = normalize_teacher_name(teacher_name_raw)
            if not teacher_name:
                stats['skipped_no_teacher'] += 1
                continue

            # Извлекаем группу
            group_name = extract_group_name(group_raw)
            if not group_name:
                stats['skipped_no_group'] += 1
                stats['errors'].append(f"Строка {idx+2}: не удалось извлечь группу из '{group_raw}'")
                continue

            # Проверяем преподавателя
            teacher = teachers_db.get(teacher_name)
            if not teacher:
                stats['skipped_no_teacher'] += 1
                stats['errors'].append(f"Строка {idx+2}: преподаватель '{teacher_name}' не найден в БД")
                continue

            # Проверяем группу
            group = groups_db.get(group_name)
            if not group:
                stats['skipped_group_not_found'] += 1
                stats['errors'].append(f"Строка {idx+2}: группа '{group_name}' не найдена в БД")
                continue

            # Определяем семестр
            semester = get_semester_for_group(group_name)

            # Конвертируем часы
            try:
                total_hours = int(total_hours) if pd.notna(total_hours) else 0
                hours_completed = int(hours_completed) if pd.notna(hours_completed) else 0
            except (ValueError, TypeError):
                total_hours = 0
                hours_completed = 0

            # Определяем тип занятия
            lesson_type = 'practice' if 'практик' in str(discipline).lower() or 'ПО 0' in str(discipline) else 'theory'

            workload_data = {
                'teacher_id': teacher.id,
                'group_id': group.id,
                'academic_year_id': academic_year.id,
                'discipline': str(discipline)[:500] if discipline else 'Без названия',
                'lesson_type': lesson_type,
                'semester': semester,
                'total_hours': total_hours,
                'hours_completed': hours_completed,
            }

            workloads_to_add.append(workload_data)
            stats['imported'] += 1

        # Выводим статистику
        print("=" * 60)
        print("СТАТИСТИКА")
        print("=" * 60)
        print(f"Всего строк в Excel: {stats['total']}")
        print(f"Готово к импорту: {stats['imported']}")
        print(f"Пропущено (нет группы): {stats['skipped_no_group']}")
        print(f"Пропущено (нет преподавателя): {stats['skipped_no_teacher']}")
        print(f"Пропущено (группа не в БД): {stats['skipped_group_not_found']}")
        print()

        if stats['errors'][:10]:
            print("Первые 10 ошибок:")
            for err in stats['errors'][:10]:
                print(f"  - {err}")
            print()

        # Сохраняем
        if not dry_run and workloads_to_add:
            print(f"Сохранение {len(workloads_to_add)} записей...")

            # Удаляем старые записи нагрузки для этого года (опционально)
            # Workload.query.filter_by(academic_year_id=academic_year.id).delete()

            for data in workloads_to_add:
                workload = Workload(**data)
                db.session.add(workload)

            db.session.commit()
            print("Импорт завершён!")
        elif dry_run:
            print("DRY RUN: данные НЕ сохранены. Запустите с dry_run=False для реального импорта.")

        # Показываем примеры
        print()
        print("Примеры записей (первые 5):")
        for i, data in enumerate(workloads_to_add[:5]):
            teacher = teachers_db.get(next((k for k, v in teachers_db.items() if v.id == data['teacher_id']), None))
            group = groups_db.get(next((k for k, v in groups_db.items() if v.id == data['group_id']), None))
            print(f"  {i+1}. {teacher.full_name if teacher else '?'} | {group.name if group else '?'} | "
                  f"Сем {data['semester']} | {data['total_hours']}ч | {data['discipline'][:40]}...")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Импорт нагрузки из Excel')
    parser.add_argument('--run', action='store_true', help='Выполнить реальный импорт (без этого флага - только проверка)')
    args = parser.parse_args()

    excel_path = '../ALL_workload_detailed.xlsx'
    import_workload(excel_path, dry_run=not args.run)
