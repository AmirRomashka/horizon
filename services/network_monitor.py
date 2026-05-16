import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque
import aiohttp
from contextlib import asynccontextmanager

@dataclass
class NetworkCheck:
    timestamp: datetime
    success: bool
    response_time: float  # в секундах
    error_message: Optional[str] = None

class NetworkMonitorService:
    """Сервис мониторинга соединения с Telegram API"""
    
    def __init__(self, bot_token: str, check_interval: int = 5):
        self.bot_token = bot_token
        self.check_interval = check_interval  # секунд между проверками
        self.checks: deque = deque(maxlen=1000)  # храним последние 1000 проверок
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._api_url = f"https://api.telegram.org/bot{bot_token}/getMe"
        
    async def start(self):
        """Запуск фонового мониторинга"""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._monitor_loop())
        print(f"✅ Network monitor service started (interval: {self.check_interval}s)")
    
    async def stop(self):
        """Остановка мониторинга"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("❌ Network monitor service stopped")
    
    async def _monitor_loop(self):
        """Основной цикл мониторинга"""
        while self.is_running:
            start_time = time.time()
            success = False
            error_msg = None
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self._api_url,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        response_time = time.time() - start_time
                        if response.status == 200:
                            success = True
                        else:
                            error_msg = f"HTTP {response.status}"
                            
            except asyncio.TimeoutError:
                response_time = time.time() - start_time
                error_msg = "Timeout error"
            except aiohttp.ClientError as e:
                response_time = time.time() - start_time
                error_msg = f"Connection error: {str(e)[:50]}"
            except Exception as e:
                response_time = time.time() - start_time
                error_msg = f"Unknown error: {str(e)[:50]}"
            else:
                response_time = time.time() - start_time
            
            # Сохраняем результат проверки
            self.checks.append(NetworkCheck(
                timestamp=datetime.now(),
                success=success,
                response_time=response_time,
                error_message=error_msg
            ))
            
            # Логируем проблемы
            if not success:
                print(f"⚠️ Network check failed: {error_msg}")
            
            await asyncio.sleep(self.check_interval)
    
    def get_statistics(self) -> Dict:
        """Получить статистику мониторинга"""
        if not self.checks:
            return {
                "total_checks": 0,
                "success_rate": 0,
                "avg_response_time": 0,
                "last_check": None,
                "current_status": "Unknown",
                "recent_errors": []
            }
        
        total = len(self.checks)
        successful = sum(1 for c in self.checks if c.success)
        success_rate = (successful / total) * 100
        
        # Среднее время ответа (только успешные)
        response_times = [c.response_time for c in self.checks if c.success]
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        
        # Последние 5 ошибок
        recent_errors = [
            {
                "time": c.timestamp.strftime("%H:%M:%S"),
                "error": c.error_message,
                "duration": round(c.response_time, 2)
            }
            for c in list(self.checks)[-10:] if not c.success
        ]
        
        # Текущий статус (последние 3 проверки ~15 секунд)
        last_checks = list(self.checks)[-3:]
        current_status = "🟢 OK" if all(c.success for c in last_checks) else "🔴 Issues"
        
        # Подсчет downtime за последний час
        one_hour_ago = datetime.now() - timedelta(hours=1)
        last_hour_checks = [c for c in self.checks if c.timestamp > one_hour_ago]
        last_hour_failed = sum(1 for c in last_hour_checks if not c.success)
        
        return {
            "total_checks": total,
            "success_rate": round(success_rate, 2),
            "avg_response_time": round(avg_response, 3),
            "last_check": self.checks[-1].timestamp.strftime("%H:%M:%S"),
            "last_status": "✅ Success" if self.checks[-1].success else f"❌ {self.checks[-1].error_message}",
            "current_status": current_status,
            "recent_errors": recent_errors[:5],
            "last_hour_stats": {
                "total": len(last_hour_checks),
                "failed": last_hour_failed,
                "uptime": round(((len(last_hour_checks) - last_hour_failed) / len(last_hour_checks)) * 100, 2) if last_hour_checks else 100
            }
        }
    
    def get_uptime_report(self) -> str:
        """Сформировать текстовый отчет"""
        stats = self.get_statistics()
        
        if stats["total_checks"] == 0:
            return "📊 Нет данных о сети. Мониторинг только начат.\nПодождите 1-2 минуты для накопления статистики."
        
        # Определяем эмодзи для uptime
        if stats["success_rate"] > 95:
            uptime_emoji = "🟢 Отлично"
        elif stats["success_rate"] > 80:
            uptime_emoji = "🟡 Средне"
        else:
            uptime_emoji = "🔴 Плохо"
        
        report = (
            f"🌐 <b>Статистика сети Telegram API</b>\n\n"
            f"{stats['current_status']} <b>Текущее состояние</b>\n\n"
            f"📈 <b>Общая статистика:</b>\n"
            f"• Проверок: {stats['total_checks']}\n"
            f"• Успешность: {stats['success_rate']}% {uptime_emoji}\n"
            f"• Средний ответ: {stats['avg_response_time']} сек\n\n"
            f"⏱ <b>Последняя проверка:</b>\n"
            f"• Время: {stats['last_check']}\n"
            f"• Статус: {stats['last_status']}\n\n"
        )
        
        # Добавляем статистику за последний час
        if stats["last_hour_stats"]["total"] > 0:
            uptime_hour_emoji = "🟢" if stats["last_hour_stats"]["uptime"] > 95 else "🟡" if stats["last_hour_stats"]["uptime"] > 80 else "🔴"
            report += (
                f"📊 <b>За последний час:</b>\n"
                f"• Аптайм: {stats['last_hour_stats']['uptime']}% {uptime_hour_emoji}\n"
                f"• Ошибок: {stats['last_hour_stats']['failed']} из {stats['last_hour_stats']['total']}\n\n"
            )
        
        # Добавляем последние ошибки
        if stats["recent_errors"]:
            report += "<b>⚠️ Последние ошибки (max 5):</b>\n"
            for err in stats["recent_errors"][:5]:
                report += f"• [{err['time']}] {err['error']} ({err['duration']}с)\n"
        else:
            report += "✅ <b>Нет ошибок в последних 10 проверках</b>"
        
        return report


# Глобальный экземпляр сервиса
_network_monitor: Optional[NetworkMonitorService] = None

async def init_network_monitor(bot_token: str, check_interval: int = 5) -> NetworkMonitorService:
    """Инициализация глобального сервиса мониторинга сети"""
    global _network_monitor
    if _network_monitor:
        await _network_monitor.stop()
    
    _network_monitor = NetworkMonitorService(bot_token, check_interval)
    await _network_monitor.start()
    return _network_monitor

async def stop_network_monitor():
    """Остановка сервиса мониторинга сети"""
    global _network_monitor
    if _network_monitor:
        await _network_monitor.stop()
        _network_monitor = None

def get_network_monitor() -> Optional[NetworkMonitorService]:
    """Получить экземпляр сервиса мониторинга сети"""
    return _network_monitor