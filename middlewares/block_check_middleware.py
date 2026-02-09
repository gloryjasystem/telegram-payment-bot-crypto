"""
Middleware для проверки блокировки пользователя
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

from services.admin_service import admin_service
from utils.logger import bot_logger


class BlockCheckMiddleware(BaseMiddleware):
    """
    Middleware для проверки заблокирован ли пользователь
    
    Если пользователь заблокирован, отправляет сообщение и прерывает обработку
    """
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """
        Проверка пользователя перед обработкой команды
        
        Args:
            handler: Следующий обработчик
            event: Сообщение от пользователя
            data: Данные контекста
        
        Returns:
            Результат обработчика или None если заблокирован
        """
        user_id = event.from_user.id
        
 # Проверяем заблокирован ли пользователь
        is_blocked = await admin_service.is_user_blocked(user_id)
        
        if is_blocked:
            # Пользователь заблокирован
            bot_logger.warning(f"Blocked user {user_id} tried to use bot")
            
            await event.answer(
                "🚫 **Доступ запрещен**\n\n"
                "Ваш аккаунт заблокирован администратором.\n\n"
                "Если вы считаете это ошибкой, обратитесь в поддержку.",
                parse_mode="Markdown"
            )
            
            # Прерываем обработку
            return None
        
        # Пользователь не заблокирован, продолжаем обработку
        return await handler(event, data)
