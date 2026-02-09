"""
Middleware для защиты от спама (rate limiting)
"""
from typing import Callable, Dict, Any, Awaitable
from collections import defaultdict
from datetime import datetime, timedelta
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from utils.logger import bot_logger


class AntiSpamMiddleware(BaseMiddleware):
    """
    Middleware для защиты от спама через rate limiting
    
    Ограничивает количество сообщений от одного пользователя
    """
    
    def __init__(
        self,
        time_window: int = 1,  # Временное окно в секундах
        max_requests: int = 3   # Максимум запросов в окне
    ):
        """
        Инициализация антиспам middleware
        
        Args:
            time_window: Размер временного окна в секундах
            max_requests: Максимум запросов в окне
        """
        super().__init__()
        self.time_window = timedelta(seconds=time_window)
        self.max_requests = max_requests
        
        # Хранилище запросов: {user_id: [timestamp1, timestamp2, ...]}
        self.user_requests: Dict[int, list[datetime]] = defaultdict(list)
        
        # Хранилище блокировок: {user_id: blocked_until}
        self.user_blocks: Dict[int, datetime] = {}
    
    def _cleanup_old_requests(self, user_id: int) -> None:
        """
        Очистка старых запросов вне временного окна
        
        Args:
            user_id: ID пользователя
        """
        now = datetime.now()
        cutoff_time = now - self.time_window
        
        # Фильтруем только запросы в пределах окна
        self.user_requests[user_id] = [
            req_time 
            for req_time in self.user_requests[user_id]
            if req_time > cutoff_time
        ]
    
    def _is_rate_limited(self, user_id: int) -> bool:
        """
        Проверка превышения лимита запросов
        
        Args:
            user_id: ID пользователя
        
        Returns:
            bool: True если превышен лимит
        """
        # Очищаем старые запросы
        self._cleanup_old_requests(user_id)
        
        # Проверяем количество запросов
        request_count = len(self.user_requests[user_id])
        
        return request_count >= self.max_requests
    
    def _is_blocked(self, user_id: int) -> bool:
        """
        Проверка блокировки пользователя
        
        Args:
            user_id: ID пользователя
        
        Returns:
            bool: True если пользователь заблокирован
        """
        if user_id not in self.user_blocks:
            return False
        
        blocked_until = self.user_blocks[user_id]
        now = datetime.now()
        
        if now < blocked_until:
            return True
        else:
            # Блокировка истекла
            del self.user_blocks[user_id]
            return False
    
    def _block_user(self, user_id: int, duration_seconds: int = 60) -> None:
        """
        Блокировка пользователя на указанное время
        
        Args:
            user_id: ID пользователя
            duration_seconds: Длительность блокировки в секундах
        """
        blocked_until = datetime.now() + timedelta(seconds=duration_seconds)
        self.user_blocks[user_id] = blocked_until
        
        bot_logger.warning(
            f"User {user_id} blocked for {duration_seconds}s due to spam"
        )
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка события с проверкой rate limit
        """
        # Определяем user_id
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if user_id is None:
            return await handler(event, data)
        
        # Пропускаем админов (они не подвержены rate limiting)
        from config import Config
        if user_id in Config.ADMIN_IDS:
            return await handler(event, data)
        
        # Проверка блокировки
        if self._is_blocked(user_id):
            bot_logger.debug(f"Blocked user {user_id} attempted request")
            
            if isinstance(event, Message):
                await event.answer(
                    "⏸ Вы отправляете слишком много запросов. "
                    "Пожалуйста, подождите немного."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⏸ Слишком много запросов. Подождите.",
                    show_alert=True
                )
            
            return None  # Блокируем обработку
        
        # Проверка rate limit
        if self._is_rate_limited(user_id):
            bot_logger.warning(f"Rate limit exceeded for user {user_id}")
            
            # Блокируем пользователя
            self._block_user(user_id, duration_seconds=60)
            
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Вы превысили лимит запросов.\n"
                    "Пожалуйста, подождите 1 минуту перед следующим запросом."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⚠️ Превышен лимит запросов. Подождите 1 минуту.",
                    show_alert=True
                )
            
            return None  # Блокируем обработку
        
        # Регистрируем запрос
        now = datetime.now()
        self.user_requests[user_id].append(now)
        
        # Продолжаем обработку
        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """
    Простой throttling middleware для команд
    
    Более простая альтернатива AntiSpamMiddleware
    """
    
    def __init__(self, throttle_time: float = 0.5):
        """
        Args:
            throttle_time: Минимальное время между командами (секунды)
        """
        super().__init__()
        self.throttle_time = throttle_time
        self.user_last_request: Dict[int, datetime] = {}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Обработка с throttling"""
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if user_id is None:
            return await handler(event, data)
        
        # Пропускаем админов
        from config import Config
        if user_id in Config.ADMIN_IDS:
            return await handler(event, data)
        
        now = datetime.now()
        
        # Проверяем последний запрос
        if user_id in self.user_last_request:
            last_request = self.user_last_request[user_id]
            time_passed = (now - last_request).total_seconds()
            
            if time_passed < self.throttle_time:
                # Слишком быстро
                if isinstance(event, CallbackQuery):
                    await event.answer("Подождите немного", show_alert=False)
                return None
        
        # Обновляем время последнего запроса
        self.user_last_request[user_id] = now
        
        return await handler(event, data)
