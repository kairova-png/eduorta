"""
Система автосинхронизации Google Sheets при изменениях расписания
"""

from sqlalchemy import event
from flask import current_app
from app.models import Schedule
from app.services.google_sheets_simple import auto_sync_schedule_change
import threading
import time


class AutoSyncManager:
    """Менеджер автосинхронизации"""
    
    def __init__(self):
        self.enabled = False
        self.pending_syncs = set()
        self.sync_lock = threading.Lock()
        
    def enable(self):
        """Включить автосинхронизацию"""
        if not self.enabled:
            self._register_events()
            self.enabled = True
            print("Автосинхронизация Google Sheets включена")
    
    def disable(self):
        """Отключить автосинхронизацию"""
        if self.enabled:
            self._unregister_events()
            self.enabled = False
            print("Автосинхронизация Google Sheets отключена")
    
    def _register_events(self):
        """Регистрация SQLAlchemy событий"""
        event.listen(Schedule, 'after_insert', self._on_schedule_insert)
        event.listen(Schedule, 'after_update', self._on_schedule_update)
        event.listen(Schedule, 'after_delete', self._on_schedule_delete)
    
    def _unregister_events(self):
        """Отмена регистрации событий"""
        event.remove(Schedule, 'after_insert', self._on_schedule_insert)
        event.remove(Schedule, 'after_update', self._on_schedule_update) 
        event.remove(Schedule, 'after_delete', self._on_schedule_delete)
    
    def _on_schedule_insert(self, mapper, connection, target):
        """Обработка добавления новой записи расписания"""
        self._queue_sync(target.id, 'insert')
    
    def _on_schedule_update(self, mapper, connection, target):
        """Обработка изменения записи расписания"""
        self._queue_sync(target.id, 'update')
    
    def _on_schedule_delete(self, mapper, connection, target):
        """Обработка удаления записи расписания"""
        self._queue_sync(target.id, 'delete')
    
    def _queue_sync(self, schedule_id: int, operation: str):
        """Добавление в очередь синхронизации"""
        with self.sync_lock:
            self.pending_syncs.add((schedule_id, operation))
        
        # Запускаем отложенную синхронизацию (через 2 секунды)
        threading.Timer(2.0, self._process_sync_queue).start()
    
    def _process_sync_queue(self):
        """Обработка очереди синхронизации"""
        if not self.enabled:
            return
            
        with self.sync_lock:
            if not self.pending_syncs:
                return
            
            # Копируем очередь и очищаем оригинал
            syncs_to_process = list(self.pending_syncs)
            self.pending_syncs.clear()
        
        # Обрабатываем уникальные schedule_id (исключаем дубликаты)
        unique_schedules = set(schedule_id for schedule_id, _ in syncs_to_process)
        
        for schedule_id in unique_schedules:
            try:
                self._sync_schedule_change(schedule_id)
            except Exception as e:
                print(f"⚠️ Ошибка автосинхронизации для schedule_id {schedule_id}: {e}")
    
    def _sync_schedule_change(self, schedule_id: int):
        """Синхронизация изменения в расписании"""
        try:
            # Проверяем настройки
            if not current_app.config.get('GOOGLE_SHEETS_AUTO_SYNC', False):
                return
            
            webhook_url = current_app.config.get('GOOGLE_SHEETS_SIMPLE_WEBHOOK_URL')
            if not webhook_url:
                return
            
            # Выполняем синхронизацию
            result = auto_sync_schedule_change(schedule_id)
            
            if result['success']:
                print(f"Автосинхронизация выполнена для schedule_id {schedule_id}")
            else:
                if 'message' in result:
                    print(f"INFO: {result['message']} (schedule_id {schedule_id})")
                else:
                    print(f"ERROR: Ошибка автосинхронизации: {result.get('error', 'Неизвестная ошибка')}")
                    
        except Exception as e:
            print(f"WARNING: Критическая ошибка автосинхронизации: {e}")


# Глобальный экземпляр менеджера
auto_sync_manager = AutoSyncManager()


def init_auto_sync(app):
    """Инициализация автосинхронизации при запуске приложения"""
    
    with app.app_context():
        if app.config.get('GOOGLE_SHEETS_AUTO_SYNC', False):
            auto_sync_manager.enable()
        else:
            auto_sync_manager.disable()


def enable_auto_sync():
    """Включить автосинхронизацию"""
    auto_sync_manager.enable()


def disable_auto_sync():
    """Отключить автосинхронизацию"""
    auto_sync_manager.disable()


def get_auto_sync_status():
    """Получить статус автосинхронизации"""
    return {
        'enabled': auto_sync_manager.enabled,
        'pending_syncs': len(auto_sync_manager.pending_syncs),
        'config_enabled': current_app.config.get('GOOGLE_SHEETS_AUTO_SYNC', False),
        'webhook_configured': bool(current_app.config.get('GOOGLE_SHEETS_SIMPLE_WEBHOOK_URL'))
    }