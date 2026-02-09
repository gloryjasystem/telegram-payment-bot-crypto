"""
Middleware для проверки админских прав
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config import Config
from utils.logger import bot_logger


class AdminAuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки прав администратора
    
    Используется для защиты админских команд и callback'ов
    Пропускает только пользователей из Config.ADMIN_IDS
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка события
        
        Args:
            handler: Следующий обработчик в цепочке
            event: Событие (Message или CallbackQuery)
            data: Данные для передачи в handler
        
        Returns:
            Результат обработки или None если доступ запрещен
        """
        # Определяем user_id в зависимости от типа события
        user_id = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        # Если user_id не определен, блокируем
        if user_id is None:
            bot_logger.warning("Could not determine user_id from event")
            return None
        
        # Проверка прав администратора
        if user_id not in Config.ADMIN_IDS:
            bot_logger.warning(f"Unauthorized admin access attempt from user {user_id}")
            
            # Отправляем сообщение о недостатке прав
            if isinstance(event, Message):
                await event.answer(
                    "❌ У вас нет прав для выполнения этой команды.\n"
                    "Только администраторы могут использовать эту функцию."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ У вас нет прав для этого действия.",
                    show_alert=True
                )
            
            return None  # Блокируем дальнейшую обработку
        
        # Пользователь - админ, продолжаем обработку
        bot_logger.debug(f"Admin {user_id} authorized")
        
        # Добавляем флаг is_admin в данные
        data['is_admin'] = True
        
        return await handler(event, data)


class UserAuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки базовой авторизации пользователя
    
    Создает запись пользователя в БД при первом обращении
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка события и создание пользователя в БД
        """
        from database import User, get_session
        from sqlalchemy import select
        
        user = None
        telegram_user = None
        
        # Получаем Telegram пользователя
        if isinstance(event, Message):
            telegram_user = event.from_user
        elif isinstance(event, CallbackQuery):
            telegram_user = event.from_user
        
        if telegram_user is None:
            return await handler(event, data)
        
        try:
            # Проверяем существует ли пользователь в БД
            async with get_session() as session:
                result = await session.scalar(
                    select(User).where(User.telegram_id == telegram_user.id)
                )
                
                # Если пользователя нет - создаем
                if result is None:
                    user = User(
                        telegram_id=telegram_user.id,
                        username=telegram_user.username,
                        first_name=telegram_user.first_name,
                        last_name=telegram_user.last_name
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)  # Refresh чтобы получить ID
                    
                    bot_logger.info(
                        f"New user created: {telegram_user.id} "
                        f"(@{telegram_user.username or 'no_username'})"
                    )
                else:
                    user = result
                    # Обновляем данные пользователя (на случай изменений)
                    user.username = telegram_user.username
                    user.first_name = telegram_user.first_name
                    user.last_name = telegram_user.last_name
                    
                    await session.commit()
                    await session.refresh(user)  # Refresh после update
                
                # Добавляем пользователя в данные для handler'а ВНУТРИ сессии
                data['db_user'] = user
        
        except Exception as e:
            bot_logger.error(f"Error in UserAuthMiddleware: {e}", exc_info=True)
            # Продолжаем работу даже если БД недоступна
        
        return await handler(event, data)
