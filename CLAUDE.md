# Правила работы с Flask сервером

## 🚨 ВАЖНО: Управление процессами сервера

### Рекомендуемый способ - Server Manager
```bash
# Запустить менеджер сервера
server_manager.bat

# Или напрямую:
# [1] Запуск разработки
# [2] Запуск продакшен  
# [3] Остановка всех серверов
# [4] Проверка статуса
```

### Ручное управление процессами
```bash
# Проверить активные Flask процессы
wmic process where "name='python.exe' and CommandLine like '%run.py%'" get ProcessId,CommandLine

# Убить ВСЕ Flask серверы перед запуском нового
wmic process where "name='python.exe' and CommandLine like '%run.py%'" delete

# Проверить что порт свободен
netstat -an | findstr :5000
```

## Команды запуска сервера

### Режим DEBUG (рекомендуется для разработки)
```bash
cd "C:\Users\tkulz\Downloads\college_schedule_backup_20251212\college_schedule"
set FLASK_DEBUG=1
python run.py
```

### Альтернативный DEBUG режим  
```bash
cd "C:\Users\tkulz\Downloads\college_schedule_backup_20251212\college_schedule"
set FLASK_ENV=development
python run.py
```

### Обычный режим
```bash
cd "C:\Users\tkulz\Downloads\college_schedule_backup_20251212\college_schedule"  
python run.py
```

## Проверка работы
- Сервер запущен: http://127.0.0.1:5000
- Генерация расписания: http://127.0.0.1:5000/schedule/generate

## Отладка проблем с кодировкой
- Все DEBUG выводы должны быть на английском языке
- Избегать вывода русских/казахских символов в print()
- При ошибках кодировки заменить проблемные строки на комментарии