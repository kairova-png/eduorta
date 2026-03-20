/**
 * Google Apps Script Webhook Receiver
 * Принимает данные расписания от Flask приложения и записывает в Google Sheets
 */

// Конфигурация
const CONFIG = {
  // ID вашей Google Таблицы (замените на реальный ID)
  SPREADSHEET_ID: 'YOUR_SPREADSHEET_ID_HERE',
  
  // Названия листов
  SHEETS: {
    SCHEDULE: 'Расписание',
    GROUPS: 'Группы', 
    TEACHERS: 'Преподаватели',
    LOG: 'Журнал обновлений'
  },
  
  // Настройки
  MAX_LOG_RECORDS: 1000,
  TIMEZONE: 'Asia/Almaty'
};

/**
 * Обработка GET запросов (для тестирования)
 */
function doGet(e) {
  try {
    // Простой тест подключения
    return ContentService
      .createTextOutput(JSON.stringify({
        success: true,
        message: 'Google Apps Script webhook работает!',
        action: 'test_connection',
        timestamp: new Date().toISOString(),
        config: {
          spreadsheet_id: CONFIG.SPREADSHEET_ID,
          sheets: Object.keys(CONFIG.SHEETS)
        }
      }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({
        success: false,
        error: error.toString(),
        timestamp: new Date().toISOString()
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Основная функция обработки POST запросов
 */
function doPost(e) {
  try {
    console.log('Получен webhook запрос');
    
    // Парсинг данных
    const data = JSON.parse(e.postData.contents);
    console.log('Данные получены:', data.action, data.metadata?.record_count || 0, 'записей');
    
    // Обработка в зависимости от типа действия
    let result;
    switch (data.action) {
      case 'update_schedule':
        result = updateScheduleData(data);
        break;
        
      case 'test_connection':
        result = testConnection(data);
        break;
        
      default:
        throw new Error(`Неизвестное действие: ${data.action}`);
    }
    
    // Логирование
    logUpdate(data, result);
    
    // Возврат результата
    return ContentService
      .createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    console.error('Ошибка обработки webhook:', error);
    
    // Логирование ошибки
    logError(error, e);
    
    return ContentService
      .createTextOutput(JSON.stringify({
        success: false,
        error: error.toString(),
        timestamp: new Date().toISOString()
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Обновление данных расписания
 */
function updateScheduleData(data) {
  const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
  
  // Получение или создание листа расписания
  let scheduleSheet = getOrCreateSheet(spreadsheet, CONFIG.SHEETS.SCHEDULE);
  
  // Обновление в зависимости от типа
  let updatedRecords = 0;
  
  switch (data.update_type) {
    case 'full':
      updatedRecords = fullScheduleUpdate(scheduleSheet, data.schedule_data);
      break;
      
    case 'single_group':
      updatedRecords = groupScheduleUpdate(scheduleSheet, data.schedule_data, data.metadata.group);
      break;
      
    case 'partial':
      updatedRecords = partialScheduleUpdate(scheduleSheet, data.schedule_data);
      break;
      
    default:
      throw new Error(`Неизвестный тип обновления: ${data.update_type}`);
  }
  
  // Применение форматирования
  formatScheduleSheet(scheduleSheet);
  
  return {
    success: true,
    action: 'update_schedule',
    update_type: data.update_type,
    records_processed: updatedRecords,
    timestamp: new Date().toISOString()
  };
}

/**
 * Полное обновление расписания
 */
function fullScheduleUpdate(sheet, scheduleData) {
  console.log('Выполняется полное обновление расписания');
  
  // Очистка старых данных (кроме заголовков)
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.deleteRows(2, lastRow - 1);
  }
  
  // Создание заголовков если их нет
  setupScheduleHeaders(sheet);
  
  // Добавление новых данных
  if (scheduleData.length > 0) {
    const dataRows = scheduleData.map(record => formatScheduleRow(record));
    sheet.getRange(2, 1, dataRows.length, dataRows[0].length).setValues(dataRows);
  }
  
  return scheduleData.length;
}

/**
 * Обновление расписания группы
 */
function groupScheduleUpdate(sheet, scheduleData, groupInfo) {
  console.log(`Обновление расписания группы: ${groupInfo?.name || 'Unknown'}`);
  
  // Создание заголовков если их нет
  setupScheduleHeaders(sheet);
  
  // Удаление старых записей группы
  if (groupInfo && groupInfo.id) {
    deleteGroupRecords(sheet, groupInfo.name);
  }
  
  // Добавление новых данных
  if (scheduleData.length > 0) {
    const dataRows = scheduleData.map(record => formatScheduleRow(record));
    const lastRow = sheet.getLastRow();
    sheet.getRange(lastRow + 1, 1, dataRows.length, dataRows[0].length).setValues(dataRows);
  }
  
  return scheduleData.length;
}

/**
 * Частичное обновление расписания
 */
function partialScheduleUpdate(sheet, scheduleData) {
  console.log('Выполняется частичное обновление расписания');
  
  setupScheduleHeaders(sheet);
  
  let updatedRecords = 0;
  
  scheduleData.forEach(record => {
    const rowIndex = findScheduleRecord(sheet, record.id);
    const formattedRow = formatScheduleRow(record);
    
    if (rowIndex > 0) {
      // Обновление существующей записи
      sheet.getRange(rowIndex, 1, 1, formattedRow.length).setValues([formattedRow]);
    } else {
      // Добавление новой записи
      const lastRow = sheet.getLastRow();
      sheet.getRange(lastRow + 1, 1, 1, formattedRow.length).setValues([formattedRow]);
    }
    
    updatedRecords++;
  });
  
  return updatedRecords;
}

/**
 * Создание заголовков листа расписания
 */
function setupScheduleHeaders(sheet) {
  const headers = [
    'ID', 'Дата', 'День недели', '№ пары', 'Время', 'Группа', 'Дисциплина',
    'Тип занятия', 'Преподаватель', 'Аудитория', 'Статус', 'Семестр',
    'Учебный год', 'Примечания', 'Последнее обновление'
  ];
  
  const firstRow = sheet.getRange(1, 1, 1, headers.length);
  firstRow.setValues([headers]);
  
  // Форматирование заголовков
  firstRow.setBackground('#4285F4');
  firstRow.setFontColor('white');
  firstRow.setFontWeight('bold');
  firstRow.setWrap(true);
}

/**
 * Форматирование строки расписания
 */
function formatScheduleRow(record) {
  return [
    record.id,
    record.date,
    record.day_of_week,
    record.pair_number,
    record.pair_time,
    record.group_name,
    record.discipline,
    record.lesson_type === 'theory' ? 'Теория' : 'Практика',
    record.teacher_name,
    record.room_name,
    record.status_display,
    record.semester,
    record.academic_year,
    record.notes || '',
    new Date().toLocaleString('ru-RU', {timeZone: CONFIG.TIMEZONE})
  ];
}

/**
 * Применение форматирования к листу расписания
 */
function formatScheduleSheet(sheet) {
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  
  if (lastRow < 2) return;
  
  // Основное форматирование
  const dataRange = sheet.getRange(2, 1, lastRow - 1, lastCol);
  dataRange.setWrap(false);
  dataRange.setVerticalAlignment('middle');
  
  // Автоширина колонок
  sheet.autoResizeColumns(1, lastCol);
  
  // Заморозка заголовков
  sheet.setFrozenRows(1);
  
  // Условное форматирование статусов
  applyStatusFormatting(sheet);
  
  // Сортировка по дате и номеру пары
  if (lastRow > 2) {
    const sortRange = sheet.getRange(2, 1, lastRow - 1, lastCol);
    sortRange.sort([{column: 2, ascending: true}, {column: 4, ascending: true}]);
  }
}

/**
 * Применение цветового кодирования статусов
 */
function applyStatusFormatting(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return;
  
  const statusColumn = 11; // Колонка "Статус"
  const statusRange = sheet.getRange(2, statusColumn, lastRow - 1, 1);
  
  // Правила условного форматирования
  const rules = [
    {
      condition: SpreadsheetApp.newConditionalFormatRule()
        .whenTextEqualTo('Проведено')
        .setBackground('#D4EDDA')
        .build()
    },
    {
      condition: SpreadsheetApp.newConditionalFormatRule()
        .whenTextEqualTo('Отменено')
        .setBackground('#F8D7DA')
        .build()
    },
    {
      condition: SpreadsheetApp.newConditionalFormatRule()
        .whenTextEqualTo('Замена')
        .setBackground('#FFF3CD')
        .build()
    },
    {
      condition: SpreadsheetApp.newConditionalFormatRule()
        .whenTextEqualTo('Перенесено')
        .setBackground('#D1ECF1')
        .build()
    }
  ];
  
  sheet.setConditionalFormatRules(rules);
}

/**
 * Поиск записи расписания по ID
 */
function findScheduleRecord(sheet, recordId) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return -1;
  
  const idRange = sheet.getRange(2, 1, lastRow - 1, 1);
  const values = idRange.getValues();
  
  for (let i = 0; i < values.length; i++) {
    if (values[i][0] == recordId) {
      return i + 2; // +2 потому что начинаем с строки 2 (после заголовков)
    }
  }
  
  return -1;
}

/**
 * Удаление записей группы
 */
function deleteGroupRecords(sheet, groupName) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return;
  
  const groupColumn = 6; // Колонка "Группа"
  
  // Удаляем строки снизу вверх, чтобы не сбить индексы
  for (let i = lastRow; i >= 2; i--) {
    const cellValue = sheet.getRange(i, groupColumn).getValue();
    if (cellValue === groupName) {
      sheet.deleteRow(i);
    }
  }
}

/**
 * Получение или создание листа
 */
function getOrCreateSheet(spreadsheet, sheetName) {
  let sheet = spreadsheet.getSheetByName(sheetName);
  
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
    console.log(`Создан новый лист: ${sheetName}`);
  }
  
  return sheet;
}

/**
 * Тест подключения
 */
function testConnection(data) {
  console.log('Выполняется тест подключения');
  
  return {
    success: true,
    action: 'test_connection',
    message: 'Подключение успешно',
    server_time: new Date().toISOString(),
    received_data: data
  };
}

/**
 * Логирование обновлений
 */
function logUpdate(data, result) {
  try {
    const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    const logSheet = getOrCreateSheet(spreadsheet, CONFIG.SHEETS.LOG);
    
    // Создание заголовков лога если их нет
    if (logSheet.getLastRow() === 0) {
      const headers = ['Дата', 'Время', 'Действие', 'Тип обновления', 'Записей', 'Статус', 'Детали'];
      logSheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      logSheet.getRange(1, 1, 1, headers.length).setBackground('#E0E0E0').setFontWeight('bold');
    }
    
    // Добавление записи лога
    const logEntry = [
      new Date().toLocaleDateString('ru-RU'),
      new Date().toLocaleTimeString('ru-RU'),
      data.action,
      data.update_type || 'N/A',
      data.metadata?.record_count || result.records_processed || 0,
      result.success ? 'Успешно' : 'Ошибка',
      result.error || JSON.stringify(result)
    ];
    
    const lastRow = logSheet.getLastRow();
    logSheet.getRange(lastRow + 1, 1, 1, logEntry.length).setValues([logEntry]);
    
    // Ограничение количества записей лога
    if (lastRow > CONFIG.MAX_LOG_RECORDS) {
      logSheet.deleteRows(2, lastRow - CONFIG.MAX_LOG_RECORDS);
    }
    
  } catch (error) {
    console.error('Ошибка записи в лог:', error);
  }
}

/**
 * Логирование ошибок
 */
function logError(error, requestData) {
  try {
    const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    const logSheet = getOrCreateSheet(spreadsheet, CONFIG.SHEETS.LOG);
    
    const errorEntry = [
      new Date().toLocaleDateString('ru-RU'),
      new Date().toLocaleTimeString('ru-RU'),
      'ERROR',
      'Ошибка обработки',
      0,
      'Ошибка',
      error.toString()
    ];
    
    const lastRow = logSheet.getLastRow();
    logSheet.getRange(lastRow + 1, 1, 1, errorEntry.length).setValues([errorEntry]);
    
  } catch (logError) {
    console.error('Критическая ошибка записи в лог:', logError);
  }
}

/**
 * Функция для ручной настройки (вызывается один раз)
 */
function setupSpreadsheet() {
  const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
  
  // Создание необходимых листов
  Object.values(CONFIG.SHEETS).forEach(sheetName => {
    getOrCreateSheet(spreadsheet, sheetName);
  });
  
  console.log('Таблица настроена успешно');
}

/**
 * Получение статуса системы
 */
function getSystemStatus() {
  try {
    const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    const scheduleSheet = spreadsheet.getSheetByName(CONFIG.SHEETS.SCHEDULE);
    
    return {
      spreadsheet_id: CONFIG.SPREADSHEET_ID,
      schedule_records: scheduleSheet ? scheduleSheet.getLastRow() - 1 : 0,
      last_update: new Date().toISOString(),
      status: 'active'
    };
    
  } catch (error) {
    return {
      error: error.toString(),
      status: 'error'
    };
  }
}