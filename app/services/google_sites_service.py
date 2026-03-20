"""
Google Sites интеграция для расписания колледжа
Генерация HTML контента и публикация на Google Sites
"""

import json
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from flask import current_app


class GoogleSitesHTMLGenerator:
    """Генератор HTML контента для Google Sites"""
    
    def __init__(self):
        self.api_base_url = ""  # Будет заполнен при генерации
        
    def generate_static_schedule_page(self, groups_data: list, teachers_data: list, schedule_data: dict, 
                                     selected_group_id: int = None, selected_teacher_id: int = None, 
                                     view_type: str = 'week', period_info: dict = None) -> str:
        """Генерирует статическую страницу расписания с встроенными данными"""
        
        # Подготовка данных для встраивания
        groups_json = json.dumps(groups_data, ensure_ascii=False)
        teachers_json = json.dumps(teachers_data, ensure_ascii=False)
        schedule_json = json.dumps(schedule_data, ensure_ascii=False)
        
        html = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Расписание АПЭК Петротехник</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
    {self._get_schedule_styles()}
</head>
<body>
    <div class="container-fluid p-3">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h2><i class="bi bi-calendar3"></i> APEC Petrotechnic College Schedule</h2>
                <p class="text-muted mb-0">Статическая версия расписания (данные на {datetime.now().strftime('%d.%m.%Y %H:%M')})</p>
            </div>
            <div class="btn-group">
                <button class="btn btn-outline-primary btn-sm" onclick="refreshSchedule()">
                    <i class="bi bi-arrow-clockwise"></i> Обновить
                </button>
            </div>
        </div>

        <!-- Фильтры -->
        <div class="card mb-4">
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-4">
                        <label class="form-label">Группа</label>
                        <select id="groupSelect" class="form-select" onchange="updateSchedule()">
                            <option value="">-- Выберите группу --</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Преподаватель</label>
                        <select id="teacherSelect" class="form-select" onchange="updateSchedule()">
                            <option value="">-- Или преподавателя --</option>
                        </select>
                    </div>
                    <div class="col-md-4 d-flex align-items-end">
                        <div class="btn-group btn-group-sm" role="group">
                            <input type="radio" class="btn-check" name="view" id="view_week" value="week" checked onchange="updateSchedule()">
                            <label class="btn btn-outline-primary" for="view_week">Неделя</label>
                            
                            <input type="radio" class="btn-check" name="view" id="view_month" value="month" onchange="updateSchedule()">
                            <label class="btn btn-outline-primary" for="view_month">Месяц</label>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Навигация по периодам -->
        <div class="d-flex justify-content-between align-items-center mb-3">
            <button class="btn btn-outline-primary" onclick="navigatePeriod(-1)">
                <i class="bi bi-chevron-left"></i> <span id="prevLabel">Пред. неделя</span>
            </button>
            <div class="text-center">
                <h5 id="periodTitle" class="mb-0">Загрузка...</h5>
                <small id="periodDates" class="text-muted"></small>
            </div>
            <button class="btn btn-outline-primary" onclick="navigatePeriod(1)">
                <span id="nextLabel">След. неделя</span> <i class="bi bi-chevron-right"></i>
            </button>
        </div>

        <!-- Контент расписания -->
        <div id="scheduleContent"></div>

        <!-- Сообщение когда не выбрана группа -->
        <div id="noSelectionMessage" class="card" style="display: none;">
            <div class="card-body text-center py-5">
                <div class="mb-4">
                    <i class="bi bi-calendar-check" style="font-size: 4rem; color: #6c757d;"></i>
                </div>
                <h4 class="text-muted mb-3">Выберите группу или преподавателя</h4>
                <p class="text-muted">
                    Для просмотра расписания выберите группу или преподавателя из списка выше
                </p>
            </div>
        </div>

        <!-- Легенда -->
        <div class="card mt-4">
            <div class="card-body">
                <h6>Статусы занятий:</h6>
                <div class="d-flex flex-wrap gap-3">
                    <span class="badge status-planned border px-3 py-2">Запланирована</span>
                    <span class="badge status-done border px-3 py-2">Проведена</span>
                    <span class="badge status-substitution border px-3 py-2">Замена</span>
                    <span class="badge status-cancelled border px-3 py-2">Отменена</span>
                    <span class="badge status-completed border px-3 py-2">Последняя пара</span>
                    <span class="badge status-rescheduled border px-3 py-2">Перенесена</span>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        // СТАТИЧЕСКИЕ ДАННЫЕ (встроены в HTML)
        const STATIC_GROUPS = {groups_json};
        const STATIC_TEACHERS = {teachers_json};
        const STATIC_SCHEDULE = {schedule_json};
        
        {self._get_static_schedule_javascript(selected_group_id, view_type)}
    </script>
</body>
</html>
        """
        return html
    
    def _get_static_schedule_javascript(self, selected_group_id: int = None, view_type: str = 'week') -> str:
        """Генерирует JavaScript для работы со статическими данными"""
        return f"""
        // Конфигурация
        const PAIR_TIMES = {{
            1: {{start: '08:30', end: '09:50'}},
            2: {{start: '10:00', end: '11:20'}},
            3: {{start: '11:30', end: '12:50'}},
            4: {{start: '13:30', end: '14:50'}},
            5: {{start: '15:00', end: '16:20'}},
            6: {{start: '16:30', end: '17:50'}},
            7: {{start: '18:00', end: '19:20'}},
            8: {{start: '19:30', end: '20:50'}}
        }};
        
        // Глобальные переменные
        let currentGroupId = {selected_group_id or 'null'};
        let currentTeacherId = null;
        let currentView = '{view_type}';
        let currentWeekOffset = 0;
        let currentMonthOffset = 0;
        
        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', function() {{
            loadStaticGroups();
            loadStaticTeachers();
            
            if (currentGroupId) {{
                document.getElementById('groupSelect').value = currentGroupId;
                loadSchedule();
            }} else {{
                showNoSelectionMessage();
            }}
        }});
        
        // Загрузка списка групп из статических данных
        function loadStaticGroups() {{
            const select = document.getElementById('groupSelect');
            select.innerHTML = '<option value="">-- Выберите группу --</option>';
            
            if (STATIC_GROUPS && STATIC_GROUPS.groups) {{
                STATIC_GROUPS.groups.forEach(group => {{
                    const option = document.createElement('option');
                    option.value = group.id;
                    option.textContent = group.name;
                    if (group.id === currentGroupId) option.selected = true;
                    select.appendChild(option);
                }});
            }}
        }}
        
        // Загрузка списка преподавателей из статических данных
        function loadStaticTeachers() {{
            const select = document.getElementById('teacherSelect');
            select.innerHTML = '<option value="">-- Или преподавателя --</option>';
            
            if (STATIC_TEACHERS && STATIC_TEACHERS.teachers) {{
                STATIC_TEACHERS.teachers.forEach(teacher => {{
                    const option = document.createElement('option');
                    option.value = teacher.id;
                    option.textContent = teacher.name;
                    select.appendChild(option);
                }});
            }}
        }}
        
        // Обновление расписания при изменении фильтров
        function updateSchedule() {{
            const groupSelect = document.getElementById('groupSelect');
            const teacherSelect = document.getElementById('teacherSelect');
            const viewRadios = document.querySelectorAll('input[name="view"]');
            
            // Получаем текущие значения
            const newGroupId = groupSelect.value ? parseInt(groupSelect.value) : null;
            const newTeacherId = teacherSelect.value ? parseInt(teacherSelect.value) : null;
            let newView = 'week';
            
            viewRadios.forEach(radio => {{
                if (radio.checked) newView = radio.value;
            }});
            
            // Сбрасываем противоположный фильтр
            if (newGroupId) {{
                teacherSelect.value = '';
                currentTeacherId = null;
            }} else if (newTeacherId) {{
                groupSelect.value = '';
                currentGroupId = null;
            }}
            
            currentGroupId = newGroupId;
            currentTeacherId = newTeacherId;
            currentView = newView;
            
            // Обновляем лейблы навигации
            updateNavigationLabels();
            
            // Загружаем расписание или показываем сообщение
            if (currentGroupId || currentTeacherId) {{
                loadSchedule();
            }} else {{
                showNoSelectionMessage();
            }}
        }}
        
        // Обновление лейблов навигации
        function updateNavigationLabels() {{
            const prevLabel = document.getElementById('prevLabel');
            const nextLabel = document.getElementById('nextLabel');
            
            if (currentView === 'week') {{
                prevLabel.textContent = 'Пред. неделя';
                nextLabel.textContent = 'След. неделя';
            }} else if (currentView === 'month') {{
                prevLabel.textContent = 'Пред. месяц';
                nextLabel.textContent = 'След. месяц';
            }}
        }}
        
        // Навигация по периодам
        function navigatePeriod(direction) {{
            if (currentView === 'week') {{
                currentWeekOffset += direction;
            }} else if (currentView === 'month') {{
                currentMonthOffset += direction;
            }}
            
            if (currentGroupId || currentTeacherId) {{
                loadSchedule();
            }}
        }}
        
        // Показать сообщение о выборе
        function showNoSelectionMessage() {{
            document.getElementById('scheduleContent').style.display = 'none';
            document.getElementById('noSelectionMessage').style.display = 'block';
            document.getElementById('periodTitle').textContent = 'Выберите фильтр';
            document.getElementById('periodDates').textContent = '';
        }}
        
        // Загрузка расписания из статических данных
        function loadSchedule() {{
            try {{
                // Вычисляем период
                const period = calculatePeriod();
                
                // Фильтруем данные
                const filteredSchedules = filterStaticScheduleData(period);
                
                if (filteredSchedules.length > 0) {{
                    displaySchedule(filteredSchedules, period);
                }} else {{
                    showEmptySchedule(period);
                }}
            }} catch (error) {{
                console.error('Ошибка загрузки расписания:', error);
                showError('Ошибка обработки данных расписания');
            }}
        }}
        
        // Фильтрация статических данных расписания
        function filterStaticScheduleData(period) {{
            if (!STATIC_SCHEDULE || !STATIC_SCHEDULE.schedules) return [];
            
            return STATIC_SCHEDULE.schedules.filter(schedule => {{
                const scheduleDate = new Date(schedule.date);
                const periodStart = new Date(period.start);
                const periodEnd = new Date(period.end);
                
                // Проверка периода
                if (scheduleDate < periodStart || scheduleDate > periodEnd) return false;
                
                // Проверка фильтров
                if (currentGroupId && schedule.group && schedule.group.id !== currentGroupId) return false;
                if (currentTeacherId && schedule.teacher && schedule.teacher.id !== currentTeacherId) return false;
                
                return true;
            }});
        }}
        
        // Вычисление периода для отображения
        function calculatePeriod() {{
            const today = new Date();
            const monday = new Date(today);
            monday.setDate(monday.getDate() - monday.getDay() + 1); // Понедельник
            
            if (currentView === 'week') {{
                const start = new Date(monday);
                start.setDate(start.getDate() + currentWeekOffset * 7);
                const end = new Date(start);
                end.setDate(end.getDate() + 6);
                
                return {{
                    start: formatDate(start),
                    end: formatDate(end),
                    startDate: start,
                    endDate: end
                }};
            }} else if (currentView === 'month') {{
                const target = new Date(today.getFullYear(), today.getMonth() + currentMonthOffset, 1);
                const start = new Date(target.getFullYear(), target.getMonth(), 1);
                const end = new Date(target.getFullYear(), target.getMonth() + 1, 0);
                
                return {{
                    start: formatDate(start),
                    end: formatDate(end),
                    startDate: start,
                    endDate: end
                }};
            }}
        }}
        
        // Форматирование даты для API
        function formatDate(date) {{
            return date.toISOString().split('T')[0];
        }}
        
        // Форматирование даты для отображения
        function formatDisplayDate(date) {{
            return date.toLocaleDateString('ru-RU', {{
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            }});
        }}
        
        // Отображение расписания
        function displaySchedule(schedules, period) {{
            updatePeriodTitle(period);
            
            if (currentView === 'week') {{
                displayWeekSchedule(schedules, period);
            }} else if (currentView === 'month') {{
                displayMonthSchedule(schedules, period);
            }}
            
            document.getElementById('scheduleContent').style.display = 'block';
            document.getElementById('noSelectionMessage').style.display = 'none';
        }}
        
        // Отображение пустого расписания
        function showEmptySchedule(period) {{
            updatePeriodTitle(period);
            
            document.getElementById('scheduleContent').innerHTML = `
                <div class="alert alert-info text-center">
                    <i class="bi bi-calendar-x" style="font-size: 3rem;"></i>
                    <h5 class="mt-3">Расписание отсутствует</h5>
                    <p class="mb-0">На выбранный период расписание не найдено</p>
                </div>
            `;
            
            document.getElementById('scheduleContent').style.display = 'block';
            document.getElementById('noSelectionMessage').style.display = 'none';
        }}
        
        // Обновление заголовка периода
        function updatePeriodTitle(period) {{
            const title = document.getElementById('periodTitle');
            const dates = document.getElementById('periodDates');
            
            if (currentView === 'week') {{
                const weekNum = Math.abs(currentWeekOffset) + 1;
                const direction = currentWeekOffset >= 0 ? 'через' : 'назад';
                title.textContent = currentWeekOffset === 0 ? 'Текущая неделя' : `Неделя ${{weekNum}} (${{direction}})`;
                dates.textContent = `${{formatDisplayDate(period.startDate)}} - ${{formatDisplayDate(period.endDate)}}`;
            }} else if (currentView === 'month') {{
                title.textContent = period.startDate.toLocaleDateString('ru-RU', {{month: 'long', year: 'numeric'}});
                dates.textContent = `${{formatDisplayDate(period.startDate)}} - ${{formatDisplayDate(period.endDate)}}`;
            }}
        }}
        
        // Отображение недельного расписания
        function displayWeekSchedule(schedules, period) {{
            // Группируем расписание по дням и парам
            const scheduleGrid = {{}};
            schedules.forEach(schedule => {{
                const date = new Date(schedule.date);
                const dayIndex = date.getDay() - 1; // Понедельник = 0
                if (dayIndex >= 0 && dayIndex < 5) {{ // Только будние дни
                    if (!scheduleGrid[dayIndex]) scheduleGrid[dayIndex] = {{}};
                    scheduleGrid[dayIndex][schedule.pair_number] = schedule;
                }}
            }});
            
            let html = `
                <div class="card">
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-bordered">
                                <thead>
                                    <tr class="table-light">
                                        <th style="width: 60px;">Пара</th>
                                        <th style="width: 100px;">Время</th>`;
            
            // Заголовки дней недели
            const dayNames = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница'];
            for (let dayIndex = 0; dayIndex < 5; dayIndex++) {{
                const dayDate = new Date(period.startDate);
                dayDate.setDate(dayDate.getDate() + dayIndex);
                html += `<th>${{dayNames[dayIndex]}}<br><small>${{formatDisplayDate(dayDate)}}</small></th>`;
            }}
            
            html += `</tr></thead><tbody>`;
            
            // Строки с парами
            for (let pairNum = 1; pairNum <= 8; pairNum++) {{
                html += `<tr>
                    <td class="text-center fw-bold">${{pairNum}}</td>
                    <td class="text-center">
                        <small>${{PAIR_TIMES[pairNum].start}}<br>${{PAIR_TIMES[pairNum].end}}</small>
                    </td>`;
                
                for (let dayIndex = 0; dayIndex < 5; dayIndex++) {{
                    const schedule = scheduleGrid[dayIndex] && scheduleGrid[dayIndex][pairNum];
                    if (schedule) {{
                        html += `<td class="schedule-cell status-${{schedule.status}}">
                            <div class="discipline">${{schedule.discipline}}</div>
                            <div class="teacher">${{schedule.teacher ? schedule.teacher.name : '-'}}</div>
                            <div class="room">ауд. ${{schedule.room ? schedule.room.number : '-'}}</div>
                        </td>`;
                    }} else {{
                        html += `<td class="schedule-cell status-empty"></td>`;
                    }}
                }}
                
                html += `</tr>`;
                
                // Обеденный перерыв после 3 пары
                if (pairNum === 3) {{
                    html += `<tr class="table-secondary">
                        <td colspan="7" class="text-center py-1"><strong>ОБЕД</strong> 12:50 - 13:30</td>
                    </tr>`;
                }}
            }}
            
            html += `</tbody></table></div></div></div>`;
            
            document.getElementById('scheduleContent').innerHTML = html;
        }}
        
        // Отображение месячного расписания
        function displayMonthSchedule(schedules, period) {{
            // Группируем по дням (только рабочие дни - пн-пт)
            const scheduleByDay = {{}};
            schedules.forEach(schedule => {{
                const date = schedule.date;
                const dayOfWeek = new Date(date).getDay();
                // Пропускаем выходные (0 - воскресенье, 6 - суббота)
                if (dayOfWeek === 0 || dayOfWeek === 6) return;
                if (!scheduleByDay[date]) scheduleByDay[date] = [];
                scheduleByDay[date].push(schedule);
            }});

            let html = `<div class="card"><div class="card-body">
                <h5 class="mb-3"><i class="bi bi-calendar-month"></i> ${{period.startDate.toLocaleDateString('ru-RU', {{month: 'long', year: 'numeric'}})}}</h5>
                <div class="row">`;

            // Простой список по дням
            const days = Object.keys(scheduleByDay).sort();
            if (days.length === 0) {{
                html += `<div class="col-12 text-center py-5">
                    <i class="bi bi-calendar-x" style="font-size: 3rem; color: #6c757d;"></i>
                    <h5 class="mt-3 text-muted">Расписание отсутствует</h5>
                    <p class="text-muted">На выбранный месяц расписание не найдено</p>
                </div>`;
            }} else {{
                days.forEach(date => {{
                    const daySchedules = scheduleByDay[date];
                    const displayDate = new Date(date).toLocaleDateString('ru-RU', {{weekday: 'short', day: '2-digit', month: '2-digit'}});

                    html += `<div class="col-md-6 col-lg-4 mb-3">
                        <div class="card">
                            <div class="card-header">
                                <strong>${{displayDate}}</strong>
                            </div>
                            <div class="card-body p-2">`;

                    daySchedules.forEach(schedule => {{
                        html += `<div class="small mb-1 p-1 rounded status-${{schedule.status}}">
                            ${{schedule.pair_number}}) ${{schedule.discipline.substring(0, 30)}}...
                            <div class="text-muted">${{schedule.teacher ? schedule.teacher.name : '-'}}</div>
                        </div>`;
                    }});

                    html += `</div></div></div>`;
                }});
            }}

            html += `</div></div></div>`;

            document.getElementById('scheduleContent').innerHTML = html;
        }}
        
        // Показать ошибку
        function showError(message) {{
            document.getElementById('scheduleContent').innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> ${{message}}
                </div>
            `;
            document.getElementById('scheduleContent').style.display = 'block';
        }}
        
        // Обновление расписания (заглушка для статической версии)
        function refreshSchedule() {{
            alert('Это статическая версия расписания. Для обновления данных перегенерируйте HTML файл.');
        }}
        """

    def generate_interactive_schedule_page(self, base_url: str = None) -> str:
        """Генерирует интерактивную страницу расписания как в системе просмотра"""
        self.api_base_url = base_url or ""
        
        html = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Расписание АПЭК Петротехник</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
    {self._get_schedule_styles()}
</head>
<body>
    <div class="container-fluid p-3">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h2><i class="bi bi-calendar3"></i> APEC Petrotechnic College Schedule</h2>
                <p class="text-muted mb-0">Актуальное расписание занятий в режиме реального времени</p>
            </div>
            <div class="btn-group">
                <button class="btn btn-outline-primary btn-sm" onclick="refreshSchedule()">
                    <i class="bi bi-arrow-clockwise"></i> Обновить
                </button>
            </div>
        </div>

        <!-- Фильтры -->
        <div class="card mb-4">
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-4">
                        <label class="form-label">Группа</label>
                        <select id="groupSelect" class="form-select" onchange="updateSchedule()">
                            <option value="">-- Выберите группу --</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Преподаватель</label>
                        <select id="teacherSelect" class="form-select" onchange="updateSchedule()">
                            <option value="">-- Или преподавателя --</option>
                        </select>
                    </div>
                    <div class="col-md-4 d-flex align-items-end">
                        <div class="btn-group btn-group-sm" role="group">
                            <input type="radio" class="btn-check" name="view" id="view_week" value="week" checked onchange="updateSchedule()">
                            <label class="btn btn-outline-primary" for="view_week">Неделя</label>
                            
                            <input type="radio" class="btn-check" name="view" id="view_month" value="month" onchange="updateSchedule()">
                            <label class="btn btn-outline-primary" for="view_month">Месяц</label>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Навигация по периодам -->
        <div class="d-flex justify-content-between align-items-center mb-3">
            <button class="btn btn-outline-primary" onclick="navigatePeriod(-1)">
                <i class="bi bi-chevron-left"></i> <span id="prevLabel">Пред. неделя</span>
            </button>
            <div class="text-center">
                <h5 id="periodTitle" class="mb-0">Загрузка...</h5>
                <small id="periodDates" class="text-muted"></small>
            </div>
            <button class="btn btn-outline-primary" onclick="navigatePeriod(1)">
                <span id="nextLabel">След. неделя</span> <i class="bi bi-chevron-right"></i>
            </button>
        </div>

        <!-- Загрузка -->
        <div id="loadingIndicator" class="text-center py-5">
            <div class="spinner-border" role="status"></div>
            <p class="mt-2">Загрузка расписания...</p>
        </div>

        <!-- Контент расписания -->
        <div id="scheduleContent" style="display: none;"></div>

        <!-- Сообщение когда не выбрана группа -->
        <div id="noSelectionMessage" class="card" style="display: none;">
            <div class="card-body text-center py-5">
                <div class="mb-4">
                    <i class="bi bi-calendar-check" style="font-size: 4rem; color: #6c757d;"></i>
                </div>
                <h4 class="text-muted mb-3">Выберите группу или преподавателя</h4>
                <p class="text-muted">
                    Для просмотра расписания выберите группу или преподавателя из списка выше
                </p>
            </div>
        </div>

        <!-- Легенда -->
        <div class="card mt-4">
            <div class="card-body">
                <h6>Статусы занятий:</h6>
                <div class="d-flex flex-wrap gap-3">
                    <span class="badge status-planned border px-3 py-2">Запланирована</span>
                    <span class="badge status-done border px-3 py-2">Проведена</span>
                    <span class="badge status-substitution border px-3 py-2">Замена</span>
                    <span class="badge status-cancelled border px-3 py-2">Отменена</span>
                    <span class="badge status-completed border px-3 py-2">Последняя пара</span>
                    <span class="badge status-rescheduled border px-3 py-2">Перенесена</span>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    {self._get_schedule_javascript()}
</body>
</html>"""
        return html
    
    def _get_schedule_styles(self) -> str:
        """Стили для расписания, аналогичные системе просмотра"""
        return """
        <style>
        :root {{
            --sidebar-width: 0px; /* Убираем sidebar для Google Sites */
        }}
        
        .schedule-cell {{
            min-height: 80px;
            font-size: 0.85rem;
            vertical-align: top;
            padding: 0.5rem !important;
        }}
        .schedule-cell .discipline {{
            font-weight: 600;
            margin-bottom: 0.25rem;
        }}
        .schedule-cell .teacher {{
            color: #666;
            font-size: 0.8rem;
        }}
        .schedule-cell .room {{
            color: #999;
            font-size: 0.75rem;
        }}
        
        /* Статусы занятий */
        .status-planned {{ background-color: #fff !important; border: 2px solid #6c757d !important; }}
        .status-done {{ background-color: #d4edda !important; border: 2px solid #28a745 !important; }}
        .status-substitution {{ background-color: #fff3cd !important; border: 2px solid #ffc107 !important; }}
        .status-cancelled {{ background-color: #f8d7da !important; border: 2px solid #dc3545 !important; text-decoration: line-through !important; opacity: 0.7 !important; }}
        .status-completed {{ background-color: #e2d5f1 !important; border: 2px solid #6f42c1 !important; }}
        .status-rescheduled {{ background-color: #d1ecf1 !important; border: 2px solid #17a2b8 !important; }}
        .status-empty {{ background-color: #f8f9fa !important; }}
        
        /* Стили для легенды */
        .badge.status-planned {{ background-color: #6c757d !important; color: #fff !important; }}
        .badge.status-done {{ background-color: #28a745 !important; color: #fff !important; }}
        .badge.status-substitution {{ background-color: #ffc107 !important; color: #000 !important; }}
        .badge.status-cancelled {{ background-color: #dc3545 !important; color: #fff !important; }}
        .badge.status-completed {{ background-color: #6f42c1 !important; color: #fff !important; }}
        .badge.status-rescheduled {{ background-color: #17a2b8 !important; color: #fff !important; }}
        
        /* Оптимизация для Google Sites embed */
        body {{
            margin: 0 !important;
            padding: 0 !important;
            background-color: transparent !important;
        }}
        
        .container-fluid {{
            max-width: 100% !important;
            overflow-x: auto;
        }}
        
        /* Таблица расписания */
        .schedule-table {{
            width: 100% !important;
            min-width: 800px; /* Минимальная ширина для сохранения читаемости */
            table-layout: auto;
        }}
        
        /* Мобильная адаптация (современные практики 2025) */
        @media (max-width: 768px) {{
            body {{
                font-size: 14px !important;
            }}
            
            .container-fluid {{
                padding: 0.5rem !important;
            }}
            
            .schedule-table {{
                min-width: 600px; /* Уменьшенная минимальная ширина на мобильных */
                font-size: 12px !important;
            }}
            
            .schedule-cell {{
                min-height: 50px !important;
                font-size: 0.65rem !important;
                padding: 0.25rem !important;
                line-height: 1.2 !important;
            }}
            
            .schedule-cell .discipline {{
                font-size: 0.7rem !important;
                margin-bottom: 0.15rem !important;
            }}
            
            .schedule-cell .teacher {{
                font-size: 0.6rem !important;
            }}
            
            .schedule-cell .room {{
                font-size: 0.55rem !important;
            }}
            
            /* Адаптивные фильтры */
            .card-body .row {{
                flex-direction: column !important;
            }}
            
            .card-body .col-md-4 {{
                margin-bottom: 0.5rem !important;
            }}
            
            /* Touch-friendly кнопки (минимум 44px) */
            .btn {{
                min-height: 44px !important;
                min-width: 44px !important;
            }}
            
            .form-select, .form-control {{
                min-height: 44px !important;
                font-size: 16px !important; /* Предотвращение зума на iOS */
            }}
        }}
        
        /* Экстра маленькие экраны */
        @media (max-width: 480px) {{
            .schedule-table {{
                min-width: 500px;
                font-size: 11px !important;
            }}
            
            .schedule-cell {{
                min-height: 40px !important;
                font-size: 0.6rem !important;
                padding: 0.2rem !important;
            }}
            
            .schedule-cell .discipline {{
                font-size: 0.65rem !important;
            }}
            
            .schedule-cell .teacher,
            .schedule-cell .room {{
                font-size: 0.5rem !important;
            }}
            
            /* Горизонтальная прокрутка таблицы */
            .table-responsive {{
                border: none !important;
            }}
        }}
        
        /* Оптимизация для больших экранов */
        @media (min-width: 1200px) {{
            .schedule-cell {{
                min-height: 90px;
                font-size: 0.9rem;
                padding: 0.6rem !important;
            }}
            .schedule-cell .teacher,
            .schedule-cell .room {{
                font-size: 0.6rem;
            }}
        }}
        
        .table-responsive {{
            border-radius: 0.5rem;
            overflow: hidden;
        }}
        
        .card {{
            border: none;
            box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
        }}
        </style>
        """

    def _get_schedule_javascript(self) -> str:
        """JavaScript для интерактивной работы с расписанием"""
        return f"""
        <script>
        // Конфигурация
        const API_BASE = '{self.api_base_url}';
        const PAIR_TIMES = {{
            1: {{start: '08:30', end: '09:50'}},
            2: {{start: '10:00', end: '11:20'}},
            3: {{start: '11:30', end: '12:50'}},
            4: {{start: '13:30', end: '14:50'}},
            5: {{start: '15:00', end: '16:20'}},
            6: {{start: '16:30', end: '17:50'}},
            7: {{start: '18:00', end: '19:20'}},
            8: {{start: '19:30', end: '20:50'}}
        }};
        
        // Глобальные переменные
        let currentGroupId = null;
        let currentTeacherId = null;
        let currentView = 'week';
        let currentWeekOffset = 0;
        let currentMonthOffset = 0;
        
        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', function() {{
            loadGroups();
            loadTeachers();
            showNoSelectionMessage();
        }});
        
        // Загрузка списка групп
        async function loadGroups() {{
            try {{
                const response = await fetch(API_BASE + '/google-sheets/api/groups');
                const data = await response.json();
                
                if (data.success) {{
                    const select = document.getElementById('groupSelect');
                    select.innerHTML = '<option value="">-- Выберите группу --</option>';
                    data.groups.forEach(group => {{
                        const option = document.createElement('option');
                        option.value = group.id;
                        option.textContent = group.name;
                        select.appendChild(option);
                    }});
                }}
            }} catch (error) {{
                console.error('Ошибка загрузки групп:', error);
            }}
        }}
        
        // Загрузка списка преподавателей
        async function loadTeachers() {{
            try {{
                const response = await fetch(API_BASE + '/google-sheets/api/teachers');
                const data = await response.json();
                
                if (data.success) {{
                    const select = document.getElementById('teacherSelect');
                    select.innerHTML = '<option value="">-- Или преподавателя --</option>';
                    data.teachers.forEach(teacher => {{
                        const option = document.createElement('option');
                        option.value = teacher.id;
                        option.textContent = teacher.name;
                        select.appendChild(option);
                    }});
                }}
            }} catch (error) {{
                console.error('Ошибка загрузки преподавателей:', error);
            }}
        }}
        
        // Обновление расписания при изменении фильтров
        function updateSchedule() {{
            const groupSelect = document.getElementById('groupSelect');
            const teacherSelect = document.getElementById('teacherSelect');
            const viewRadios = document.querySelectorAll('input[name="view"]');
            
            // Получаем текущие значения
            const newGroupId = groupSelect.value || null;
            const newTeacherId = teacherSelect.value || null;
            let newView = 'week';
            
            viewRadios.forEach(radio => {{
                if (radio.checked) newView = radio.value;
            }});
            
            // Сбрасываем противоположный фильтр
            if (newGroupId) {{
                teacherSelect.value = '';
                currentTeacherId = null;
            }} else if (newTeacherId) {{
                groupSelect.value = '';
                currentGroupId = null;
            }}
            
            currentGroupId = newGroupId;
            currentTeacherId = newTeacherId;
            currentView = newView;
            
            // Обновляем лейблы навигации
            updateNavigationLabels();
            
            // Загружаем расписание или показываем сообщение
            if (currentGroupId || currentTeacherId) {{
                loadSchedule();
            }} else {{
                showNoSelectionMessage();
            }}
        }}
        
        // Обновление лейблов навигации
        function updateNavigationLabels() {{
            const prevLabel = document.getElementById('prevLabel');
            const nextLabel = document.getElementById('nextLabel');
            
            if (currentView === 'week') {{
                prevLabel.textContent = 'Пред. неделя';
                nextLabel.textContent = 'След. неделя';
            }} else if (currentView === 'month') {{
                prevLabel.textContent = 'Пред. месяц';
                nextLabel.textContent = 'След. месяц';
            }}
        }}
        
        // Навигация по периодам
        function navigatePeriod(direction) {{
            if (currentView === 'week') {{
                currentWeekOffset += direction;
            }} else if (currentView === 'month') {{
                currentMonthOffset += direction;
            }}
            
            if (currentGroupId || currentTeacherId) {{
                loadSchedule();
            }}
        }}
        
        // Показать сообщение о выборе
        function showNoSelectionMessage() {{
            document.getElementById('loadingIndicator').style.display = 'none';
            document.getElementById('scheduleContent').style.display = 'none';
            document.getElementById('noSelectionMessage').style.display = 'block';
            document.getElementById('periodTitle').textContent = 'Выберите фильтр';
            document.getElementById('periodDates').textContent = '';
        }}
        
        // Показать индикатор загрузки
        function showLoading() {{
            document.getElementById('loadingIndicator').style.display = 'block';
            document.getElementById('scheduleContent').style.display = 'none';
            document.getElementById('noSelectionMessage').style.display = 'none';
        }}
        
        // Загрузка расписания
        async function loadSchedule() {{
            showLoading();
            
            try {{
                // Вычисляем период
                const period = calculatePeriod();
                const params = new URLSearchParams({{
                    start_date: period.start,
                    end_date: period.end
                }});
                
                if (currentGroupId) params.append('group_id', currentGroupId);
                if (currentTeacherId) params.append('teacher_id', currentTeacherId);
                
                const response = await fetch(API_BASE + `/google-sheets/api/schedule?${{params}}`);
                const data = await response.json();
                
                if (data.success) {{
                    displaySchedule(data.schedules, period);
                }} else {{
                    showError('Ошибка загрузки расписания: ' + data.error);
                }}
            }} catch (error) {{
                console.error('Ошибка загрузки расписания:', error);
                showError('Ошибка соединения с сервером');
            }}
        }}
        
        // Вычисление периода для запроса
        function calculatePeriod() {{
            const today = new Date();
            const monday = new Date(today);
            monday.setDate(monday.getDate() - monday.getDay() + 1); // Понедельник
            
            if (currentView === 'week') {{
                const start = new Date(monday);
                start.setDate(start.getDate() + currentWeekOffset * 7);
                const end = new Date(start);
                end.setDate(end.getDate() + 6);
                
                return {{
                    start: formatDate(start),
                    end: formatDate(end),
                    startDate: start,
                    endDate: end
                }};
            }} else if (currentView === 'month') {{
                const target = new Date(today.getFullYear(), today.getMonth() + currentMonthOffset, 1);
                const start = new Date(target.getFullYear(), target.getMonth(), 1);
                const end = new Date(target.getFullYear(), target.getMonth() + 1, 0);
                
                return {{
                    start: formatDate(start),
                    end: formatDate(end),
                    startDate: start,
                    endDate: end
                }};
            }}
        }}
        
        // Форматирование даты для API
        function formatDate(date) {{
            return date.toISOString().split('T')[0];
        }}
        
        // Форматирование даты для отображения
        function formatDisplayDate(date) {{
            return date.toLocaleDateString('ru-RU', {{
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            }});
        }}
        
        // Отображение расписания
        function displaySchedule(schedules, period) {{
            updatePeriodTitle(period);
            
            if (currentView === 'week') {{
                displayWeekSchedule(schedules, period);
            }} else if (currentView === 'month') {{
                displayMonthSchedule(schedules, period);
            }}
            
            document.getElementById('loadingIndicator').style.display = 'none';
            document.getElementById('scheduleContent').style.display = 'block';
            document.getElementById('noSelectionMessage').style.display = 'none';
        }}
        
        // Обновление заголовка периода
        function updatePeriodTitle(period) {{
            const title = document.getElementById('periodTitle');
            const dates = document.getElementById('periodDates');
            
            if (currentView === 'week') {{
                const weekNum = currentWeekOffset + 1;
                title.textContent = `Неделя ${{weekNum}}`;
                dates.textContent = `${{formatDisplayDate(period.startDate)}} - ${{formatDisplayDate(period.endDate)}}`;
            }} else if (currentView === 'month') {{
                title.textContent = period.startDate.toLocaleDateString('ru-RU', {{month: 'long', year: 'numeric'}});
                dates.textContent = `${{formatDisplayDate(period.startDate)}} - ${{formatDisplayDate(period.endDate)}}`;
            }}
        }}
        
        // Отображение недельного расписания
        function displayWeekSchedule(schedules, period) {{
            // Группируем расписание по дням и парам
            const scheduleGrid = {{}};
            schedules.forEach(schedule => {{
                const date = new Date(schedule.date);
                const dayIndex = date.getDay() - 1; // Понедельник = 0
                if (dayIndex >= 0 && dayIndex < 5) {{ // Только будние дни
                    if (!scheduleGrid[dayIndex]) scheduleGrid[dayIndex] = {{}};
                    scheduleGrid[dayIndex][schedule.pair_number] = schedule;
                }}
            }});
            
            let html = `
                <div class="card">
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-bordered">
                                <thead>
                                    <tr class="table-light">
                                        <th style="width: 60px;">Пара</th>
                                        <th style="width: 100px;">Время</th>`;
            
            // Заголовки дней недели
            const dayNames = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница'];
            for (let dayIndex = 0; dayIndex < 5; dayIndex++) {{
                const dayDate = new Date(period.startDate);
                dayDate.setDate(dayDate.getDate() + dayIndex);
                html += `<th>${{dayNames[dayIndex]}}<br><small>${{formatDisplayDate(dayDate)}}</small></th>`;
            }}
            
            html += `</tr></thead><tbody>`;
            
            // Строки с парами
            for (let pairNum = 1; pairNum <= 8; pairNum++) {{
                html += `<tr>
                    <td class="text-center fw-bold">${{pairNum}}</td>
                    <td class="text-center">
                        <small>${{PAIR_TIMES[pairNum].start}}<br>${{PAIR_TIMES[pairNum].end}}</small>
                    </td>`;
                
                for (let dayIndex = 0; dayIndex < 5; dayIndex++) {{
                    const schedule = scheduleGrid[dayIndex] && scheduleGrid[dayIndex][pairNum];
                    if (schedule) {{
                        html += `<td class="schedule-cell status-${{schedule.status}}">
                            <div class="discipline">${{schedule.discipline}}</div>
                            <div class="teacher">${{schedule.teacher ? schedule.teacher.name : '-'}}</div>
                            <div class="room">ауд. ${{schedule.room ? schedule.room.number : '-'}}</div>
                        </td>`;
                    }} else {{
                        html += `<td class="schedule-cell status-empty"></td>`;
                    }}
                }}
                
                html += `</tr>`;
                
                // Обеденный перерыв после 3 пары
                if (pairNum === 3) {{
                    html += `<tr class="table-secondary">
                        <td colspan="7" class="text-center py-1"><strong>ОБЕД</strong> 12:50 - 13:30</td>
                    </tr>`;
                }}
            }}
            
            html += `</tbody></table></div></div></div>`;
            
            document.getElementById('scheduleContent').innerHTML = html;
        }}
        
        // Отображение месячного расписания (упрощенная версия)
        function displayMonthSchedule(schedules, period) {{
            // Группируем по дням (только рабочие дни - пн-пт)
            const scheduleByDay = {{}};
            schedules.forEach(schedule => {{
                const date = schedule.date;
                const dayOfWeek = new Date(date).getDay();
                // Пропускаем выходные (0 - воскресенье, 6 - суббота)
                if (dayOfWeek === 0 || dayOfWeek === 6) return;
                if (!scheduleByDay[date]) scheduleByDay[date] = [];
                scheduleByDay[date].push(schedule);
            }});

            let html = `<div class="card"><div class="card-body">
                <h5 class="mb-3"><i class="bi bi-calendar-month"></i> ${{period.startDate.toLocaleDateString('ru-RU', {{month: 'long', year: 'numeric'}})}}</h5>
                <div class="row">`;

            // Простой список по дням
            const days = Object.keys(scheduleByDay).sort();
            days.forEach(date => {{
                const daySchedules = scheduleByDay[date];
                const displayDate = new Date(date).toLocaleDateString('ru-RU', {{weekday: 'short', day: '2-digit', month: '2-digit'}});

                html += `<div class="col-md-6 col-lg-4 mb-3">
                    <div class="card">
                        <div class="card-header">
                            <strong>${{displayDate}}</strong>
                        </div>
                        <div class="card-body p-2">`;

                daySchedules.forEach(schedule => {{
                    html += `<div class="small mb-1 p-1 rounded status-${{schedule.status}}">
                        ${{schedule.pair_number}}) ${{schedule.discipline.substring(0, 30)}}...
                        <div class="text-muted">${{schedule.teacher ? schedule.teacher.name : '-'}}</div>
                    </div>`;
                }});

                html += `</div></div></div>`;
            }});

            html += `</div></div></div>`;

            document.getElementById('scheduleContent').innerHTML = html;
        }}
        
        // Показать ошибку
        function showError(message) {{
            document.getElementById('scheduleContent').innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> ${{message}}
                </div>
            `;
            document.getElementById('loadingIndicator').style.display = 'none';
            document.getElementById('scheduleContent').style.display = 'block';
        }}
        
        // Обновление расписания
        function refreshSchedule() {{
            if (currentGroupId || currentTeacherId) {{
                loadSchedule();
            }}
        }}
        </script>
        """
        
    def __init__(self):
        self.base_styles = """
        <style>
            .schedule-container {
                max-width: 1200px;
                margin: 0 auto;
                font-family: 'Google Sans', Arial, sans-serif;
                padding: 20px;
            }
            
            .schedule-header {
                text-align: center;
                margin-bottom: 30px;
                background: linear-gradient(135deg, #4285f4, #34a853);
                color: white;
                padding: 20px;
                border-radius: 12px;
            }
            
            .course-tabs {
                display: flex;
                justify-content: center;
                margin-bottom: 20px;
                gap: 10px;
                flex-wrap: wrap;
            }
            
            .course-tab {
                padding: 12px 24px;
                background: #f8f9fa;
                border: 2px solid #e8eaed;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: 500;
            }
            
            .course-tab:hover {
                background: #e8f0fe;
                border-color: #4285f4;
            }
            
            .course-tab.active {
                background: #4285f4;
                color: white;
                border-color: #4285f4;
            }
            
            .course-content {
                display: none;
                animation: fadeIn 0.3s ease;
            }
            
            .course-content.active {
                display: block;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            .schedule-table {
                width: 100%;
                border-collapse: collapse;
                background: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                border-radius: 8px;
                overflow: hidden;
                margin-bottom: 30px;
            }
            
            .schedule-table th {
                background: linear-gradient(135deg, #4285f4, #1a73e8);
                color: white;
                padding: 15px 10px;
                text-align: center;
                font-weight: 500;
                font-size: 14px;
            }
            
            .schedule-table td {
                border: 1px solid #e8eaed;
                padding: 12px 8px;
                text-align: center;
                vertical-align: top;
                min-height: 60px;
                font-size: 12px;
            }
            
            .time-column {
                background-color: #f8f9fa;
                font-weight: bold;
                color: #5f6368;
                width: 80px;
            }
            
            .pair-number {
                background-color: #f1f3f4;
                font-weight: bold;
                color: #5f6368;
                width: 40px;
            }
            
            .lesson-cell {
                background: white;
                line-height: 1.4;
                min-width: 120px;
            }
            
            .lesson-cell.done {
                background: linear-gradient(135deg, #e8f5e8, #d4edda);
                border-left: 4px solid #34a853;
            }
            
            .lesson-cell.substitution {
                background: linear-gradient(135deg, #fff3cd, #ffeaa7);
                border-left: 4px solid #fbbc04;
            }
            
            .lesson-cell.completed {
                background: linear-gradient(135deg, #e2d5f1, #d1c4e9);
                border-left: 4px solid #9c27b0;
            }
            
            .discipline {
                font-weight: 600;
                color: #202124;
                margin-bottom: 2px;
                font-size: 11px;
            }
            
            .teacher {
                color: #5f6368;
                font-size: 10px;
                font-style: italic;
            }
            
            .group-header {
                background: linear-gradient(135deg, #34a853, #137333);
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            
            .classroom {
                background: #f8f9fa;
                color: #5f6368;
                font-size: 10px;
                font-style: italic;
            }
            
            .last-updated {
                text-align: center;
                color: #5f6368;
                font-size: 12px;
                margin-top: 20px;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 6px;
            }
            
            /* Мобильная адаптация */
            @media (max-width: 768px) {
                .schedule-container {
                    padding: 10px;
                }
                
                .schedule-table {
                    font-size: 10px;
                }
                
                .schedule-table th,
                .schedule-table td {
                    padding: 6px 4px;
                }
                
                .course-tabs {
                    flex-direction: column;
                    align-items: center;
                }
                
                .course-tab {
                    padding: 8px 16px;
                    font-size: 12px;
                }
                
                .discipline {
                    font-size: 9px;
                }
                
                .teacher {
                    font-size: 8px;
                }
            }
            
            @media (max-width: 480px) {
                .schedule-table th,
                .schedule-table td {
                    padding: 4px 2px;
                    font-size: 8px;
                }
                
                .lesson-cell {
                    min-width: 80px;
                }
            }
        </style>
        """
        
        self.base_script = """
        <script>
            function showCourse(courseNumber) {
                // Скрыть все курсы
                document.querySelectorAll('.course-content').forEach(content => {
                    content.classList.remove('active');
                });
                
                // Убрать активность с кнопок
                document.querySelectorAll('.course-tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                
                // Показать выбранный курс
                const courseContent = document.getElementById(`course-${courseNumber}`);
                if (courseContent) {
                    courseContent.classList.add('active');
                }
                
                // Активировать кнопку
                const activeTab = document.querySelector(`[onclick="showCourse(${courseNumber})"]`);
                if (activeTab) {
                    activeTab.classList.add('active');
                }
                
                // Сохранить выбор в localStorage
                localStorage.setItem('selectedCourse', courseNumber);
            }
            
            // Восстановить выбранный курс при загрузке
            document.addEventListener('DOMContentLoaded', function() {
                const savedCourse = localStorage.getItem('selectedCourse') || '3';
                showCourse(parseInt(savedCourse));
            });
            
            // Поиск по расписанию
            function searchSchedule() {
                const query = document.getElementById('search-input').value.toLowerCase();
                document.querySelectorAll('.lesson-cell').forEach(cell => {
                    const text = cell.textContent.toLowerCase();
                    if (query && text.includes(query)) {
                        cell.style.background = '#fff3cd';
                        cell.style.border = '2px solid #fbbc04';
                    } else {
                        cell.style.background = '';
                        cell.style.border = '';
                    }
                });
            }
        </script>
        """
    
    def generate_weekly_schedule(self, week_start: date, week_end: date) -> str:
        """Генерация HTML для недельного расписания"""
        
        # Получаем данные расписания
        from app.services.google_sheets_simple import SimpleGoogleSheetsSync
        sync_service = SimpleGoogleSheetsSync()
        weekly_data = sync_service._get_weekly_schedule_data(week_start, week_end)
        
        if not weekly_data:
            return self._generate_no_data_page()
        
        # Группируем по курсам
        courses_data = {}
        for group_data in weekly_data:
            course = group_data['course']
            if course not in courses_data:
                courses_data[course] = []
            
            # Преобразуем в формат schedule_grid
            converted_group = sync_service._convert_schedule_to_grid_format(group_data)
            courses_data[course].append(converted_group)
        
        # Генерируем HTML
        html_content = f"""
        <div class="schedule-container">
            {self._generate_header(week_start, week_end)}
            {self._generate_search_bar()}
            {self._generate_course_tabs(courses_data.keys())}
            {self._generate_course_content(courses_data, week_start, week_end)}
            {self._generate_footer()}
        </div>
        {self.base_styles}
        {self.base_script}
        """
        
        return html_content
    
    def _generate_header(self, week_start: date, week_end: date) -> str:
        """Генерация заголовка"""
        week_str = f"{week_start.strftime('%d.%m.%Y')} - {week_end.strftime('%d.%m.%Y')}"
        return f"""
        <div class="schedule-header">
            <h1>📅 Расписание АПЭК Петротехник</h1>
            <h2>{week_str}</h2>
            <p>Актуальное расписание занятий по всем курсам</p>
        </div>
        """
    
    def _generate_search_bar(self) -> str:
        """Генерация строки поиска"""
        return f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <input type="text" id="search-input" placeholder="🔍 Поиск по дисциплине или преподавателю..." 
                   style="padding: 10px 15px; width: 300px; border: 2px solid #e8eaed; border-radius: 25px; font-size: 14px;"
                   onkeyup="searchSchedule()">
        </div>
        """
    
    def _generate_course_tabs(self, courses: List[int]) -> str:
        """Генерация вкладок курсов"""
        tabs = []
        for course in sorted(courses):
            tabs.append(f"""
            <div class="course-tab" onclick="showCourse({course})">
                {course} курс
            </div>
            """)
        
        return f"""
        <div class="course-tabs">
            {' '.join(tabs)}
        </div>
        """
    
    def _generate_course_content(self, courses_data: Dict[int, List], week_start: date, week_end: date) -> str:
        """Генерация контента для каждого курса"""
        content_blocks = []
        
        for course in sorted(courses_data.keys()):
            groups = courses_data[course]
            table_html = self._generate_course_table(groups, course, week_start, week_end)
            
            content_blocks.append(f"""
            <div id="course-{course}" class="course-content">
                <h3 style="text-align: center; color: #4285f4; margin-bottom: 20px;">
                    {course} курс ({len(groups)} групп)
                </h3>
                {table_html}
            </div>
            """)
        
        return '\n'.join(content_blocks)
    
    def _generate_course_table(self, groups: List[Dict], course: int, week_start: date, week_end: date) -> str:
        """Генерация таблицы для курса"""
        
        # Дни недели
        weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница']
        
        # Пары
        pairs = list(range(1, 9))  # 1-8 пары
        
        # Заголовок таблицы
        header_html = """
        <table class="schedule-table table table-bordered table-responsive">
            <thead>
                <tr>
                    <th rowspan="2" class="time-column">Время</th>
                    <th rowspan="2" class="pair-number">№</th>
        """
        
        # Заголовки групп
        for group in groups:
            header_html += f'<th class="group-header">{group["group_name"]}</th>'
        
        header_html += "</tr><tr>"
        
        # Аудитории под названиями групп
        for group in groups:
            classroom = group.get('main_classroom', '')
            header_html += f'<th class="classroom">ауд. {classroom}</th>'
        
        header_html += "</tr></thead><tbody>"
        
        # Тело таблицы
        body_html = ""
        
        for day in weekdays:
            # Определяем количество строк для этого дня
            day_pairs = len(pairs)
            
            for pair_idx, pair_num in enumerate(pairs):
                row_html = "<tr>"
                
                # Время и номер пары (только в первой строке дня)
                if pair_idx == 0:
                    # День недели и время первой пары
                    pair_time = self._get_pair_time(pair_num)
                    row_html += f"""
                    <td rowspan="{day_pairs}" class="time-column">
                        <strong>{day}</strong><br>
                        <small>{pair_time}</small>
                    </td>
                    """
                
                # Номер пары
                pair_time = self._get_pair_time(pair_num)
                roman = self._get_roman_numeral(pair_num)
                row_html += f"""
                <td class="pair-number">
                    <strong>{roman}</strong><br>
                    <small>{pair_time}</small>
                </td>
                """
                
                # Ячейки групп
                for group in groups:
                    cell_content = self._get_lesson_cell_content(group, day, pair_num)
                    row_html += cell_content
                
                row_html += "</tr>"
                body_html += row_html
        
        return header_html + body_html + "</tbody></table>"
    
    def _get_lesson_cell_content(self, group: Dict, day: str, pair_num: int) -> str:
        """Получение содержимого ячейки урока"""
        schedule_grid = group.get('schedule_grid', {})
        day_schedule = schedule_grid.get(day, {})
        pair_data = day_schedule.get(pair_num)
        
        if not pair_data:
            return '<td class="lesson-cell"></td>'
        
        discipline = pair_data.get('discipline', '')
        teacher = pair_data.get('teacher', '')
        status = pair_data.get('status', 'planned')
        classroom = pair_data.get('classroom', '')
        
        # Определяем CSS класс по статусу
        css_class = f"lesson-cell {status}"
        
        # Формируем содержимое
        content_parts = []
        if discipline:
            content_parts.append(f'<div class="discipline">{discipline}</div>')
        if teacher:
            content_parts.append(f'<div class="teacher">{teacher}</div>')
        if classroom:
            content_parts.append(f'<div class="teacher">ауд. {classroom}</div>')
        
        content = ''.join(content_parts)
        
        return f'<td class="{css_class}">{content}</td>'
    
    def _get_pair_time(self, pair_number: int) -> str:
        """Получение времени пары"""
        from flask import current_app
        pair_times = current_app.config.get('PAIR_TIMES', {})
        pair_info = pair_times.get(pair_number, {})
        
        if pair_info:
            return f"{pair_info['start']}-{pair_info['end']}"
        else:
            # Fallback времена
            times = {
                1: "08:30-09:50", 2: "10:00-11:20", 3: "11:30-12:50", 4: "13:30-14:50",
                5: "15:00-16:20", 6: "16:30-17:50", 7: "18:00-19:20", 8: "19:30-20:50"
            }
            return times.get(pair_number, f"Пара {pair_number}")
    
    def _get_roman_numeral(self, number: int) -> str:
        """Преобразование числа в римскую цифру"""
        roman_numerals = {
            1: 'I', 2: 'II', 3: 'III', 4: 'IV',
            5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII'
        }
        return roman_numerals.get(number, str(number))
    
    def _generate_footer(self) -> str:
        """Генерация подвала"""
        now = datetime.now()
        return f"""
        <div class="last-updated">
            📅 Последнее обновление: {now.strftime('%d.%m.%Y в %H:%M')} <br>
            🏫 АПЭК Петротехник - Расписание занятий <br>
            💡 Обновляется автоматически при изменении расписания
        </div>
        """
    
    def _generate_no_data_page(self) -> str:
        """Генерация страницы при отсутствии данных"""
        return f"""
        <div class="schedule-container">
            <div class="schedule-header">
                <h1>📅 Расписание АПЭК Петротехник</h1>
                <h2>Нет данных</h2>
                <p>Расписание временно недоступно</p>
            </div>
            <div style="text-align: center; padding: 50px; background: #f8f9fa; border-radius: 8px;">
                <h3>⚠️ Данные не найдены</h3>
                <p>Расписание находится в процессе обновления.<br>
                Попробуйте обновить страницу через несколько минут.</p>
            </div>
            {self._generate_footer()}
        </div>
        {self.base_styles}
        """


class GoogleSitesService:
    """Сервис для работы с Google Sites"""
    
    def __init__(self):
        self.html_generator = GoogleSitesHTMLGenerator()
        self.enabled = current_app.config.get('GOOGLE_SITES_ENABLED', False)
    
    def generate_current_week_html(self) -> str:
        """Генерация HTML для текущей недели"""
        from datetime import date, timedelta
        
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)
        
        return self.html_generator.generate_weekly_schedule(monday, friday)
    
    def generate_static_html(self, period_start: date, period_end: date,
                           group_id: Optional[int] = None, 
                           teacher_id: Optional[int] = None,
                           view_type: str = 'week') -> Dict:
        """Генерация статического HTML с встроенными данными"""
        try:
            from app.models import Schedule, Group, Teacher, Workload, Room
            from app import db
            
            # Получаем все необходимые данные
            groups = Group.query.order_by(Group.name).all()
            teachers = Teacher.query.order_by(Teacher.full_name).all()
            
            # Определяем расширенный период для данных (±2 месяца)
            extended_start = period_start - timedelta(days=60)
            extended_end = period_end + timedelta(days=60)
            
            # Базовый запрос расписания для расширенного периода
            query = db.session.query(Schedule)\
                .join(Workload, Schedule.workload_id == Workload.id)\
                .join(Group, Workload.group_id == Group.id)\
                .outerjoin(Teacher, Workload.teacher_id == Teacher.id)\
                .outerjoin(Room, Schedule.room_id == Room.id)\
                .filter(Schedule.date >= extended_start, Schedule.date <= extended_end)
            
            # УБИРАЕМ ФИЛЬТРЫ - получаем расписание ВСЕХ групп
            # Комментируем фильтры для полной генерации всех групп
            # if group_id:
            #     query = query.filter(Workload.group_id == group_id)
            # elif teacher_id:
            #     query = query.filter(Workload.teacher_id == teacher_id)
            
            schedules = query.order_by(Schedule.date, Schedule.pair_number).all()
            
            # Подготавливаем данные для встраивания с меткой времени генерации
            generated_at = datetime.now().isoformat()
            groups_data = {
                'generated_at': generated_at,
                'groups': [{'id': g.id, 'name': g.name} for g in groups]
            }
            teachers_data = {
                'generated_at': generated_at,
                'teachers': [{'id': t.id, 'name': t.full_name} for t in teachers]
            }
            schedule_data = {
                'generated_at': generated_at,
                'schedules': []
            }
            for schedule in schedules:
                # Пропускаем выходные дни (суббота=5, воскресенье=6)
                if schedule.date.weekday() >= 5:
                    continue

                schedule_data['schedules'].append({
                    'id': schedule.id,
                    'date': schedule.date.isoformat(),
                    'pair_number': schedule.pair_number,
                    'status': schedule.status,
                    'discipline': schedule.workload.discipline,
                    'group': {
                        'id': schedule.workload.group.id,
                        'name': schedule.workload.group.name
                    },
                    'teacher': {
                        'id': schedule.workload.teacher.id,
                        'name': schedule.workload.teacher.full_name
                    } if schedule.workload.teacher else None,
                    'substitute_teacher': {
                        'id': schedule.substitute_teacher.id,
                        'name': schedule.substitute_teacher.full_name
                    } if schedule.substitute_teacher else None,
                    'room': {
                        'id': schedule.room.id,
                        'number': schedule.room.number
                    } if schedule.room else None,
                    'notes': schedule.notes,
                    'change_reason': schedule.change_reason
                })

            # Формируем описание для заголовка (ВСЕ ГРУППЫ)
            title_parts = ["Все группы АПЭК Петротехник"]
            
            if view_type == 'week':
                title_parts.append(f"Неделя {period_start.strftime('%d.%m')} - {period_end.strftime('%d.%m.%Y')}")
            elif view_type == 'month':
                title_parts.append(f"{period_start.strftime('%B %Y')}")
            else:
                title_parts.append(f"{period_start.year} год")
            
            title = " | ".join(title_parts)
            
            # Генерируем статическую HTML страницу
            html_content = self.html_generator.generate_static_schedule_page(
                groups_data, teachers_data, schedule_data, 
                group_id, teacher_id, view_type, 
                {'start': period_start, 'end': period_end}
            )
            
            # Сохраняем файл (ВСЕ ГРУППЫ)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Удаляем фильтры суффиксы, так как генерируем для всех групп
            # filter_suffix = ''
            # if group_id:
            #     group = Group.query.get(group_id)
            #     if group:
            #         filter_suffix = f'_group_{group_id}'
            # elif teacher_id:
            #     teacher = Teacher.query.get(teacher_id)
            #     if teacher:
            #         filter_suffix = f'_teacher_{teacher_id}'
            
            filename = f'schedule_{view_type}_{timestamp}_all_groups.html'
            file_path = f'exports/{filename}'
            
            # Создаем директорию если не существует
            import os
            os.makedirs('exports', exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return {
                'success': True,
                'message': f'Статический HTML сгенерирован ({title})',
                'file_path': file_path,
                'filename': filename,
                'preview_available': True,
                'schedules_count': len(schedule_data['schedules']),
                'static_mode': True
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка генерации статического HTML: {str(e)}'
            }
    
    def generate_json_data(self, period_start: date, period_end: date) -> Dict:
        """Генерация JSON файлов для загрузки с Google Drive"""
        try:
            from app.models import Schedule, Group, Teacher, Workload, Room
            from app import db
            
            # Получаем все необходимые данные
            groups = Group.query.order_by(Group.name).all()
            teachers = Teacher.query.order_by(Teacher.full_name).all()
            
            # Определяем расширенный период для данных (±2 месяца)
            extended_start = period_start - timedelta(days=60)
            extended_end = period_end + timedelta(days=60)
            
            # Базовый запрос расписания для расширенного периода (ВСЕ ГРУППЫ)
            query = db.session.query(Schedule)\
                .join(Workload, Schedule.workload_id == Workload.id)\
                .join(Group, Workload.group_id == Group.id)\
                .outerjoin(Teacher, Workload.teacher_id == Teacher.id)\
                .outerjoin(Room, Schedule.room_id == Room.id)\
                .filter(Schedule.date >= extended_start, Schedule.date <= extended_end)
            
            schedules = query.order_by(Schedule.date, Schedule.pair_number).all()
            
            # Подготавливаем данные для JSON с меткой времени генерации
            generated_at = datetime.now().isoformat()
            groups_data = {
                'generated_at': generated_at,
                'groups': [{'id': g.id, 'name': g.name} for g in groups]
            }
            teachers_data = {
                'generated_at': generated_at,
                'teachers': [{'id': t.id, 'name': t.full_name} for t in teachers]
            }
            schedule_data = {
                'generated_at': generated_at,
                'schedules': []
            }
            for schedule in schedules:
                # Пропускаем выходные дни (суббота=5, воскресенье=6)
                if schedule.date.weekday() >= 5:
                    continue

                schedule_data['schedules'].append({
                    'id': schedule.id,
                    'date': schedule.date.isoformat(),
                    'pair_number': schedule.pair_number,
                    'status': schedule.status,
                    'discipline': schedule.workload.discipline,
                    'group': {
                        'id': schedule.workload.group.id,
                        'name': schedule.workload.group.name
                    },
                    'teacher': {
                        'id': schedule.workload.teacher.id,
                        'name': schedule.workload.teacher.full_name
                    } if schedule.workload.teacher else None,
                    'substitute_teacher': {
                        'id': schedule.substitute_teacher.id,
                        'name': schedule.substitute_teacher.full_name
                    } if schedule.substitute_teacher else None,
                    'room': {
                        'id': schedule.room.id,
                        'number': schedule.room.number
                    } if schedule.room else None,
                    'notes': schedule.notes,
                    'change_reason': schedule.change_reason
                })

            # Сохраняем отдельные JSON файлы
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Создаем директорию если не существует
            import os
            import json
            os.makedirs('exports/json', exist_ok=True)
            
            # Сохраняем группы
            groups_file = f'exports/json/groups_{timestamp}.json'
            with open(groups_file, 'w', encoding='utf-8') as f:
                json.dump(groups_data, f, ensure_ascii=False, indent=2)
            
            # Сохраняем преподавателей
            teachers_file = f'exports/json/teachers_{timestamp}.json'
            with open(teachers_file, 'w', encoding='utf-8') as f:
                json.dump(teachers_data, f, ensure_ascii=False, indent=2)
            
            # Сохраняем расписание
            schedule_file = f'exports/json/schedule_{timestamp}.json'
            with open(schedule_file, 'w', encoding='utf-8') as f:
                json.dump(schedule_data, f, ensure_ascii=False, indent=2)
            
            return {
                'success': True,
                'message': f'JSON файлы сгенерированы для Google Drive',
                'files': {
                    'groups': groups_file,
                    'teachers': teachers_file,
                    'schedule': schedule_file
                },
                'period': {
                    'start': period_start.isoformat(),
                    'end': period_end.isoformat(),
                    'type': 'extended'
                },
                'schedules_count': len(schedule_data['schedules']),
                'groups_count': len(groups_data['groups']),
                'teachers_count': len(teachers_data['teachers'])
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка при генерации JSON файлов: {str(e)}'
            }
    
    def generate_drive_html_template(self, groups_drive_url: str = '', teachers_drive_url: str = '', schedule_drive_url: str = '') -> Dict:
        """Генерация легкого HTML шаблона для Google Drive"""
        try:
            # Легкий HTML шаблон без встроенных данных
            html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>APEC Petrotechnic College - Schedule</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
    
    <style>
    :root {{
        --sidebar-width: 0px;
    }}
    
    .schedule-cell {{
        min-height: 80px;
        font-size: 0.85rem;
        vertical-align: top;
        padding: 0.5rem !important;
    }}
    .schedule-cell .discipline {{
        font-weight: 600;
        margin-bottom: 0.25rem;
    }}
    .schedule-cell .teacher {{
        color: #666;
        font-size: 0.8rem;
    }}
    .schedule-cell .room {{
        color: #999;
        font-size: 0.75rem;
    }}
    
    /* Статусы занятий */
    .status-planned {{ background-color: #fff !important; border: 2px solid #6c757d !important; }}
    .status-done {{ background-color: #d4edda !important; border: 2px solid #28a745 !important; }}
    .status-substitution {{ background-color: #fff3cd !important; border: 2px solid #ffc107 !important; }}
    .status-cancelled {{ background-color: #f8d7da !important; border: 2px solid #dc3545 !important; text-decoration: line-through !important; opacity: 0.7 !important; }}
    .status-completed {{ background-color: #e2d5f1 !important; border: 2px solid #6f42c1 !important; }}
    .status-rescheduled {{ background-color: #d1ecf1 !important; border: 2px solid #17a2b8 !important; }}
    .status-empty {{ background-color: #f8f9fa !important; }}
    
    /* Адаптивность */
    @media (max-width: 768px) {{
        .schedule-cell {{
            min-height: 60px;
            font-size: 0.7rem;
            padding: 0.3rem !important;
        }}
        .schedule-cell .teacher,
        .schedule-cell .room {{
            font-size: 0.6rem;
        }}
    }}
    
    .loading-indicator {{
        display: none;
        text-align: center;
        padding: 2rem;
    }}
    
    .error-message {{
        display: none;
    }}
    </style>
</head>
<body>
    <div class="container-fluid p-3">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h2><i class="bi bi-calendar3"></i> APEC Petrotechnic College Schedule</h2>
                <p class="text-muted mb-0">Данные загружаются с Google Drive <span id="lastUpdate"></span></p>
            </div>
            <div class="btn-group">
                <button class="btn btn-outline-primary btn-sm" onclick="refreshData()">
                    <i class="bi bi-arrow-clockwise"></i> Обновить
                </button>
            </div>
        </div>

        <!-- Индикатор загрузки -->
        <div id="loadingIndicator" class="loading-indicator">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Загрузка...</span>
            </div>
            <p class="mt-2">Загружаем актуальные данные расписания...</p>
        </div>

        <!-- Сообщение об ошибке -->
        <div id="errorMessage" class="alert alert-warning error-message">
            <h5><i class="bi bi-exclamation-triangle"></i> Ошибка загрузки данных</h5>
            <p>Не удалось загрузить актуальные данные с Google Drive. Проверьте подключение к интернету.</p>
            <button class="btn btn-outline-warning" onclick="refreshData()">Попробовать еще раз</button>
        </div>

        <!-- Фильтры -->
        <div class="card mb-4" id="filtersCard" style="display: none;">
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-4">
                        <label class="form-label">Группа</label>
                        <select id="groupSelect" class="form-select" onchange="updateSchedule()">
                            <option value="">-- Выберите группу --</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Преподаватель</label>
                        <select id="teacherSelect" class="form-select" onchange="updateSchedule()">
                            <option value="">-- Или преподавателя --</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Период</label>
                        <div class="btn-group w-100" role="group">
                            <input type="radio" class="btn-check" name="view" id="view_week" value="week" checked onchange="updateSchedule()">
                            <label class="btn btn-outline-primary" for="view_week">Неделя</label>
                            
                            <input type="radio" class="btn-check" name="view" id="view_month" value="month" onchange="updateSchedule()">
                            <label class="btn btn-outline-primary" for="view_month">Месяц</label>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Навигация -->
        <div id="navigationCard" class="d-flex justify-content-between align-items-center mb-3" style="display: none;">
            <button class="btn btn-outline-primary" onclick="navigateWeek(-1)">
                <i class="bi bi-chevron-left"></i> Пред. неделя
            </button>
            <h5 class="mb-0" id="currentPeriod"></h5>
            <button class="btn btn-outline-primary" onclick="navigateWeek(1)">
                След. неделя <i class="bi bi-chevron-right"></i>
            </button>
        </div>

        <!-- Контент расписания -->
        <div id="scheduleContent"></div>
    </div>

<script>
// Конфигурация URL для JSON файлов Google Drive
const DRIVE_CONFIG = {{
    groups_url: '{groups_drive_url}',
    teachers_url: '{teachers_drive_url}',
    schedule_url: '{schedule_drive_url}'
}};

// Глобальные переменные
let STATIC_GROUPS = null;
let STATIC_TEACHERS = null;
let STATIC_SCHEDULE = null;

// Настройки отображения
let currentGroupId = null;
let currentTeacherId = null;
let currentView = 'week';
let currentWeekOffset = 0;

// Время последнего обновления
let lastUpdateTime = null;

// Инициализация
document.addEventListener('DOMContentLoaded', function() {{
    loadDataFromDrive();
}});

// Загрузка данных с Google Drive
async function loadDataFromDrive() {{
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorMessage = document.getElementById('errorMessage');
    const filtersCard = document.getElementById('filtersCard');
    const navigationCard = document.getElementById('navigationCard');
    
    loadingIndicator.style.display = 'block';
    errorMessage.style.display = 'none';
    filtersCard.style.display = 'none';
    navigationCard.style.display = 'none';
    
    try {{
        console.log('Загружаем данные с Google Drive...');
        
        // Загружаем все JSON файлы параллельно
        const [groupsResponse, teachersResponse, scheduleResponse] = await Promise.all([
            fetch(DRIVE_CONFIG.groups_url).catch(e => {{ throw new Error('Группы: ' + e.message) }}),
            fetch(DRIVE_CONFIG.teachers_url).catch(e => {{ throw new Error('Преподаватели: ' + e.message) }}),
            fetch(DRIVE_CONFIG.schedule_url).catch(e => {{ throw new Error('Расписание: ' + e.message) }})
        ]);
        
        if (!groupsResponse.ok) throw new Error('Ошибка загрузки групп');
        if (!teachersResponse.ok) throw new Error('Ошибка загрузки преподавателей');
        if (!scheduleResponse.ok) throw new Error('Ошибка загрузки расписания');
        
        STATIC_GROUPS = await groupsResponse.json();
        STATIC_TEACHERS = await teachersResponse.json();
        STATIC_SCHEDULE = await scheduleResponse.json();
        
        console.log('Данные загружены:', {{
            groups: STATIC_GROUPS.groups.length,
            teachers: STATIC_TEACHERS.teachers.length,
            schedules: STATIC_SCHEDULE.schedules.length
        }});
        
        lastUpdateTime = new Date();
        updateLastUpdateDisplay();
        
        // Инициализируем интерфейс
        initializeInterface();
        
        loadingIndicator.style.display = 'none';
        filtersCard.style.display = 'block';
        navigationCard.style.display = 'flex';
        
    }} catch (error) {{
        console.error('Ошибка загрузки:', error);
        loadingIndicator.style.display = 'none';
        errorMessage.style.display = 'block';
        
        // Попробуем использовать fallback данные если есть
        if (typeof FALLBACK_DATA !== 'undefined') {{
            console.log('Используем резервные данные');
            STATIC_GROUPS = FALLBACK_DATA.groups;
            STATIC_TEACHERS = FALLBACK_DATA.teachers;
            STATIC_SCHEDULE = FALLBACK_DATA.schedule;
            initializeInterface();
            filtersCard.style.display = 'block';
            navigationCard.style.display = 'flex';
        }}
    }}
}}

// Обновление времени последнего обновления
function updateLastUpdateDisplay() {{
    const lastUpdateElement = document.getElementById('lastUpdate');
    if (lastUpdateTime) {{
        lastUpdateElement.textContent = '(обновлено ' + lastUpdateTime.toLocaleTimeString() + ')';
    }}
}}

// Обновление данных
function refreshData() {{
    loadDataFromDrive();
}}

// Инициализация интерфейса
function initializeInterface() {{
    populateDropdowns();
    updateSchedule();
}}

// Заполнение выпадающих списков
function populateDropdowns() {{
    const groupSelect = document.getElementById('groupSelect');
    const teacherSelect = document.getElementById('teacherSelect');
    
    // Очищаем списки
    groupSelect.innerHTML = '<option value="">-- Выберите группу --</option>';
    teacherSelect.innerHTML = '<option value="">-- Или преподавателя --</option>';
    
    // Заполняем группы
    if (STATIC_GROUPS && STATIC_GROUPS.groups) {{
        STATIC_GROUPS.groups.forEach(group => {{
            const option = document.createElement('option');
            option.value = group.id;
            option.textContent = group.name;
            groupSelect.appendChild(option);
        }});
    }}
    
    // Заполняем преподавателей
    if (STATIC_TEACHERS && STATIC_TEACHERS.teachers) {{
        STATIC_TEACHERS.teachers.forEach(teacher => {{
            const option = document.createElement('option');
            option.value = teacher.id;
            option.textContent = teacher.name;
            teacherSelect.appendChild(option);
        }});
    }}
}}

// Обновление расписания
function updateSchedule() {{
    const groupSelect = document.getElementById('groupSelect');
    const teacherSelect = document.getElementById('teacherSelect');
    const viewRadios = document.querySelectorAll('input[name="view"]');
    
    // Получаем текущие значения
    currentGroupId = groupSelect.value ? parseInt(groupSelect.value) : null;
    currentTeacherId = teacherSelect.value ? parseInt(teacherSelect.value) : null;
    
    viewRadios.forEach(radio => {{
        if (radio.checked) currentView = radio.value;
    }});
    
    // Сбрасываем противоположный фильтр
    if (currentGroupId) {{
        teacherSelect.value = '';
        currentTeacherId = null;
    }} else if (currentTeacherId) {{
        groupSelect.value = '';
        currentGroupId = null;
    }}
    
    updateNavigationLabels();
    loadSchedule();
}}

// Навигация по неделям
function navigateWeek(direction) {{
    currentWeekOffset += direction;
    updateNavigationLabels();
    loadSchedule();
}}

// Обновление лейблов навигации
function updateNavigationLabels() {{
    const currentPeriodElement = document.getElementById('currentPeriod');
    const today = new Date();
    const currentMonday = new Date(today);
    currentMonday.setDate(today.getDate() - today.getDay() + 1);
    
    const targetMonday = new Date(currentMonday);
    targetMonday.setDate(currentMonday.getDate() + (currentWeekOffset * 7));
    
    const targetSunday = new Date(targetMonday);
    targetSunday.setDate(targetMonday.getDate() + 6);
    
    currentPeriodElement.innerHTML = `
        Неделя ${{targetMonday.toLocaleDateString('ru-RU', {{day: '2-digit', month: '2-digit'}})}} - 
        ${{targetSunday.toLocaleDateString('ru-RU', {{day: '2-digit', month: '2-digit', year: 'numeric'}})}}
    `;
}}

// Загрузка и отображение расписания
function loadSchedule() {{
    if (!STATIC_SCHEDULE || !STATIC_SCHEDULE.schedules) {{
        document.getElementById('scheduleContent').innerHTML = 
            '<div class="alert alert-info">Данные расписания не загружены</div>';
        return;
    }}
    
    // Фильтруем расписание
    let filteredSchedules = STATIC_SCHEDULE.schedules;
    
    if (currentGroupId) {{
        filteredSchedules = filteredSchedules.filter(s => s.group.id === currentGroupId);
    }}
    
    if (currentTeacherId) {{
        // Фильтруем по основному преподавателю ИЛИ по заменяющему
        filteredSchedules = filteredSchedules.filter(s =>
            (s.teacher && s.teacher.id === currentTeacherId) ||
            (s.substitute_teacher && s.substitute_teacher.id === currentTeacherId)
        );
    }}
    
    // Фильтруем по текущей неделе
    const today = new Date();
    const currentMonday = new Date(today);
    currentMonday.setDate(today.getDate() - today.getDay() + 1);
    
    const targetMonday = new Date(currentMonday);
    targetMonday.setDate(currentMonday.getDate() + (currentWeekOffset * 7));
    
    const targetSunday = new Date(targetMonday);
    targetSunday.setDate(targetMonday.getDate() + 6);
    
    const weekSchedules = filteredSchedules.filter(s => {{
        const scheduleDate = new Date(s.date);
        return scheduleDate >= targetMonday && scheduleDate <= targetSunday;
    }});
    
    displayWeekSchedule(weekSchedules, targetMonday, targetSunday);
}}

// Отображение недельного расписания
function displayWeekSchedule(schedules, startDate, endDate) {{
    // Создаем сетку расписания
    const scheduleGrid = {{}};
    
    schedules.forEach(schedule => {{
        const scheduleDate = new Date(schedule.date);
        const dayOfWeek = scheduleDate.getDay();
        const dayIndex = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Понедельник = 0
        
        if (!scheduleGrid[dayIndex]) {{
            scheduleGrid[dayIndex] = {{}};
        }}
        
        if (!scheduleGrid[dayIndex][schedule.pair_number]) {{
            scheduleGrid[dayIndex][schedule.pair_number] = [];
        }}
        
        scheduleGrid[dayIndex][schedule.pair_number].push(schedule);
    }});
    
    const PAIR_TIMES = {{
        1: {{start: '08:00', end: '09:30'}},
        2: {{start: '09:40', end: '11:10'}},
        3: {{start: '11:20', end: '12:50'}},
        4: {{start: '13:30', end: '15:00'}},
        5: {{start: '15:10', end: '16:40'}},
        6: {{start: '16:50', end: '18:20'}},
        7: {{start: '18:30', end: '20:00'}},
        8: {{start: '20:10', end: '21:40'}}
    }};
    
    const WEEK_DAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница'];
    
    let html = `
        <div class="card">
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-bordered">
                        <thead class="table-light">
                            <tr>
                                <th style="width: 80px;">Пара</th>
                                <th style="width: 100px;">Время</th>`;
    
    WEEK_DAYS.forEach((day, index) => {{
        const currentDate = new Date(startDate);
        currentDate.setDate(startDate.getDate() + index);
        html += `<th class="text-center">
            ${{day}}<br>
            <small class="text-muted">${{currentDate.toLocaleDateString('ru-RU', {{day: '2-digit', month: '2-digit'}})}}</small>
        </th>`;
    }});
    
    html += `</tr></thead><tbody>`;
    
    for (let pairNum = 1; pairNum <= 8; pairNum++) {{
        html += `<tr>
            <td class="text-center fw-bold">${{pairNum}}</td>
            <td class="text-center">
                <small>${{PAIR_TIMES[pairNum].start}}<br>${{PAIR_TIMES[pairNum].end}}</small>
            </td>`;
        
        for (let dayIndex = 0; dayIndex < 5; dayIndex++) {{
            const daySchedules = scheduleGrid[dayIndex] && scheduleGrid[dayIndex][pairNum];
            if (daySchedules && daySchedules.length > 0) {{
                const schedule = daySchedules[0]; // Берем первое занятие
                html += `<td class="schedule-cell status-${{schedule.status}}">
                    <div class="discipline">${{schedule.discipline}}</div>
                    <div class="teacher">${{schedule.teacher ? schedule.teacher.name : '-'}}</div>
                    <div class="room">ауд. ${{schedule.room ? schedule.room.number : '-'}}</div>
                </td>`;
            }} else {{
                html += `<td class="schedule-cell status-empty"></td>`;
            }}
        }}
        
        html += `</tr>`;
        
        // Обеденный перерыв после 3 пары
        if (pairNum === 3) {{
            html += `<tr class="table-secondary">
                <td colspan="7" class="text-center py-1"><strong>ОБЕД</strong> 12:50 - 13:30</td>
            </tr>`;
        }}
    }}
    
    html += `</tbody></table></div></div></div>`;
    
    document.getElementById('scheduleContent').innerHTML = html;
}}

// Показать сообщение о выборе
function showNoSelectionMessage() {{
    document.getElementById('scheduleContent').innerHTML = `
        <div class="alert alert-info text-center">
            <h5><i class="bi bi-info-circle"></i> Выберите группу или преподавателя</h5>
            <p class="mb-0">Для просмотра расписания выберите группу или преподавателя из списков выше</p>
        </div>
    `;
}}
</script>
</body>
</html>"""

            # Определяем путь сохранения в зависимости от типа шаблона
            import os
            
            # Проверяем, это GitHub шаблон или Google Drive шаблон
            is_github_template = ('github.io' in groups_drive_url or 
                                'github.io' in teachers_drive_url or 
                                'github.io' in schedule_drive_url)
            
            if is_github_template:
                # GitHub шаблон - фиксированное имя файла в специальной папке
                filename = 'index.html'
                file_path = 'exports/github_pages/index.html'
                os.makedirs('exports/github_pages', exist_ok=True)
                template_type = 'github_pages'
            else:
                # Google Drive шаблон - уникальное имя с timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'schedule_drive_template_{timestamp}.html'
                file_path = f'exports/{filename}'
                os.makedirs('exports', exist_ok=True)
                template_type = 'google_drive'
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Формируем сообщение в зависимости от типа шаблона
            if is_github_template:
                message = f'HTML шаблон для GitHub Pages создан в папке github_pages'
            else:
                message = f'HTML шаблон для Google Drive создан'
            
            return {
                'success': True,
                'message': message,
                'file_path': file_path,
                'filename': filename,
                'template_type': template_type,
                'drive_config': {
                    'groups_url': groups_drive_url,
                    'teachers_url': teachers_drive_url, 
                    'schedule_url': schedule_drive_url
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка при генерации Drive HTML шаблона: {str(e)}'
            }

    def generate_github_pages_package(self, period_start: date, period_end: date) -> Dict:
        """Генерация пакета для GitHub Pages (JSON + HTML + README)"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            github_dir = os.path.join('exports', 'github_pages')
            docs_dir = os.path.join(github_dir, 'docs')
            os.makedirs(docs_dir, exist_ok=True)
            
            # Создаем API директорию в docs
            api_dir = os.path.join(docs_dir, 'api')
            os.makedirs(api_dir, exist_ok=True)
            
            # Генерируем JSON файлы для API
            json_result = self.generate_json_data(period_start, period_end)
            if not json_result['success']:
                return json_result
            
            # Копируем JSON файлы в API директорию
            import shutil
            for file_type, file_path in json_result['files'].items():
                src_path = file_path  # file_path уже содержит полный путь
                dst_path = os.path.join(api_dir, f'{file_type}.json')
                shutil.copy2(src_path, dst_path)
            
            # GitHub Pages URLs для вашего репозитория
            github_repo = "Azamat313/apec_schedule"
            base_url = f"https://{github_repo.split('/')[0]}.github.io/{github_repo.split('/')[1]}"
            
            github_config = {
                'groups_url': f'{base_url}/api/groups.json',
                'teachers_url': f'{base_url}/api/teachers.json',
                'schedule_url': f'{base_url}/api/schedule.json'
            }
            
            # Используем полный HTML шаблон для GitHub Pages
            html_template = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>APEC Petrotechnic College - Schedule</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
    
    <style>
    :root {{
        --sidebar-width: 0px;
    }}
    
    /* Основные стили для iframe в Google Sites */
    body {{
        margin: 0 !important;
        padding: 0 !important;
        box-sizing: border-box;
        width: 100% !important;
        overflow-x: auto;
    }}
    
    .container-fluid {{
        padding: 0.75rem !important;
        max-width: 100% !important;
        margin: 0 !important;
    }}
    
    /* Стили расписания */
    .schedule-cell {{
        min-height: 80px;
        font-size: 0.85rem;
        vertical-align: top;
        padding: 0.5rem !important;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }}
    .schedule-cell .discipline {{
        font-weight: 600;
        margin-bottom: 0.25rem;
        line-height: 1.2;
    }}
    .schedule-cell .teacher {{
        color: #666;
        font-size: 0.8rem;
        line-height: 1.1;
    }}
    .schedule-cell .room {{
        color: #999;
        font-size: 0.75rem;
        line-height: 1.1;
    }}
    
    /* Статусы занятий */
    .status-planned {{ background-color: #fff !important; border: 2px solid #6c757d !important; }}
    .status-done {{ background-color: #d4edda !important; border: 2px solid #28a745 !important; }}
    .status-substitution {{ background-color: #fff3cd !important; border: 2px solid #ffc107 !important; }}
    .status-cancelled {{ background-color: #f8d7da !important; border: 2px solid #dc3545 !important; text-decoration: line-through !important; opacity: 0.7 !important; }}
    .status-completed {{ background-color: #e2d5f1 !important; border: 2px solid #6f42c1 !important; }}
    .status-rescheduled {{ background-color: #d1ecf1 !important; border: 2px solid #17a2b8 !important; }}
    .status-empty {{ background-color: #f8f9fa !important; }}
    
    /* Таблица расписания */
    .table-responsive {{
        border-radius: 8px;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
    }}
    
    .table {{
        margin-bottom: 0 !important;
        min-width: 800px;
    }}
    
    /* Улучшенная мобильная адаптация */
    @media (max-width: 768px) {{
        .container-fluid {{
            padding: 0.5rem !important;
        }}
        
        h2 {{
            font-size: 1.25rem !important;
            margin-bottom: 0.5rem !important;
        }}
        
        .d-flex.justify-content-between {{
            flex-direction: column !important;
            gap: 0.5rem;
        }}
        
        .btn-group {{
            align-self: flex-start;
        }}
        
        .schedule-cell {{
            min-height: 50px !important;
            font-size: 0.7rem !important;
            padding: 0.25rem !important;
        }}
        
        .schedule-cell .discipline {{
            font-size: 0.7rem !important;
            margin-bottom: 0.1rem !important;
        }}
        
        .schedule-cell .teacher,
        .schedule-cell .room {{
            font-size: 0.6rem !important;
        }}
        
        .table th,
        .table td {{
            padding: 0.25rem !important;
            font-size: 0.75rem;
        }}
        
        .table th:first-child,
        .table td:first-child {{
            width: 30px !important;
            font-size: 0.7rem;
        }}
        
        .table th:nth-child(2),
        .table td:nth-child(2) {{
            width: 60px !important;
            font-size: 0.6rem;
        }}
        
        /* Скрываем фильтры на мобильных для экономии места */
        .card.mb-4 {{
            margin-bottom: 0.5rem !important;
        }}
        
        .card-body {{
            padding: 0.75rem !important;
        }}
        
        .row.g-3 {{
            gap: 0.5rem !important;
        }}
        
        .form-select,
        .btn {{
            font-size: 0.8rem !important;
        }}
        
        #navigationCard {{
            margin-bottom: 0.5rem !important;
        }}
        
        #navigationCard h5 {{
            font-size: 0.9rem !important;
        }}
        
        #navigationCard .btn {{
            font-size: 0.7rem !important;
            padding: 0.25rem 0.5rem !important;
        }}
    }}
    
    /* Дополнительная оптимизация для очень маленьких экранов */
    @media (max-width: 480px) {{
        .table {{
            min-width: 700px;
        }}
        
        .schedule-cell {{
            min-height: 45px !important;
            font-size: 0.65rem !important;
        }}
        
        .schedule-cell .discipline {{
            font-size: 0.65rem !important;
        }}
        
        .schedule-cell .teacher,
        .schedule-cell .room {{
            font-size: 0.55rem !important;
        }}
        
        h2 {{
            font-size: 1.1rem !important;
        }}
        
        .table th,
        .table td {{
            padding: 0.2rem !important;
            font-size: 0.7rem !important;
        }}
    }}
    
    /* Стили для загрузки и ошибок */
    .loading-indicator {{
        display: none;
        text-align: center;
        padding: 1rem;
    }}
    
    .error-message {{
        display: none;
    }}
    
    /* Исправления для Google Sites iframe */
    @media (max-width: 768px) {{
        body {{
            min-width: 320px !important;
        }}
        
        .table-responsive {{
            margin-left: -0.5rem !important;
            margin-right: -0.5rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }}
    }}
    
    /* Стили для примеров статусов */
    .status-example {{
        width: 20px;
        height: 20px;
        border-radius: 4px;
        display: inline-block;
        border: 2px solid;
    }}
    
    .status-example.status-planned {{ background-color: #fff; border-color: #6c757d; }}
    .status-example.status-done {{ background-color: #d4edda; border-color: #28a745; }}
    .status-example.status-substitution {{ background-color: #fff3cd; border-color: #ffc107; }}
    .status-example.status-cancelled {{ background-color: #f8d7da; border-color: #dc3545; }}
    .status-example.status-completed {{ background-color: #e2d5f1; border-color: #6f42c1; }}
    .status-example.status-rescheduled {{ background-color: #d1ecf1; border-color: #17a2b8; }}
    .status-example.status-empty {{ background-color: #f8f9fa; border-color: #dee2e6; }}
    </style>
</head>
<body>
    <div class="container-fluid p-3">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h2><i class="bi bi-calendar3"></i> APEC Petrotechnic College Schedule</h2>
                <p class="text-muted mb-0">Данные загружаются с GitHub <span id="lastUpdate"></span></p>
            </div>
            <div class="btn-group">
                <button class="btn btn-outline-primary btn-sm" onclick="refreshData()">
                    <i class="bi bi-arrow-clockwise"></i> Обновить
                </button>
            </div>
        </div>

        <!-- Индикатор загрузки -->
        <div id="loadingIndicator" class="loading-indicator">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Загрузка...</span>
            </div>
            <p class="mt-2">Загружаем актуальные данные расписания...</p>
        </div>

        <!-- Сообщение об ошибке -->
        <div id="errorMessage" class="alert alert-warning error-message">
            <h5><i class="bi bi-exclamation-triangle"></i> Ошибка загрузки данных</h5>
            <p>Не удалось загрузить актуальные данные с GitHub. Проверьте подключение к интернету.</p>
            <button class="btn btn-outline-warning" onclick="refreshData()">Попробовать еще раз</button>
        </div>

        <!-- Фильтры -->
        <div class="card mb-4" id="filtersCard" style="display: none;">
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-4">
                        <label class="form-label">Группа</label>
                        <select id="groupSelect" class="form-select" onchange="updateSchedule()">
                            <option value="">-- Выберите группу --</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Преподаватель</label>
                        <select id="teacherSelect" class="form-select" onchange="updateSchedule()">
                            <option value="">-- Или преподавателя --</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Период</label>
                        <div class="btn-group w-100" role="group">
                            <input type="radio" class="btn-check" name="view" id="view_day" value="day" onchange="updateSchedule()">
                            <label class="btn btn-outline-primary" for="view_day">День</label>
                            
                            <input type="radio" class="btn-check" name="view" id="view_week" value="week" checked onchange="updateSchedule()">
                            <label class="btn btn-outline-primary" for="view_week">Неделя</label>
                            
                            <input type="radio" class="btn-check" name="view" id="view_month" value="month" onchange="updateSchedule()">
                            <label class="btn btn-outline-primary" for="view_month">Месяц</label>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Навигация -->
        <div id="navigationCard" class="d-flex justify-content-between align-items-center mb-3" style="display: none;">
            <button class="btn btn-outline-primary" onclick="navigatePeriod(-1)">
                <i class="bi bi-chevron-left"></i> <span id="prevButton">Предыдущий</span>
            </button>
            <h5 class="mb-0 text-center" id="currentPeriod"></h5>
            <button class="btn btn-outline-primary" onclick="navigatePeriod(1)">
                <span id="nextButton">Следующий</span> <i class="bi bi-chevron-right"></i>
            </button>
        </div>

        <!-- Статусы занятий -->
        <div class="card mb-4" id="statusLegend">
            <div class="card-body">
                <h6 class="card-title mb-3"><i class="bi bi-info-circle"></i> Статусы занятий:</h6>
                <div class="row g-2">
                    <div class="col-md-4 col-sm-6">
                        <div class="d-flex align-items-center">
                            <div class="status-example status-planned me-2"></div>
                            <small>Запланирована</small>
                        </div>
                    </div>
                    <div class="col-md-4 col-sm-6">
                        <div class="d-flex align-items-center">
                            <div class="status-example status-done me-2"></div>
                            <small>Проведена</small>
                        </div>
                    </div>
                    <div class="col-md-4 col-sm-6">
                        <div class="d-flex align-items-center">
                            <div class="status-example status-substitution me-2"></div>
                            <small>Замена</small>
                        </div>
                    </div>
                    <div class="col-md-4 col-sm-6">
                        <div class="d-flex align-items-center">
                            <div class="status-example status-cancelled me-2"></div>
                            <small>Отменена</small>
                        </div>
                    </div>
                    <div class="col-md-4 col-sm-6">
                        <div class="d-flex align-items-center">
                            <div class="status-example status-completed me-2"></div>
                            <small>Последняя пара</small>
                        </div>
                    </div>
                    <div class="col-md-4 col-sm-6">
                        <div class="d-flex align-items-center">
                            <div class="status-example status-rescheduled me-2"></div>
                            <small>Перенесена</small>
                        </div>
                    </div>
                    <div class="col-md-4 col-sm-6">
                        <div class="d-flex align-items-center">
                            <div class="status-example status-empty me-2"></div>
                            <small>Вакант</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Контент расписания -->
        <div id="scheduleContent">
            <div class="alert alert-info text-center">
                <h5><i class="bi bi-info-circle"></i> Выберите группу или преподавателя</h5>
                <p class="mb-2">Для просмотра расписания выберите группу или преподавателя из списка выше</p>
                <small class="text-muted"><strong>Подсказка:</strong> Используйте переключатели "День", "Неделя", "Месяц" для выбора типа отображения расписания</small>
            </div>
        </div>
    </div>

<script>
// Конфигурация URL для JSON файлов GitHub
const DRIVE_CONFIG = {{
    groups_url: 'api/groups.json',
    teachers_url: 'api/teachers.json',
    schedule_url: 'api/schedule.json'
}};

// Глобальные переменные
let STATIC_GROUPS = null;
let STATIC_TEACHERS = null;
let STATIC_SCHEDULE = null;

// Настройки отображения
let currentGroupId = null;
let currentTeacherId = null;
let currentView = 'week';
let currentWeekOffset = 0;
let currentDayOffset = 0;
let currentMonthOffset = 0;

// Время последнего обновления
let lastUpdateTime = null;

// Инициализация
document.addEventListener('DOMContentLoaded', function() {{
    loadDataFromDrive();
}});

// Загрузка данных с GitHub
async function loadDataFromDrive() {{
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorMessage = document.getElementById('errorMessage');
    const filtersCard = document.getElementById('filtersCard');
    const navigationCard = document.getElementById('navigationCard');
    
    loadingIndicator.style.display = 'block';
    errorMessage.style.display = 'none';
    filtersCard.style.display = 'none';
    navigationCard.style.display = 'none';
    
    try {{
        console.log('Загружаем данные с GitHub...');
        
        // Загружаем все JSON файлы параллельно
        const [groupsResponse, teachersResponse, scheduleResponse] = await Promise.all([
            fetch(DRIVE_CONFIG.groups_url).catch(e => {{ throw new Error('Группы: ' + e.message) }}),
            fetch(DRIVE_CONFIG.teachers_url).catch(e => {{ throw new Error('Преподаватели: ' + e.message) }}),
            fetch(DRIVE_CONFIG.schedule_url).catch(e => {{ throw new Error('Расписание: ' + e.message) }})
        ]);
        
        if (!groupsResponse.ok) throw new Error('Ошибка загрузки групп');
        if (!teachersResponse.ok) throw new Error('Ошибка загрузки преподавателей');
        if (!scheduleResponse.ok) throw new Error('Ошибка загрузки расписания');
        
        STATIC_GROUPS = await groupsResponse.json();
        STATIC_TEACHERS = await teachersResponse.json();
        STATIC_SCHEDULE = await scheduleResponse.json();
        
        console.log('Данные загружены:', {{
            groups: STATIC_GROUPS.groups.length,
            teachers: STATIC_TEACHERS.teachers.length,
            schedules: STATIC_SCHEDULE.schedules.length
        }});
        
        lastUpdateTime = new Date();
        updateLastUpdateDisplay();
        
        // Инициализируем интерфейс
        initializeInterface();
        
        loadingIndicator.style.display = 'none';
        filtersCard.style.display = 'block';
        navigationCard.style.display = 'flex';
        
    }} catch (error) {{
        console.error('Ошибка загрузки:', error);
        loadingIndicator.style.display = 'none';
        errorMessage.style.display = 'block';
    }}
}}

// Обновление времени последнего обновления
function updateLastUpdateDisplay() {{
    const lastUpdateElement = document.getElementById('lastUpdate');
    if (lastUpdateTime) {{
        lastUpdateElement.textContent = '(обновлено ' + lastUpdateTime.toLocaleTimeString() + ')';
    }}
}}

// Обновление данных
function refreshData() {{
    loadDataFromDrive();
}}

// Инициализация интерфейса
function initializeInterface() {{
    populateDropdowns();
    updateSchedule();
}}

// Заполнение выпадающих списков
function populateDropdowns() {{
    const groupSelect = document.getElementById('groupSelect');
    const teacherSelect = document.getElementById('teacherSelect');
    
    // Очищаем списки
    groupSelect.innerHTML = '<option value="">-- Выберите группу --</option>';
    teacherSelect.innerHTML = '<option value="">-- Или преподавателя --</option>';
    
    // Заполняем группы
    if (STATIC_GROUPS && STATIC_GROUPS.groups) {{
        STATIC_GROUPS.groups.forEach(group => {{
            const option = document.createElement('option');
            option.value = group.id;
            option.textContent = group.name;
            groupSelect.appendChild(option);
        }});
    }}
    
    // Заполняем преподавателей
    if (STATIC_TEACHERS && STATIC_TEACHERS.teachers) {{
        STATIC_TEACHERS.teachers.forEach(teacher => {{
            const option = document.createElement('option');
            option.value = teacher.id;
            option.textContent = teacher.name;
            teacherSelect.appendChild(option);
        }});
    }}
}}

// Обновление расписания
function updateSchedule() {{
    const groupSelect = document.getElementById('groupSelect');
    const teacherSelect = document.getElementById('teacherSelect');
    const viewRadios = document.querySelectorAll('input[name="view"]');
    
    // Получаем текущие значения
    currentGroupId = groupSelect.value ? parseInt(groupSelect.value) : null;
    currentTeacherId = teacherSelect.value ? parseInt(teacherSelect.value) : null;
    
    viewRadios.forEach(radio => {{
        if (radio.checked) currentView = radio.value;
    }});
    
    // Сбрасываем противоположный фильтр
    if (currentGroupId) {{
        teacherSelect.value = '';
        currentTeacherId = null;
    }} else if (currentTeacherId) {{
        groupSelect.value = '';
        currentGroupId = null;
    }}
    
    updateNavigationLabels();
    loadSchedule();
}}

// Навигация по периодам
function navigatePeriod(direction) {{
    if (currentView === 'day') {{
        currentDayOffset += direction;
    }} else if (currentView === 'week') {{
        currentWeekOffset += direction;
    }} else if (currentView === 'month') {{
        currentMonthOffset += direction;
    }}
    updateNavigationLabels();
    loadSchedule();
}}

// Обновление лейблов навигации
function updateNavigationLabels() {{
    const currentPeriodElement = document.getElementById('currentPeriod');
    const prevButton = document.getElementById('prevButton');
    const nextButton = document.getElementById('nextButton');
    const today = new Date();
    
    if (currentView === 'day') {{
        const targetDate = new Date(today);
        targetDate.setDate(today.getDate() + currentDayOffset);
        
        currentPeriodElement.innerHTML = `
            ${{targetDate.toLocaleDateString('ru-RU', {{weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric'}})}}
        `;
        prevButton.textContent = 'Пред. день';
        nextButton.textContent = 'След. день';
        
    }} else if (currentView === 'week') {{
        const currentMonday = new Date(today);
        currentMonday.setDate(today.getDate() - today.getDay() + 1);
        
        const targetMonday = new Date(currentMonday);
        targetMonday.setDate(currentMonday.getDate() + (currentWeekOffset * 7));
        
        const targetSunday = new Date(targetMonday);
        targetSunday.setDate(targetMonday.getDate() + 6);
        
        currentPeriodElement.innerHTML = `
            Неделя ${{targetMonday.toLocaleDateString('ru-RU', {{day: '2-digit', month: '2-digit'}})}} - 
            ${{targetSunday.toLocaleDateString('ru-RU', {{day: '2-digit', month: '2-digit', year: 'numeric'}})}}
        `;
        prevButton.textContent = 'Пред. неделя';
        nextButton.textContent = 'След. неделя';
        
    }} else if (currentView === 'month') {{
        const targetMonth = new Date(today.getFullYear(), today.getMonth() + currentMonthOffset, 1);
        
        currentPeriodElement.innerHTML = `
            ${{targetMonth.toLocaleDateString('ru-RU', {{month: 'long', year: 'numeric'}})}}
        `;
        prevButton.textContent = 'Пред. месяц';
        nextButton.textContent = 'След. месяц';
    }}
}}

// Загрузка и отображение расписания
function loadSchedule() {{
    if (!STATIC_SCHEDULE || !STATIC_SCHEDULE.schedules) {{
        document.getElementById('scheduleContent').innerHTML = 
            '<div class="alert alert-info">Данные расписания не загружены</div>';
        return;
    }}
    
    // Фильтруем расписание
    let filteredSchedules = STATIC_SCHEDULE.schedules;
    
    if (currentGroupId) {{
        filteredSchedules = filteredSchedules.filter(s => 
            s.group && s.group.id === currentGroupId
        );
    }}
    
    if (currentTeacherId) {{
        // Фильтруем по основному преподавателю ИЛИ по заменяющему
        filteredSchedules = filteredSchedules.filter(s =>
            (s.teacher && s.teacher.id === currentTeacherId) ||
            (s.substitute_teacher && s.substitute_teacher.id === currentTeacherId)
        );
    }}
    
    // Определяем период для отображения
    const today = new Date();
    let startDate, endDate;
    
    if (currentView === 'day') {{
        const targetDate = new Date(today);
        targetDate.setDate(today.getDate() + currentDayOffset);
        startDate = new Date(targetDate);
        endDate = new Date(targetDate);
        
    }} else if (currentView === 'week') {{
        const currentMonday = new Date(today);
        currentMonday.setDate(today.getDate() - today.getDay() + 1);
        
        const targetMonday = new Date(currentMonday);
        targetMonday.setDate(currentMonday.getDate() + (currentWeekOffset * 7));
        
        const targetSunday = new Date(targetMonday);
        targetSunday.setDate(targetMonday.getDate() + 6);
        
        startDate = targetMonday;
        endDate = targetSunday;
        
    }} else if (currentView === 'month') {{
        const targetMonth = new Date(today.getFullYear(), today.getMonth() + currentMonthOffset, 1);
        startDate = new Date(targetMonth.getFullYear(), targetMonth.getMonth(), 1);
        endDate = new Date(targetMonth.getFullYear(), targetMonth.getMonth() + 1, 0);
    }}
    
    // Фильтруем по выбранному периоду
    const startDateStr = startDate.getFullYear() + '-' + 
        String(startDate.getMonth() + 1).padStart(2, '0') + '-' + 
        String(startDate.getDate()).padStart(2, '0');
    const endDateStr = endDate.getFullYear() + '-' + 
        String(endDate.getMonth() + 1).padStart(2, '0') + '-' + 
        String(endDate.getDate()).padStart(2, '0');
        
    const periodSchedules = filteredSchedules.filter(s => {{
        return s.date >= startDateStr && s.date <= endDateStr;
    }});
    
    // Отображаем расписание в зависимости от режима
    console.log('loadSchedule data:', {{
        currentView: currentView,
        filteredSchedulesCount: filteredSchedules.length,
        periodSchedulesCount: periodSchedules.length,
        startDate: startDate,
        endDate: endDate,
        startDateStr: startDateStr,
        endDateStr: endDateStr,
        currentTeacherId: currentTeacherId,
        currentGroupId: currentGroupId,
        periodSchedules: periodSchedules
    }});
    
    if (currentView === 'day') {{
        displayDaySchedule(periodSchedules, startDate);
    }} else if (currentView === 'week') {{
        displayWeekSchedule(periodSchedules, startDate, endDate);
    }} else if (currentView === 'month') {{
        displayMonthSchedule(periodSchedules, startDate, endDate);
    }}
}}

// Глобальные константы времени пар
const PAIR_TIMES = {{
    1: {{start: '08:30', end: '09:50'}},
    2: {{start: '10:00', end: '11:20'}},
    3: {{start: '11:30', end: '12:50'}},
    4: {{start: '13:30', end: '14:50'}},
    5: {{start: '15:00', end: '16:20'}},
    6: {{start: '16:30', end: '17:50'}},
    7: {{start: '18:00', end: '19:20'}}
}};

// Глобальная функция для получения информации о статусе
function getStatusInfo(status) {{
    switch(status) {{
        case 'planned':
            return {{ color: 'primary', name: 'Запланирована' }};
        case 'done':
            return {{ color: 'success', name: 'Проведена' }};
        case 'cancelled':
            return {{ color: 'danger', name: 'Отменена' }};
        case 'rescheduled':
            return {{ color: 'warning', name: 'Перенесена' }};
        case 'substitution':
            return {{ color: 'info', name: 'Замена' }};
        case 'completed':
            return {{ color: 'dark', name: 'Последняя пара' }};
        default:
            return {{ color: 'secondary', name: status || 'Неизвестно' }};
    }}
}}

// Отображение недельного расписания
function displayWeekSchedule(schedules, startDate, endDate) {{
    // Создаем сетку расписания
    const scheduleGrid = {{}};
    
    schedules.forEach(schedule => {{
        const scheduleDate = new Date(schedule.date);
        const dayOfWeek = scheduleDate.getDay();
        const dayIndex = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Понедельник = 0
        
        if (!scheduleGrid[dayIndex]) {{
            scheduleGrid[dayIndex] = {{}};
        }}
        
        if (!scheduleGrid[dayIndex][schedule.pair_number]) {{
            scheduleGrid[dayIndex][schedule.pair_number] = [];
        }}
        
        scheduleGrid[dayIndex][schedule.pair_number].push(schedule);
    }});
    
    const WEEK_DAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница'];
    
    let html = `
        <div class="card">
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-bordered">
                        <thead class="table-light">
                            <tr>
                                <th style="width: 80px;">Пара</th>
                                <th style="width: 100px;">Время</th>`;
    
    WEEK_DAYS.forEach((day, index) => {{
        const currentDate = new Date(startDate);
        currentDate.setDate(startDate.getDate() + index);
        html += `<th class="text-center">
            ${{day}}<br>
            <small class="text-muted">${{currentDate.toLocaleDateString('ru-RU', {{day: '2-digit', month: '2-digit'}})}}</small>
        </th>`;
    }});
    
    html += `</tr></thead><tbody>`;
    
    for (let pairNum = 1; pairNum <= 7; pairNum++) {{
        html += `<tr>
            <td class="text-center fw-bold">${{pairNum}}</td>
            <td class="text-center">
                <small>${{PAIR_TIMES[pairNum].start}}<br>${{PAIR_TIMES[pairNum].end}}</small>
            </td>`;
        
        for (let dayIndex = 0; dayIndex < 5; dayIndex++) {{
            const daySchedules = scheduleGrid[dayIndex] && scheduleGrid[dayIndex][pairNum];
            if (daySchedules && daySchedules.length > 0) {{
                const schedule = daySchedules[0]; // Берем первое занятие
                html += `<td class="schedule-cell status-${{schedule.status}}">
                    <div class="d-flex justify-content-between align-items-start mb-1">
                        <div class="discipline">${{schedule.discipline}}</div>
                        <span class="badge bg-${{getStatusInfo(schedule.status).color}} badge-sm">${{getStatusInfo(schedule.status).name}}</span>
                    </div>`;
                
                // Показываем преподавателя если выбрана группа, или группу если выбран преподаватель
                if (currentTeacherId && schedule.group) {{
                    html += `<div class="teacher">гр. ${{schedule.group.name}}</div>`;
                }} else if (schedule.teacher) {{
                    html += `<div class="teacher">${{schedule.teacher.name}}</div>`;
                }}
                
                html += `<div class="room">ауд. ${{schedule.room ? schedule.room.number : '-'}}</div>
                </td>`;
            }} else {{
                html += `<td class="schedule-cell status-empty"></td>`;
            }}
        }}
        
        html += `</tr>`;
        
        // Обеденный перерыв после 3 пары
        if (pairNum === 3) {{
            html += `<tr class="table-secondary">
                <td colspan="7" class="text-center py-1"><strong>ОБЕД</strong> 12:50 - 13:30</td>
            </tr>`;
        }}
    }}
    
    html += `</tbody></table></div></div></div>`;
    
    document.getElementById('scheduleContent').innerHTML = html;
}}

// Отображение дневного расписания
function displayDaySchedule(schedules, targetDate) {{
    
    const targetDateStr = targetDate.getFullYear() + '-' + 
        String(targetDate.getMonth() + 1).padStart(2, '0') + '-' + 
        String(targetDate.getDate()).padStart(2, '0');
    
    
    // schedules уже отфильтрованы по дате в loadSchedule()
    const daySchedules = schedules;
    
    // Группируем по парам
    const scheduleByPair = {{}};
    daySchedules.forEach(schedule => {{
        if (!scheduleByPair[schedule.pair_number]) {{
            scheduleByPair[schedule.pair_number] = [];
        }}
        scheduleByPair[schedule.pair_number].push(schedule);
    }});
    
    const dayName = targetDate.toLocaleDateString('ru-RU', {{ weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }});
    
    let html = `
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">${{dayName}}</h5>
            </div>
            <div class="card-body">
                <div class="list-group">`;
    
    for (let pairNum = 1; pairNum <= 7; pairNum++) {{
        const pairSchedules = scheduleByPair[pairNum];
        if (pairSchedules && pairSchedules.length > 0) {{
            pairSchedules.forEach(schedule => {{
                html += `
                    <div class="list-group-item schedule-cell status-${{schedule.status || 'normal'}} d-flex align-items-center">
                        <div class="me-3">
                            <strong>${{pairNum}}</strong><br>
                            <small>${{PAIR_TIMES[pairNum].start}}<br>${{PAIR_TIMES[pairNum].end}}</small>
                        </div>
                        <div class="flex-grow-1">
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <div class="discipline">${{schedule.discipline || '-'}}</div>
                                <span class="badge bg-${{getStatusInfo(schedule.status).color}}">${{getStatusInfo(schedule.status).name}}</span>
                            </div>`;
                            
                if (currentTeacherId && schedule.group) {{
                    html += `<div class="teacher">гр. ${{schedule.group.name}}</div>`;
                }} else if (schedule.teacher) {{
                    html += `<div class="teacher">${{schedule.teacher.name}}</div>`;
                }}
                
                html += `<div class="room">ауд. ${{schedule.room?.number || '-'}}</div>
                        </div>
                    </div>`;
            }});
        }} else {{
            html += `
                <div class="list-group-item schedule-cell status-empty d-flex align-items-center">
                    <div class="me-3">
                        <strong>${{pairNum}}</strong><br>
                        <small>${{PAIR_TIMES[pairNum].start}}<br>${{PAIR_TIMES[pairNum].end}}</small>
                    </div>
                    <div class="flex-grow-1 text-muted">Свободно</div>
                </div>`;
        }}
        
        if (pairNum === 3) {{
            html += `
                <div class="list-group-item bg-light text-center">
                    <strong>ОБЕД</strong> 12:50 - 13:30
                </div>`;
        }}
    }}
    
    html += `</div></div></div>`;
    document.getElementById('scheduleContent').innerHTML = html;
}}

// Отображение месячного расписания (только рабочие дни пн-пт)
function displayMonthSchedule(schedules, startDate, endDate) {{
    // Группируем по датам (только рабочие дни)
    const schedulesByDate = {{}};
    schedules.forEach(schedule => {{
        const dateKey = schedule.date;
        const dayOfWeek = new Date(dateKey).getDay();
        // Пропускаем выходные (0 - воскресенье, 6 - суббота)
        if (dayOfWeek === 0 || dayOfWeek === 6) return;
        if (!schedulesByDate[dateKey]) {{
            schedulesByDate[dateKey] = [];
        }}
        schedulesByDate[dateKey].push(schedule);
    }});

    let html = `
        <div class="card">
            <div class="card-body">
                <div class="row g-2">`;

    const currentDate = new Date(startDate);
    while (currentDate <= endDate) {{
        const isWeekend = currentDate.getDay() === 0 || currentDate.getDay() === 6;

        // Пропускаем выходные дни
        if (isWeekend) {{
            currentDate.setDate(currentDate.getDate() + 1);
            continue;
        }}

        const dateKey = currentDate.toISOString().split('T')[0];
        const daySchedules = schedulesByDate[dateKey] || [];

        html += `
            <div class="col-md-6 col-lg-4">
                <div class="card">
                    <div class="card-header py-1">
                        <small><strong>${{currentDate.toLocaleDateString('ru-RU', {{weekday: 'short', day: '2-digit', month: '2-digit'}})}}</strong></small>
                    </div>
                    <div class="card-body py-2">`;

        if (daySchedules.length > 0) {{
            daySchedules.forEach(schedule => {{
                html += `
                    <div class="schedule-cell status-${{schedule.status}} mb-1 p-1">
                        <div class="d-flex justify-content-between align-items-start mb-1">
                            <div class="discipline" style="font-size: 0.75rem;">${{schedule.discipline}}</div>
                            <span class="badge bg-${{getStatusInfo(schedule.status).color}}" style="font-size: 0.6rem;">${{getStatusInfo(schedule.status).name}}</span>
                        </div>`;

                if (currentTeacherId && schedule.group) {{
                    html += `<div class="teacher" style="font-size: 0.65rem;">гр. ${{schedule.group.name}}</div>`;
                }} else if (schedule.teacher) {{
                    html += `<div class="teacher" style="font-size: 0.65rem;">${{schedule.teacher.name}}</div>`;
                }}

                html += `<div class="room" style="font-size: 0.65rem;">ауд. ${{schedule.room ? schedule.room.number : '-'}}</div>
                    </div>`;
            }});
        }} else {{
            html += `<div class="text-muted" style="font-size: 0.75rem;">Нет занятий</div>`;
        }}

        html += `
                    </div>
                </div>
            </div>`;

        currentDate.setDate(currentDate.getDate() + 1);
    }}

    html += `</div></div></div>`;
    document.getElementById('scheduleContent').innerHTML = html;
}}

// Показать сообщение о выборе
function showNoSelectionMessage() {{
    document.getElementById('scheduleContent').innerHTML = `
        <div class="alert alert-info text-center">
            <h5><i class="bi bi-info-circle"></i> Выберите группу или преподавателя</h5>
            <p class="mb-0">Для просмотра расписания выберите группу или преподавателя из списков выше</p>
        </div>
    `;
}}
</script>
</body>
</html>"""
            
            # Сохраняем HTML в docs директорию
            html_path = os.path.join(docs_dir, 'index.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_template)
            
            # Создаем README.md с инструкциями для вашего проекта
            readme_content = f"""# АПЭК Петротехник - Данные расписания для GitHub Pages

Автоматически генерируемые данные расписания для АПЭК Петротехник.

## 📁 Структура файлов

- `api/groups.json` - Список всех групп ({json_result['groups_count']} групп)
- `api/teachers.json` - Список преподавателей ({json_result['teachers_count']} человек)
- `api/schedule.json` - Данные расписания ({json_result['schedules_count']} записей)
- `index.html` - HTML интерфейс для просмотра
- `README.md` - Эта документация

## 🚀 Настройка GitHub Pages

### 1. Загрузите файлы в ваш репозиторий
```bash
git clone https://github.com/Azamat313/apec_schedule.git
cd apec_schedule
# Скопируйте файлы из exports/github_pages/ в корень репозитория
```

### 2. Включите GitHub Pages
1. Откройте Settings вашего репозитория
2. Scroll down до секции "Pages" 
3. Source: Deploy from a branch
4. Branch: main (или master)
5. Folder: / (root)
6. Нажмите Save

### 3. Проверьте доступность
Данные будут доступны по адресу:
- **HTML интерфейс:** `https://azamat313.github.io/apec_schedule/`
- **API данные:**
  - `https://azamat313.github.io/apec_schedule/api/groups.json`
  - `https://azamat313.github.io/apec_schedule/api/teachers.json`
  - `https://azamat313.github.io/apec_schedule/api/schedule.json`

## 🌐 Интеграция с Google Sites

### Способ 1: Встроенный код (рекомендуется)
1. Откройте содержимое файла `index.html`
2. Скопируйте весь HTML код
3. В Google Sites: **Вставить → Встроить код**
4. Вставьте HTML код и сохраните

### Способ 2: Iframe
```html
<iframe src="https://azamat313.github.io/apec_schedule/" width="100%" height="600"></iframe>
```

## 📊 Информация о данных

- **Период:** {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}
- **Сгенерировано:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
- **Всего групп:** {json_result['groups_count']}
- **Преподавателей:** {json_result['teachers_count']}
- **Записей расписания:** {json_result['schedules_count']}

## 🔄 Автоматическое обновление

Создайте файл `.github/workflows/update-schedule.yml`:

```yaml
name: Обновление расписания
on:
  schedule:
    - cron: '0 6 * * 1'  # Каждый понедельник в 6:00
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Обновить данные расписания
        run: |
          # Здесь будет ваш скрипт обновления данных
          echo "Обновление данных..."
      - name: Commit changes
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add .
          git commit -m "Автообновление расписания" || exit 0
          git push
```

## 📝 Техническая информация

- **CORS:** Включен для всех доменов
- **Формат данных:** JSON
- **Кодировка:** UTF-8
- **Размер API:** ~3.8MB
- **Время кеширования:** 24 часа

---
🤖 Автоматически сгенерировано системой управления расписанием АПЭК Петротехник
"""
            
            readme_path = os.path.join(github_dir, 'README.md')
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            # Создаем _config.yml для Jekyll
            config_content = """# GitHub Pages configuration
plugins:
  - jekyll-sitemap
  
# CORS headers
headers:
  "/api/*.json":
    - "Access-Control-Allow-Origin: *"
    - "Access-Control-Allow-Methods: GET"
    - "Content-Type: application/json"
"""
            
            config_path = os.path.join(github_dir, '_config.yml')
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
                
            # Создаем .htaccess для CORS (альтернативный способ)
            htaccess_content = """<IfModule mod_headers.c>
    <FilesMatch "\\.json$">
        Header set Access-Control-Allow-Origin "*"
        Header set Access-Control-Allow-Methods "GET"
        Header set Content-Type "application/json"
    </FilesMatch>
</IfModule>
"""
            
            htaccess_path = os.path.join(github_dir, '.htaccess')
            with open(htaccess_path, 'w', encoding='utf-8') as f:
                f.write(htaccess_content)
            
            return {
                'success': True,
                'message': 'GitHub Pages пакет успешно создан',
                'github_dir': github_dir,
                'files': {
                    'html': 'index.html',
                    'readme': 'README.md',
                    'config': '_config.yml',
                    'htaccess': '.htaccess',
                    'groups_api': 'api/groups.json',
                    'teachers_api': 'api/teachers.json',
                    'schedule_api': 'api/schedule.json'
                },
                'instructions': {
                    'step1': 'Создайте GitHub репозиторий (например: username/apec-schedule-data)',
                    'step2': 'Загрузите все файлы из github_pages/ в репозиторий',
                    'step3': 'Включите GitHub Pages в настройках репозитория',
                    'step4': 'Обновите URLs в index.html на ваши GitHub Pages URLs',
                    'step5': 'Используйте index.html в Google Sites'
                },
                'github_config': github_config,
                'schedules_count': json_result['schedules_count'],
                'groups_count': json_result['groups_count'],
                'teachers_count': json_result['teachers_count']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка при создании GitHub Pages пакета: {str(e)}'
            }

    def sync_to_github_repo(self, github_dir: str, repo_url: str, auto_push: bool = False, force_overwrite: bool = False) -> Dict:
        """Синхронизация файлов с GitHub репозиторием"""
        try:
            import subprocess
            import tempfile
            
            # Проверяем и корректируем путь для Windows
            if not os.path.isabs(github_dir):
                # Относительный путь - делаем абсолютным относительно рабочей директории
                github_dir = os.path.abspath(github_dir)
            
            print(f"[SYNC] Начало синхронизации: {github_dir} -> {repo_url}", flush=True)
            
            # Проверяем существование директории
            if not os.path.exists(github_dir):
                return {
                    'success': False,
                    'error': f'Директория {github_dir} не существует'
                }
                
            print(f"[SYNC] Файлы для синхронизации: {os.listdir(github_dir)}", flush=True)
            
            # Создаем временную директорию для клона
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_dir = os.path.join(temp_dir, 'repo')
                print(f"[SYNC] Клонирование в: {repo_dir}")
                
                # Клонируем репозиторий
                result = subprocess.run([
                    'git', 'clone', repo_url, repo_dir
                ], capture_output=True, text=True)
                
                print(f"[SYNC] Git clone результат: код={result.returncode}")
                if result.stdout: print(f"[SYNC] Git clone stdout: {result.stdout}")
                if result.stderr: print(f"[SYNC] Git clone stderr: {result.stderr}")
                
                if result.returncode != 0:
                    return {
                        'success': False,
                        'error': f'Ошибка клонирования: {result.stderr}'
                    }
                
                # Используем папку /docs для GitHub Pages
                pages_dir = os.path.join(repo_dir, 'docs')
                os.makedirs(pages_dir, exist_ok=True)
                
                # Копируем файлы из github_dir в репозиторий
                # Исключаем системные папки Git
                import shutil
                git_system_dirs = {'.git', '.github', 'node_modules', '__pycache__'}
                
                print(f"[SYNC] Режим синхронизации: {'ПОЛНАЯ ПЕРЕЗАПИСЬ' if force_overwrite else 'ОБНОВЛЕНИЕ'}")
                copied_count = 0
                
                if force_overwrite:
                    # Для создания шаблона: полная перезапись
                    print("[SYNC] Полная перезапись - очищаем репозиторий")
                    # Удаляем все файлы кроме .git
                    for item in os.listdir(pages_dir):
                        if item != '.git':
                            item_path = os.path.join(pages_dir, item)
                            try:
                                if os.path.isdir(item_path):
                                    shutil.rmtree(item_path)
                                else:
                                    os.remove(item_path)
                                print(f"[SYNC] Удален: {item_path}")
                            except Exception as e:
                                print(f"[SYNC] Ошибка удаления {item_path}: {e}")
                    
                    # Копируем все файлы заново
                    for item in os.listdir(github_dir):
                        if item in git_system_dirs:
                            continue
                            
                        src = os.path.join(github_dir, item)
                        dst = os.path.join(pages_dir, item)
                        
                        try:
                            if os.path.isdir(src):
                                shutil.copytree(src, dst)
                                print(f"[SYNC] Папка скопирована: {item}")
                            else:
                                # Копируем все файлы включая index.html
                                shutil.copy2(src, dst)
                                print(f"[SYNC] Файл скопирован: {item}")
                            copied_count += 1
                        except Exception as e:
                            print(f"[SYNC] Ошибка копирования {item}: {e}")
                else:
                    # Для обновления данных: только JSON файлы
                    print("[SYNC] Обновление JSON файлов")
                    for item in os.listdir(github_dir):
                        if item in git_system_dirs:
                            continue
                            
                        src = os.path.join(github_dir, item)
                        dst = os.path.join(pages_dir, item)
                        
                        try:
                            if item == 'api':  # Папка с JSON
                                if not os.path.exists(dst):
                                    os.makedirs(dst)
                                # Копируем JSON файлы
                                for json_file in os.listdir(src):
                                    if json_file.endswith('.json'):
                                        shutil.copy2(os.path.join(src, json_file), os.path.join(dst, json_file))
                                        print(f"[SYNC] JSON обновлен: {json_file}")
                                copied_count += 1
                            elif item.endswith(('.json', '.yml', '.yaml')):  # Отдельные файлы конфигурации
                                shutil.copy2(src, dst)
                                print(f"[SYNC] Конфиг обновлен: {item}")
                                copied_count += 1
                        except Exception as e:
                            print(f"[SYNC] Ошибка обновления {item}: {e}")
                
                print(f"[SYNC] Всего скопировано элементов: {copied_count}")
                print(f"[SYNC] Состояние репозитория после копирования: {os.listdir(repo_dir)}")
                
                # Добавляем изменения в git
                print("[SYNC] Добавление изменений в Git...")
                add_result = subprocess.run(['git', 'add', '.'], cwd=repo_dir, capture_output=True, text=True)
                print(f"[SYNC] Git add результат: код={add_result.returncode}")
                if add_result.stdout: print(f"[SYNC] Git add stdout: {add_result.stdout}")
                if add_result.stderr: print(f"[SYNC] Git add stderr: {add_result.stderr}")
                
                # Создаем коммит
                commit_msg = f"Автообновление расписания - {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                print(f"[SYNC] Создание коммита: {commit_msg}")
                result = subprocess.run([
                    'git', 'commit', '-m', commit_msg
                ], cwd=repo_dir, capture_output=True, text=True)
                
                print(f"[SYNC] Git commit результат: код={result.returncode}")
                print(f"[SYNC] Git commit stdout: {result.stdout}")
                if result.stderr: print(f"[SYNC] Git commit stderr: {result.stderr}")
                
                # Проверяем есть ли изменения
                if "nothing to commit" in result.stdout:
                    print(f"[SYNC] Нет изменений для коммита, пропускаем push (auto_push={auto_push})")
                    return {
                        'success': True,
                        'message': 'Нет изменений для синхронизации',
                        'auto_pushed': False
                    }
                
                print(f"[SYNC] Коммит успешно создан, проверяем auto_push={auto_push}")
                if auto_push:
                    # Автоматический push
                    print(f"[SYNC] Начинаем push в GitHub (auto_push={auto_push})...")
                    push_result = subprocess.run([
                        'git', 'push', 'origin', 'main'
                    ], cwd=repo_dir, capture_output=True, text=True)
                    
                    print(f"[SYNC] Git push main результат: код={push_result.returncode}")
                    print(f"[SYNC] Git push stdout: {push_result.stdout}")
                    if push_result.stderr: print(f"[SYNC] Git push stderr: {push_result.stderr}")
                    
                    if push_result.returncode != 0:
                        # Попробуем master если main не работает
                        print("[SYNC] Пробуем push в master ветку...")
                        push_result = subprocess.run([
                            'git', 'push', 'origin', 'master'  
                        ], cwd=repo_dir, capture_output=True, text=True)
                        
                        print(f"[SYNC] Git push master результат: код={push_result.returncode}")
                        print(f"[SYNC] Git push master stdout: {push_result.stdout}")
                        if push_result.stderr: print(f"[SYNC] Git push master stderr: {push_result.stderr}")
                    
                    auto_pushed = push_result.returncode == 0
                    push_error = push_result.stderr if push_result.returncode != 0 else None
                    
                    print(f"[SYNC] Push завершен: auto_pushed={auto_pushed}, push_error={push_error}")
                else:
                    print(f"[SYNC] Push пропущен (auto_push={auto_push})")
                    auto_pushed = False
                    push_error = None
                
                return {
                    'success': True,
                    'message': 'Файлы успешно синхронизированы',
                    'commit_message': commit_msg,
                    'auto_pushed': auto_pushed,
                    'push_error': push_error,
                    'pages_url': f"https://{repo_url.split('/')[-2]}.github.io/{repo_url.split('/')[-1].replace('.git', '')}/"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка синхронизации: {str(e)}'
            }

    def sync_to_github_repository(self, repo_url: str, github_dir: str, auto_push: bool = False) -> Dict:
        """Алиас для sync_to_github_repo с изменённым порядком параметров"""
        return self.sync_to_github_repo(github_dir, repo_url, auto_push)

    def generate_filtered_html(self, period_start: date, period_end: date,
                             group_id: Optional[int] = None, 
                             teacher_id: Optional[int] = None,
                             view_type: str = 'week',
                             api_base_url: str = 'http://localhost:5000',
                             embed_only: bool = False) -> Dict:
        """Генерация HTML с учётом фильтров"""
        try:
            from app.models import Schedule, Group, Teacher, Workload
            from app import db
            
            # Базовый запрос
            query = Schedule.query.join(Workload).filter(
                Schedule.date >= period_start,
                Schedule.date <= period_end
            )
            
            # Применяем фильтры
            if group_id:
                query = query.filter(Workload.group_id == group_id)
            elif teacher_id:
                from sqlalchemy import or_
                # Показываем пары где преподаватель основной ИЛИ заменяющий
                query = query.filter(
                    or_(
                        Workload.teacher_id == teacher_id,
                        Schedule.substitute_teacher_id == teacher_id
                    )
                )
            
            schedules = query.all()
            
            # Определяем заголовок
            title_parts = []
            if group_id:
                group = Group.query.get(group_id)
                title_parts.append(f"Группа {group.name}")
            elif teacher_id:
                teacher = Teacher.query.get(teacher_id)
                title_parts.append(f"Преподаватель {teacher.full_name}")
            
            if view_type == 'week':
                title_parts.append(f"Неделя {period_start.strftime('%d.%m')} - {period_end.strftime('%d.%m.%Y')}")
            elif view_type == 'month':
                title_parts.append(f"{period_start.strftime('%B %Y')}")
            else:
                title_parts.append(f"{period_start.year} год")
            
            title = " | ".join(title_parts) if title_parts else "Расписание АПЭК Петротехник"
            
            # Генерируем интерактивную HTML страницу
            html_content = self.html_generator.generate_interactive_schedule_page(api_base_url)
            
            # Сохраняем файл
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filter_suffix = ''
            if group_id:
                filter_suffix = f'_group_{group_id}'
            elif teacher_id:
                filter_suffix = f'_teacher_{teacher_id}'
            
            filename = f'schedule_{view_type}_{timestamp}{filter_suffix}.html'
            filepath = self.save_html_to_file(html_content, filename)
            
            return {
                'success': True,
                'message': f'HTML сгенерирован ({title})',
                'file_path': filepath,
                'preview_available': True,
                'period': {
                    'start': period_start.isoformat(),
                    'end': period_end.isoformat(),
                    'type': view_type
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Ошибка генерации фильтрованного HTML: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def save_html_to_file(self, html_content: str, filename: str = None) -> str:
        """Сохранение HTML в файл для просмотра"""
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"schedule_{timestamp}.html"
        
        file_path = f"exports/{filename}"
        
        # Создаем директорию если её нет
        import os
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return file_path


def sync_google_sites():
    """Функция для синхронизации с Google Sites"""
    try:
        sites_service = GoogleSitesService()
        
        # Генерируем HTML
        html_content = sites_service.generate_current_week_html()
        
        # Сохраняем для предварительного просмотра
        file_path = sites_service.save_html_to_file(html_content)
        
        return {
            'success': True,
            'message': 'HTML сгенерирован успешно',
            'file_path': file_path,
            'preview_available': True
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': 'Ошибка генерации HTML'
        }