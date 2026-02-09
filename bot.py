"""
Главный файл Telegram бота для обработки платежей через Cryptomus
"""
import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import Config
from database import init_db, create_tables, close_db
from handlers import user_router, admin_router, admin_commands_router, callback_router
from middlewares import (
    LoggingMiddleware,
    UserAuthMiddleware,
    AdminAuthMiddleware,
    AntiSpamMiddleware,
    ThrottlingMiddleware,
    BlockCheckMiddleware
)
from services import invoice_service
from utils.logger import bot_logger


# Глобальные объекты
bot: Bot | None = None
dp: Dispatcher | None = None


async def on_startup():
    """
    Действия при запуске бота
    """
    bot_logger.info("🚀 Starting bot...")
    
    # Валидация конфигурации
    try:
        Config.validate()
        bot_logger.info("✅ Configuration validated")
    except ValueError as e:
        bot_logger.error(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Инициализация базы данных
    try:
        await init_db()
        await create_tables()
        bot_logger.info("✅ Database initialized")
    except Exception as e:
        bot_logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
        sys.exit(1)
    
    bot_logger.info("✅ Bot started successfully!")
    bot_logger.info(f"Bot username: @{(await bot.get_me()).username}")
    bot_logger.info(f"Admins: {Config.ADMIN_IDS}")


async def on_shutdown():
    """
    Действия при остановке бота
    """
    bot_logger.info("🛑 Shutting down bot...")
    
    # Закрытие соединений с базой данных
    await close_db()
    bot_logger.info("✅ Database connections closed")
    
    # Закрытие бота
    if bot:
        await bot.session.close()
        bot_logger.info("✅ Bot session closed")
    
    bot_logger.info("✅ Bot shutdown complete")


async def expire_invoices_task():
    """
    Фоновая задача для автоматического истечения старых инвойсов
    
    Запускается каждые 5 минут и проверяет инвойсы старше 1 часа
    """
    while True:
        try:
            # Ждем 5 минут перед следующей проверкой
            await asyncio.sleep(300)  # 5 минут = 300 секунд
            
            # Истекаем старые инвойсы (старше 1 часа)
            expired_count = await invoice_service.expire_old_invoices(hours=1)
            
            if expired_count > 0:
                bot_logger.info(f"⌛️ Expired {expired_count} old invoice(s)")
        
        except asyncio.CancelledError:
            bot_logger.info("Invoice expiration task cancelled")
            break
        except Exception as e:
            bot_logger.error(f"Error in invoice expiration task: {e}", exc_info=True)


def setup_middlewares(dp: Dispatcher):
    """
    Настройка middlewares
    
    ВАЖНО: Порядок регистрации имеет значение!
    1. LoggingMiddleware - логирует всё
    2. UserAuthMiddleware - создает пользователей в БД
    3. AntiSpamMiddleware - защита от спама
    """
    # Логирование (первым - видит все запросы)
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    
    # Создание пользователей (вторым - до бизнес логики)
    dp.message.middleware(UserAuthMiddleware())
    dp.callback_query.middleware(UserAuthMiddleware())
    
    # Проверка блокировки (третьим - блокирует доступ)
    dp.message.middleware(BlockCheckMiddleware())
    dp.callback_query.middleware(BlockCheckMiddleware())
    
    # Антиспам для обычных пользователей
    # Настройки: максимум 3 запроса в секунду, блокировка на 60 секунд
    dp.message.middleware(AntiSpamMiddleware(time_window=1, max_requests=3))
    
    # Throttling для callback'ов (минимум 0.5 секунды между нажатиями)
    dp.callback_query.middleware(ThrottlingMiddleware(throttle_time=0.5))
    
    bot_logger.info("✅ Global middlewares registered")


def setup_admin_middlewares():
    """
    Настройка middlewares для админского роутера
    
    AdminAuthMiddleware защищает все команды в admin_router
    """
    # Защита админских команд
    admin_router.message.middleware(AdminAuthMiddleware())
    admin_router.callback_query.middleware(AdminAuthMiddleware())
    
    # Защита расширенных админских команд
    admin_commands_router.message.middleware(AdminAuthMiddleware())
    admin_commands_router.callback_query.middleware(AdminAuthMiddleware())
    
    bot_logger.info("✅ Admin middlewares registered")


def setup_routers(dp: Dispatcher):
    """
    Регистрация роутеров
    
    Порядок важен - первые роутеры имеют приоритет
    """
    # Админские команды (приоритет)
    dp.include_router(admin_router)
    dp.include_router(admin_commands_router)
    
    # Пользовательские команды
    dp.include_router(user_router)
    
    # Callback'ы (последними - как fallback)
    dp.include_router(callback_router)
    
    bot_logger.info("✅ Routers registered")


async def main():
    """
    Главная функция запуска бота
    """
    global bot, dp
    
    # Создание бота с настройками по умолчанию
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.MARKDOWN
        )
    )
    
    # Создание диспетчера
    dp = Dispatcher()
    
    # Настройка middlewares
    setup_middlewares(dp)
    setup_admin_middlewares()
    
    # Регистрация роутеров
    setup_routers(dp)
    
    # Регистрация startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Запуск фоновой задачи для истечения инвойсов
    expiration_task = asyncio.create_task(expire_invoices_task())
    
    try:
        # Запуск polling
        bot_logger.info("Starting polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    except KeyboardInterrupt:
        bot_logger.info("Received interrupt signal")
    finally:
        # Отмена фоновой задачи
        expiration_task.cancel()
        try:
            await expiration_task
        except asyncio.CancelledError:
            pass
        
        # Вызов shutdown handlers
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        bot_logger.info("Bot stopped by user")
    except Exception as e:
        bot_logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
