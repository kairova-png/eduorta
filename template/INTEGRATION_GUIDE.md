# 📋 Интеграция редактора шаблонов нагрузки в Flask-систему

## 🎯 Задача
Интегрировать HTML-редактор распределения учебной нагрузки в существующую Flask-систему колледжа.

---

## 📁 Прилагаемые файлы
1. `workload_template_gup_v2.html` — редактор (чистый HTML/CSS/JS, без зависимостей)
2. `gup_2025_2026.json` — пример структуры ГУП

---

## 🏗️ Информация о системе

### Стек:
- **Backend:** Flask (Python)
- **Database:** SQLite
- **Templates:** Jinja2
- **CSS:** Bootstrap 5
- **Auth:** Есть система аутентификации

### Существующие модели:
```python
# Примерная структура (уточни по models.py)
class Group:
    id, name, course, specialty...

class Teacher:
    id, name, department...

class Room:
    id, number, building, capacity...

class Workload:
    id, teacher_id, group_id, subject, hours_total, semester...

class Schedule:
    id, date, pair_number, group_id, teacher_id, room_id, subject...

class GUP:
    id, group_id, week_number, activity_type, start_date, end_date...
```

### Существующие endpoints:
- `GET /groups/` — список групп
- `GET /gup/` — управление ГУП
- `GET /workload/` — управление нагрузкой
- `GET /schedule/generate` — страница генерации расписания

### Сервисы:
- `/app/services/scheduler.py` — генератор расписания
- `/app/services/smart_scheduler.py` — умный генератор

---

## 📊 Что делает редактор

### Функционал:
1. Загружает ГУП (JSON) и показывает недели по группе
2. При клике на учебную неделю — модальное окно с сеткой дней/пар
3. Можно отметить слоты как:
   - ✓ **selected** — занятие будет здесь
   - ⭐ **preferred** — желательное время
   - ✕ **avoid** — избегать это время
4. Превью расписания в виде таблицы (как в schedule)
5. Экспорт JSON с распределением

### Структура выходного JSON:
```json
{
  "meta": {
    "name": "Программирование",
    "group": "ВТиПО 2-23",
    "academicYear": "2025-2026",
    "createdAt": "2025-01-07T..."
  },
  "parameters": {
    "totalHours": 72,
    "semester": 1
  },
  "weeks": [
    {
      "week": 3,
      "hours": 6,
      "startDate": "2025-09-15",
      "endDate": "2025-09-21",
      "schedule": [
        {
          "day": "mon",
          "pairs": [
            {"pair": "I", "status": "selected"},
            {"pair": "II", "status": "preferred"}
          ]
        },
        {
          "day": "wed",
          "pairs": [
            {"pair": "III", "status": "selected"}
          ]
        }
      ]
    }
  ],
  "statistics": {
    "totalDistributed": 72,
    "weeksUsed": 12
  }
}
```

---

## 🔧 План интеграции

### 1. Создать новую модель WorkloadTemplate

```python
# app/models/workload_template.py

class WorkloadTemplate(db.Model):
    __tablename__ = 'workload_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    
    # Связи
    workload_id = db.Column(db.Integer, db.ForeignKey('workload.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    
    # Параметры
    semester = db.Column(db.Integer, nullable=False)  # 1 или 2
    total_hours = db.Column(db.Integer, nullable=False)
    
    # JSON с распределением по неделям
    distribution_json = db.Column(db.Text, nullable=False)  # JSON строка
    
    # Мета
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    workload = db.relationship('Workload', backref='templates')
    group = db.relationship('Group', backref='workload_templates')
```

### 2. Создать API endpoints

```python
# app/routes/workload_templates.py

from flask import Blueprint, jsonify, request
from app.models import WorkloadTemplate, Group, Workload, GUP

bp = Blueprint('workload_templates', __name__, url_prefix='/api/workload-templates')

@bp.route('/', methods=['GET'])
@login_required
def list_templates():
    """Список шаблонов"""
    templates = WorkloadTemplate.query.all()
    return jsonify([t.to_dict() for t in templates])

@bp.route('/', methods=['POST'])
@login_required
def create_template():
    """Создать шаблон из редактора"""
    data = request.json
    
    template = WorkloadTemplate(
        name=data['meta']['name'],
        group_id=data['meta']['group_id'],
        workload_id=data['meta']['workload_id'],
        semester=data['parameters']['semester'],
        total_hours=data['parameters']['totalHours'],
        distribution_json=json.dumps(data['weeks']),
        created_by=current_user.id
    )
    
    db.session.add(template)
    db.session.commit()
    
    return jsonify({'success': True, 'id': template.id})

@bp.route('/<int:id>', methods=['GET'])
@login_required
def get_template(id):
    """Получить шаблон для редактирования"""
    template = WorkloadTemplate.query.get_or_404(id)
    return jsonify(template.to_dict())

@bp.route('/<int:id>', methods=['PUT'])
@login_required
def update_template(id):
    """Обновить шаблон"""
    template = WorkloadTemplate.query.get_or_404(id)
    data = request.json
    
    template.name = data['meta']['name']
    template.distribution_json = json.dumps(data['weeks'])
    template.total_hours = data['parameters']['totalHours']
    
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/<int:id>', methods=['DELETE'])
@login_required
def delete_template(id):
    """Удалить шаблон"""
    template = WorkloadTemplate.query.get_or_404(id)
    db.session.delete(template)
    db.session.commit()
    return jsonify({'success': True})
```

### 3. API для данных редактора

```python
# app/routes/api.py (добавить)

@bp.route('/groups-with-gup', methods=['GET'])
@login_required
def groups_with_gup():
    """Группы с их ГУП для редактора"""
    groups = Group.query.all()
    result = []
    
    for g in groups:
        gup_data = GUP.query.filter_by(group_id=g.id).all()
        result.append({
            'id': g.id,
            'name': g.name,
            'course': g.course,
            'gup': {
                str(gup.week_number): {
                    'activity': gup.activity_type,
                    'start_date': gup.start_date.isoformat(),
                    'end_date': gup.end_date.isoformat()
                } for gup in gup_data
            }
        })
    
    return jsonify(result)

@bp.route('/workloads-by-group/<int:group_id>', methods=['GET'])
@login_required
def workloads_by_group(group_id):
    """Нагрузка (дисциплины) для группы"""
    workloads = Workload.query.filter_by(group_id=group_id).all()
    return jsonify([{
        'id': w.id,
        'subject': w.subject,
        'teacher_id': w.teacher_id,
        'teacher_name': w.teacher.name if w.teacher else None,
        'hours_total': w.hours_total,
        'semester': w.semester
    } for w in workloads])
```

### 4. Интеграция в scheduler

```python
# app/services/scheduler.py (модифицировать)

def generate_schedule_with_templates(group_id, semester):
    """Генерация с учётом шаблонов"""
    
    templates = WorkloadTemplate.query.filter_by(
        group_id=group_id, 
        semester=semester
    ).all()
    
    # Собираем constraints из шаблонов
    constraints = {
        'selected': [],   # Обязательные слоты
        'preferred': [],  # Желательные
        'avoid': []       # Избегать
    }
    
    for template in templates:
        weeks = json.loads(template.distribution_json)
        workload = template.workload
        
        for week_data in weeks:
            week_num = week_data['week']
            
            for day_data in week_data.get('schedule', []):
                day = day_data['day']
                
                for pair_data in day_data.get('pairs', []):
                    pair = pair_data['pair']
                    status = pair_data['status']
                    
                    slot = {
                        'week': week_num,
                        'day': day,
                        'pair': pair,
                        'workload_id': workload.id,
                        'subject': workload.subject,
                        'teacher_id': workload.teacher_id,
                        'group_id': group_id
                    }
                    
                    constraints[status].append(slot)
    
    # Передаём в основной алгоритм
    return generate_with_constraints(constraints)
```

### 5. Создать страницу редактора

```python
# app/routes/workload_templates.py (добавить view)

@bp.route('/editor')
@bp.route('/editor/<int:template_id>')
@login_required
def editor(template_id=None):
    """Страница редактора шаблонов"""
    template_data = None
    
    if template_id:
        template = WorkloadTemplate.query.get_or_404(template_id)
        template_data = template.to_dict()
    
    return render_template(
        'workload_templates/editor.html',
        template_data=template_data
    )
```

### 6. Jinja2 шаблон

```html
<!-- templates/workload_templates/editor.html -->
{% extends "base.html" %}

{% block title %}Редактор шаблонов нагрузки{% endblock %}

{% block styles %}
<style>
    /* Вставить CSS из workload_template_gup_v2.html */
    /* Адаптировать цвета под Bootstrap если нужно */
</style>
{% endblock %}

{% block content %}
<div class="container-fluid">
    <!-- HTML контент из workload_template_gup_v2.html -->
    <!-- Убрать модалку загрузки файла - данные будут из API -->
</div>
{% endblock %}

{% block scripts %}
<script>
    // Конфигурация API
    const API = {
        groups: '/api/groups-with-gup',
        workloads: '/api/workloads-by-group/',
        templates: '/api/workload-templates/'
    };
    
    // Предзагруженные данные (если редактируем)
    const TEMPLATE_DATA = {{ template_data | tojson | safe if template_data else 'null' }};
    
    // Модифицированный JS из workload_template_gup_v2.html
    // Заменить загрузку файла на fetch из API
    
    async function loadGroups() {
        const resp = await fetch(API.groups);
        const groups = await resp.json();
        // ... заполнить select
    }
    
    async function loadWorkloads(groupId) {
        const resp = await fetch(API.workloads + groupId);
        const workloads = await resp.json();
        // ... заполнить select дисциплин
    }
    
    async function saveTemplate() {
        const config = generateConfig();
        
        // Добавить ID для связей
        config.meta.group_id = parseInt(document.getElementById('groupSelect').value);
        config.meta.workload_id = parseInt(document.getElementById('workloadSelect').value);
        
        const resp = await fetch(API.templates, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        
        const result = await resp.json();
        if (result.success) {
            toast('Шаблон сохранён!', 'success');
        }
    }
    
    // Инициализация
    document.addEventListener('DOMContentLoaded', async () => {
        await loadGroups();
        
        if (TEMPLATE_DATA) {
            // Загрузить существующий шаблон
            loadTemplateData(TEMPLATE_DATA);
        }
    });
</script>
{% endblock %}
```

---

## 📝 Изменения в HTML редакторе

### Добавить select для дисциплины:
```html
<div class="form-group">
    <label>Дисциплина</label>
    <select id="workloadSelect" style="min-width: 200px;">
        <option value="">-- Выберите --</option>
    </select>
</div>
```

### Убрать:
- Модалку загрузки файла (`#uploadModal`)
- Кнопку "📁 ГУП"
- localStorage сохранение

### Заменить:
- `loadFile()` → `loadGroups()` + `loadWorkloads()`
- `saveTemplate()` → POST на API
- `exportTemplate()` → можно оставить для локальной копии

---

## 🗄️ Миграция БД

```python
# migrations/add_workload_templates.py

def upgrade():
    op.create_table('workload_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('workload_id', sa.Integer(), sa.ForeignKey('workload.id')),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id')),
        sa.Column('semester', sa.Integer(), nullable=False),
        sa.Column('total_hours', sa.Integer(), nullable=False),
        sa.Column('distribution_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime()),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'))
    )

def downgrade():
    op.drop_table('workload_templates')
```

---

## ✅ Чеклист интеграции

1. [ ] Создать модель `WorkloadTemplate`
2. [ ] Создать миграцию и применить
3. [ ] Создать API endpoints (`/api/workload-templates/`)
4. [ ] Создать endpoint `/api/groups-with-gup`
5. [ ] Создать endpoint `/api/workloads-by-group/<id>`
6. [ ] Создать Jinja2 шаблон `editor.html`
7. [ ] Адаптировать JS для работы с API
8. [ ] Добавить select для выбора дисциплины
9. [ ] Добавить ссылку в меню навигации
10. [ ] Интегрировать с `scheduler.py`
11. [ ] Протестировать создание/редактирование/удаление
12. [ ] Протестировать генерацию расписания с шаблонами

---

## 🤔 Вопросы для уточнения

1. Как точно называются поля в модели `Workload`? (subject или discipline?)
2. Есть ли поле `semester` в `Workload` или семестр определяется по дате?
3. Нужно ли добавить роль "методист" для доступа к редактору?
4. Куда добавить ссылку на редактор в навигации?
5. Нужна ли история изменений шаблонов?
