"""
Middleware для логирования всех запросов
"""
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from utils.logger import bot_logger, log_user_action


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware для логирования всех входящих сообщений и callback'ов
    
    Полезно для отладки и мониторинга активности бота
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Логирование события перед обработкой
        """
        start_time = datetime.now()
        
        # Логирование Message
        if isinstance(event, Message):
            user = event.from_user
            chat = event.chat
            
            # Формируем информацию о сообщении
            message_info = f"text='{event.text[:50] if event.text else 'N/A'}'"
            
            if event.photo:
                message_info = "photo"
            elif event.document:
                message_info = "document"
            elif event.voice:
                message_info = "voice"
            elif event.video:
                message_info = "video"
            
            bot_logger.debug(
                f"Message from user {user.id} (@{user.username or 'no_username'}) "
                f"in chat {chat.id} ({chat.type}): {message_info}"
            )
            
            # Логируем через log_user_action если есть текст
            if event.text:
                log_user_action(
                    user.id,
                    user.username,
                    f"message: {event.text[:50]}"
                )
        
        # Логирование CallbackQuery
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            callback_data = event.data
            
            bot_logger.debug(
                f"Callback from user {user.id} (@{user.username or 'no_username'}): "
                f"data='{callback_data}'"
            )
            
            log_user_action(
                user.id,
                user.username,
                f"callback: {callback_data}"
            )
        
        # Выполняем обработчик
        try:
            result = await handler(event, data)
            
            # Логируем время выполнения
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if duration > 1.0:
                bot_logger.warning(
                    f"Handler took {duration:.2f}s to execute "
                    f"(event type: {type(event).__name__})"
                )
            
            return result
        
        except Exception as e:
            # Логируем ошибки в обработчиках
            bot_logger.error(
                f"Error in handler for {type(event).__name__}: {e}",
                exc_info=True
            )
            raise


class PerformanceMiddleware(BaseMiddleware):
    """
    Middleware для мониторинга производительности
    
    Отслеживает медленные обработчики
    """
    
    def __init__(self, slow_threshold: float = 1.0):
        """
        Args:
            slow_threshold: Порог медленного обработчика (секунды)
        """
        super().__init__()
        self.slow_threshold = slow_threshold
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Измерение производительности"""
        start_time = datetime.now()
        
        result = await handler(event, data)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Если обработчик медленный - логируем
        if duration > self.slow_threshold:
            event_type = type(event).__name__
            
            # Получаем дополнительную информацию
            extra_info = ""
            if isinstance(event, Message) and event.text:
                extra_info = f" (text: {event.text[:30]})"
            elif isinstance(event, CallbackQuery):
                extra_info = f" (callback: {event.data})"
            
            bot_logger.warning(
                f"⚠️ Slow handler detected: {duration:.2f}s for {event_type}{extra_info}"
            )
        
        return result
