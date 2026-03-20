# GUP Data Export Documentation

## Обзор / Overview

Этот документ описывает структуру JSON файла с полным экспортом данных ГУП (График Учебного Процесса) для всех групп колледжа.

This document describes the structure of the JSON file containing the complete export of GUP (Educational Process Graph) data for all college groups.

**Файл экспорта:** `gup_export_complete.json`  
**Дата создания:** 2026-01-07  
**Версия:** 1.0

---

## Структура JSON / JSON Structure

### 1. Metadata (Метаданные)
```json
{
  "metadata": {
    "export_date": "2026-01-07T01:24:36.627949",
    "export_version": "1.0",
    "description": "Complete GUP data export for all groups",
    "total_academic_years": 2,
    "total_groups": 78,
    "total_gup_entries": 2964
  }
}
```

**Описание полей:**
- `export_date` - дата и время создания экспорта
- `export_version` - версия формата экспорта
- `total_academic_years` - количество учебных годов в системе
- `total_groups` - общее количество групп
- `total_gup_entries` - общее количество записей ГУП

---

### 2. Legends (Легенды и справочники)

#### 2.1 Activity Codes (Коды деятельности)
```json
{
  "legends": {
    "activity_codes": {
      "": {"name": "Учебная практика", "needs_schedule": true},
      "К": {"name": "Каникулы", "needs_schedule": false},
      "П": {"name": "Производственная практика", "needs_schedule": false},
      "ПА": {"name": "Промежуточная аттестация", "needs_schedule": false},
      "Э": {"name": "Экзамены", "needs_schedule": false}
    }
  }
}
```

**Коды деятельности:**
- `""` (пустой) / `null` / `"None"` - **Учебная практика** - обычные учебные недели, требуют расписания
- `"УП"` - **Учебная практика** - требует расписания
- `"К"` - **Каникулы** - не требует расписания
- `"П"` / `"ПП"` - **Производственная практика** - не требует расписания
- `"ПА"` - **Промежуточная аттестация** (сессия) - не требует расписания
- `"ИА"` - **Итоговая аттестация** - не требует расписания
- `"Э"` - **Экзамены** - не требует расписания
- `"З"` - **Зачеты** - не требует расписания
- `"ДП"` - **Дипломное проектирование** - не требует расписания
- `"::"` - **Перерыв** - не требует расписания
- `"ОТ"` - **Отработка** - требует расписания
- `"ӨО"` - **Өткізу** (отработка на казахском) - требует расписания

#### 2.2 Shift Types (Типы смен)
```json
{
  "shift_types": {
    "1": {"name": "1 смена (утро)", "pairs": [1,2,3,4], "time_range": "8:30 - 14:50"},
    "2": {"name": "2 смена (день)", "pairs": [5,6,7], "time_range": "15:00 - 19:20"},
    "3": {"name": "Смешанная", "pairs": [1,2,3,4,5,6,7], "time_range": "8:30 - 19:20"}
  }
}
```

#### 2.3 Pair Times (Время пар)
```json
{
  "pair_times": {
    "1": {"start": "08:30", "end": "10:00"},
    "2": {"start": "10:10", "end": "11:40"},
    "3": {"start": "12:30", "end": "14:00"},
    "4": {"start": "14:10", "end": "15:40"},
    "5": {"start": "15:50", "end": "17:20"},
    "6": {"start": "17:30", "end": "19:00"},
    "7": {"start": "19:10", "end": "20:40"}
  }
}
```

---

### 3. Academic Years (Учебные годы)
```json
{
  "academic_years": {
    "1": {
      "id": 1,
      "name": "2024-2025",
      "start_date": "2024-09-02",
      "end_date": "2025-06-30",
      "is_current": false
    }
  }
}
```

---

### 4. Departments (Кафедры/Отделения)
```json
{
  "departments": {
    "1": {
      "id": 1,
      "code": "ИТ",
      "name_ru": "Информационные технологии",
      "name_kz": "Ақпараттық технологиялар"
    }
  }
}
```

---

### 5. Specialties (Специальности)
```json
{
  "specialties": {
    "1": {
      "id": 1,
      "code": "ПО",
      "name_ru": "Программное обеспечение",
      "name_kz": "Бағдарламалық қамтамасыз ету",
      "department_id": 1
    }
  }
}
```

---

### 6. Groups (Группы)
```json
{
  "groups": {
    "1": {
      "id": 1,
      "name": "ПО 1-23",
      "specialty_id": 1,
      "specialty_code": "ПО",
      "specialty_name": "Программное обеспечение",
      "department_id": 1,
      "department_name": "Информационные технологии",
      "group_number": 1,
      "enrollment_year": 2023,
      "current_course": 3,
      "shift": 1,
      "shift_name": "1 смена (утро)",
      "shift_pairs": [1, 2, 3, 4],
      "max_consecutive_pairs": 2,
      "constraints": {
        "valid_pairs": [1, 2, 3, 4],
        "max_consecutive": 2,
        "shift_restrictions": {
          "morning_only": true,
          "afternoon_only": false,
          "mixed_schedule": false
        }
      }
    }
  }
}
```

**Важные поля для генератора расписания:**
- `shift_pairs` - допустимые номера пар для группы
- `max_consecutive_pairs` - максимальное количество пар подряд
- `constraints.shift_restrictions` - ограничения по сменам

---

### 7. GUP Data (Данные ГУП)

Основная структура данных ГУП организована по принципу:
`academic_year_id -> group_id -> weeks`

```json
{
  "gup_data": {
    "2": {
      "1": {
        "group_info": {
          "id": 1,
          "name": "ПО 1-23",
          "specialty_code": "ПО",
          "course": 3
        },
        "academic_year": {
          "id": 2,
          "name": "2025-2026"
        },
        "weeks": {
          "1": {
            "week_number": 1,
            "start_date": "2025-09-01",
            "end_date": "2025-09-07",
            "activity_code": "",
            "activity_name": null,
            "legend": {
              "name": "Учебная практика",
              "name_en": "Educational Practice",
              "description": "Обычные учебные недели",
              "needs_schedule": true
            },
            "constraints": {
              "needs_schedule_generation": true,
              "allows_classes": true,
              "scheduling_restrictions": {
                "normal_classes": true,
                "exams": false,
                "practice": false,
                "holidays": false,
                "makeup_classes": false
              }
            }
          }
        }
      }
    }
  }
}
```

**Ключевые поля для генератора расписания:**
- `constraints.needs_schedule_generation` - требуется ли генерация расписания
- `constraints.allows_classes` - можно ли проводить занятия
- `constraints.scheduling_restrictions` - конкретные ограничения по типу занятий

---

### 8. Statistics (Статистика)
```json
{
  "statistics": {
    "overall": {
      "total_groups": 78,
      "total_weeks_scheduled": 2964,
      "groups_by_shift": {
        "morning": 45,
        "afternoon": 20,
        "mixed": 13
      }
    },
    "by_academic_year": {
      "2": {
        "name": "2025-2026",
        "total_entries": 1482,
        "groups_count": 39,
        "weeks_range": {"min": 1, "max": 38}
      }
    }
  }
}
```

---

## Использование данных в генераторе расписания

### Алгоритм определения возможности создания расписания:

1. **Проверка недели:**
   ```python
   week_data = gup_data[academic_year][group_id]["weeks"][week_number]
   if week_data["constraints"]["needs_schedule_generation"]:
       # Создавать расписание для этой недели
   ```

2. **Проверка ограничений группы:**
   ```python
   group_data = groups[group_id]
   valid_pairs = group_data["shift_pairs"]  # [1,2,3,4] или [5,6,7] или [1,2,3,4,5,6,7]
   max_consecutive = group_data["max_consecutive_pairs"]  # обычно 2
   ```

3. **Применение ограничений:**
   ```python
   # Группа может заниматься только в определенные пары
   if pair_number not in group_data["shift_pairs"]:
       continue  # Пропустить эту пару
   
   # Не более N пар подряд
   if consecutive_pairs_count >= max_consecutive:
       break  # Прекратить назначение пар подряд
   ```

### Практические примеры:

**Пример 1: Обычная учебная неделя**
- `activity_code`: `""` (пустой)
- `needs_schedule_generation`: `true`
- **Действие:** Генерировать полное расписание

**Пример 2: Каникулы**
- `activity_code`: `"К"`
- `needs_schedule_generation`: `false`
- **Действие:** Не генерировать расписание

**Пример 3: Экзаменационная сессия**
- `activity_code`: `"Э"`
- `needs_schedule_generation`: `false`
- **Действие:** Не генерировать обычное расписание (возможно, специальное расписание экзаменов)

---

## Технические детали

### Формат дат:
- Все даты в формате ISO 8601: `"YYYY-MM-DD"`
- Время экспорта в формате: `"YYYY-MM-DDTHH:MM:SS.ffffff"`

### Кодировка:
- Файл сохранен в UTF-8 с поддержкой кириллицы и казахских символов
- `ensure_ascii=False` при генерации JSON

### Структура ключей:
- Все ID сохранены как строки для совместимости
- Номера недель: 1-52 (соответствуют календарным неделям)
- Номера пар: 1-7 (соответствуют академическим парам)

---

## Примеры использования

### Получить все группы утренней смены:
```python
morning_groups = [
    group_id for group_id, group_data in data["groups"].items()
    if group_data["shift"] == 1
]
```

### Найти недели с каникулами:
```python
holiday_weeks = []
for year_id, year_data in data["gup_data"].items():
    for group_id, group_data in year_data.items():
        for week_num, week_data in group_data["weeks"].items():
            if week_data["activity_code"] == "К":
                holiday_weeks.append({
                    "year": year_id,
                    "group": group_id,
                    "week": week_num,
                    "dates": f"{week_data['start_date']} - {week_data['end_date']}"
                })
```

### Проверить возможность расписания для группы и недели:
```python
def can_schedule_classes(academic_year_id, group_id, week_number):
    try:
        week_data = data["gup_data"][str(academic_year_id)][str(group_id)]["weeks"][str(week_number)]
        return week_data["constraints"]["needs_schedule_generation"]
    except KeyError:
        return False
```

---

## Контакт и поддержка

Для вопросов по структуре данных или использованию в генераторе расписания обращайтесь к разработчикам системы.

**Последнее обновление:** 2026-01-07