# Google Sheets Integration

Интеграция системы расписания APEC Petrotechnic с Google Таблицами для публичного отображения данных.

## Обзор

Система автоматически отправляет данные расписания в Google Таблицы через webhook при:
- Генерации расписания для группы
- Массовой генерации расписания
- Изменении существующих записей (опционально)

## Архитектура

```
Flask App → Google Apps Script (webhook) → Google Sheets
```

### Компоненты

1. **Flask Webhook Service** (`app/services/google_sheets_webhook.py`)
   - Формирование JSON данных
   - Отправка POST запросов в Google Apps Script
   - Обработка ошибок и логирование

2. **Google Apps Script** (`google_apps_script/webhook_receiver.gs`)
   - Прием webhook запросов от Flask
   - Обработка и форматирование данных
   - Запись в Google Sheets с применением стилей

3. **Google Sheets**
   - Публичное отображение расписания
   - Автоматическое форматирование и сортировка
   - Условное форматирование статусов

## Настройка

### 1. Google Apps Script

1. Перейдите на [script.google.com](https://script.google.com)
2. Создайте новый проект "Schedule Webhook Receiver"
3. Скопируйте код из `google_apps_script/webhook_receiver.gs`
4. В константе `CONFIG.SPREADSHEET_ID` укажите ID вашей Google Таблицы
5. Сохраните проект и разверните как веб-приложение:
   - Нажмите "Deploy" → "New deployment"
   - Type: "Web app" 
   - Execute as: "Me"
   - Who has access: "Anyone"
   - Нажмите "Deploy"
6. Скопируйте URL веб-приложения

### 2. Google Sheets

1. Создайте новую Google Таблицу
2. Скопируйте ID таблицы из URL (между `/d/` и `/edit`)
3. Настройте публичный доступ:
   - File → Share → "Anyone with the link can view"
4. Листы будут созданы автоматически при первой синхронизации

### 3. Flask Configuration

Установите переменную окружения:
```bash
export GOOGLE_SHEETS_WEBHOOK_URL="https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"
export GOOGLE_SHEETS_AUTO_UPDATE="true"
```

Или добавьте в `config.py`:
```python
GOOGLE_SHEETS_WEBHOOK_URL = 'https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec'
GOOGLE_SHEETS_AUTO_UPDATE = True
```

## Структура данных

### Webhook Payload

```json
{
  "action": "update_schedule",
  "update_type": "single_group|full|partial",
  "metadata": {
    "update_type": "single_group",
    "record_count": 45,
    "timestamp": "2025-12-14T12:00:00",
    "academic_year": "2025-2026",
    "group": {
      "id": 1,
      "name": "ПО 1-23",
      "specialty": "Программное обеспечение"
    }
  },
  "schedule_data": [
    {
      "id": 123,
      "date": "2025-12-15",
      "day_of_week": "Понедельник",
      "pair_number": 1,
      "pair_time": "08:30-10:00",
      "group_name": "ПО 1-23",
      "group_id": 1,
      "discipline": "Основы программирования",
      "lesson_type": "theory",
      "teacher_name": "Иванов И.И.",
      "teacher_id": 5,
      "room_name": "Каб. 301",
      "room_id": 15,
      "status": "planned",
      "status_display": "Запланировано",
      "semester": 1,
      "academic_year": "2025-2026",
      "substitute_teacher": null,
      "change_reason": null,
      "notes": null
    }
  ],
  "timestamp": "2025-12-14T12:00:00"
}
```

### Google Sheets Structure

Создается лист "Расписание" с колонками:
- ID, Дата, День недели, № пары, Время, Группа, Дисциплина
- Тип занятия, Преподаватель, Аудитория, Статус, Семестр
- Учебный год, Примечания, Последнее обновление

## Использование

### Автоматическая синхронизация

При включенной автоматической синхронизации данные отправляются:
- После генерации расписания группы
- После массовой генерации расписания
- При изменении записей расписания (если включено)

### Ручная синхронизация

Через веб-интерфейс `/google-sheets`:
- Полная синхронизация всех данных
- Синхронизация отдельных групп
- Тест подключения

### Программный доступ

```python
from app.services.google_sheets_webhook import send_group_schedule_to_sheets

# Отправка расписания группы
result = send_group_schedule_to_sheets(group_id=1)
if result['success']:
    print(f"Отправлено {result['records_sent']} записей")

# Полная синхронизация
from app.services.google_sheets_webhook import send_full_schedule_to_sheets
result = send_full_schedule_to_sheets()
```

## Форматирование Google Sheets

### Условное форматирование статусов

- **Проведено**: Зеленый фон (#D4EDDA)
- **Отменено**: Красный фон (#F8D7DA)  
- **Замена**: Желтый фон (#FFF3CD)
- **Перенесено**: Синий фон (#D1ECF1)

### Автоматические функции

- Сортировка по дате и номеру пары
- Автоширина колонок
- Заморозка заголовков
- Группировка по дням/неделям (опционально)

## Мониторинг и отладка

### Логирование Flask

```python
print(f"DEBUG: Данные отправлены в Google Sheets. Записей: {records_sent}")
print(f"WARNING: Ошибка отправки в Google Sheets: {error}")
```

### Логирование Google Apps Script

Создается лист "Журнал обновлений" с информацией о:
- Времени получения webhook'ов
- Количестве обработанных записей  
- Статусе операций
- Ошибках обработки

### Проверка статуса

```bash
# API endpoint для проверки статуса
curl http://localhost:5000/google-sheets/api/webhook-status
```

## Безопасность

### Google Apps Script
- Webhook доступен только через HTTPS
- Валидация входящих данных
- Ограничение размера payload'а

### Flask Application  
- Таймаут запросов (30 сек по умолчанию)
- Обработка ошибок сети
- Логирование попыток отправки

## Ограничения

### Google Apps Script
- Максимум 6 минут выполнения
- 20,000 триггеров в день
- 100MB максимальный размер ответа

### Google Sheets
- 10 миллионов ячеек на таблицу
- 256 колонок на лист
- 40,000 новых строк в день

## Troubleshooting

### Частые ошибки

1. **Webhook URL не настроен**
   - Проверьте переменную `GOOGLE_SHEETS_WEBHOOK_URL`

2. **Ошибка 403 в Google Apps Script**
   - Проверьте права доступа к таблице
   - Переразверните веб-приложение

3. **Таймаут запроса**
   - Уменьшите размер отправляемых данных
   - Проверьте производительность Google Apps Script

4. **Данные не появляются в таблице**
   - Проверьте ID таблицы в Google Apps Script
   - Убедитесь что листы создаются правильно

### Отладка

Включите детальное логирование:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Проверьте webhook в Google Apps Script:
```javascript
console.log('Received data:', JSON.stringify(data));
```

## Расширение функциональности

### Дополнительные типы событий

Можно добавить webhook'и для:
- Изменения статуса занятий
- Добавления замен
- Обновления информации о группах/преподавателях

### Кастомизация форматирования

В Google Apps Script можно настроить:
- Цветовые схемы
- Дополнительные листы (по группам, преподавателям)
- Автоматические сводные таблицы
- Графики и диаграммы

## Поддержка

При возникновении проблем проверьте:
1. Логи Flask приложения
2. Журнал выполнения Google Apps Script
3. Лист "Журнал обновлений" в Google Sheets
4. Статус webhook'а через API