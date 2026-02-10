"""
Главный файл Telegram бота для обработки платежей через Cryptomus/NOWPayments
Поддерживает два режима:
- Webhook (продакшн, Railway) - aiohttp web-сервер
- Polling (локальная разработка) - fallback если WEBHOOK_URL не задан
"""
import asyncio
import hashlib
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import Config
from database import init_db, create_tables, close_db
from handlers import user_router, admin_router, admin_commands_router, callback_router
from handlers.webhook_handlers import handle_nowpayments_webhook
from services.nowpayments_service import nowpayments_service
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


async def on_startup_webhook(**kwargs):
    """
    Действия при запуске бота в режиме webhook
    """
    bot_logger.info("🚀 Starting bot in WEBHOOK mode...")
    
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
    
    # Установка webhook с секретным токеном для защиты
    config = Config()
    webhook_url = f"{config.BASE_WEBHOOK_URL}{Config.WEBHOOK_PATH}"
    webhook_secret = hashlib.sha256(Config.BOT_TOKEN.encode()).hexdigest()
    
    await bot.set_webhook(
        url=webhook_url,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
        secret_token=webhook_secret
    )
    
    bot_info = await bot.get_me()
    bot_logger.info(f"✅ Bot started successfully!")
    bot_logger.info(f"Bot username: @{bot_info.username}")
    bot_logger.info(f"Webhook URL: {webhook_url}")
    bot_logger.info(f"Admins: {Config.ADMIN_IDS}")


async def on_startup_polling():
    """
    Действия при запуске бота в режиме polling
    """
    bot_logger.info("🚀 Starting bot in POLLING mode...")
    
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
    
    # Удаление webhook при polling
    await bot.delete_webhook(drop_pending_updates=True)
    
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


async def check_payments_task():
    """
    Фоновая задача: проверка статусов платежей через NOWPayments API
    
    Работает как FALLBACK если IPN от NOWPayments не приходит.
    Каждые 60 секунд проверяет все pending инвойсы.
    """
    from services.nowpayments_service import nowpayments_service
    from services.notification_service import NotificationService
    
    # Ждём 30 секунд при старте чтобы всё инициализировалось
    await asyncio.sleep(30)
    bot_logger.info("🔄 Payment status polling task started")
    
    while True:
        try:
            await asyncio.sleep(60)  # Проверяем каждые 60 секунд
            
            # Получаем все pending инвойсы
            pending = await invoice_service.get_pending_invoices()
            
            if not pending:
                continue
            
            bot_logger.info(f"🔍 Checking {len(pending)} pending invoice(s)...")
            
            for invoice in pending:
                try:
                    # Пропускаем если нет payment_id (ещё не оплачивали)
                    if not invoice.cryptomus_invoice_id:
                        continue
                    
                    # Запрашиваем статус у NOWPayments
                    status_result = await nowpayments_service.check_payment_status(
                        str(invoice.cryptomus_invoice_id)
                    )
                    
                    if not status_result.get('success'):
                        continue
                    
                    payment_status = status_result.get('status', '')
                    
                    if status_result.get('is_paid'):
                        bot_logger.info(f"💰 POLL: Invoice {invoice.invoice_id} is PAID (status: {payment_status})")
                        
                        # Получаем инвойс с пользователем
                        invoice_data = await invoice_service.get_invoice_with_user(invoice.invoice_id)
                        if not invoice_data:
                            continue
                        
                        inv, user = invoice_data
                        
                        # Проверяем что ещё не помечен как оплаченный
                        if inv.status == 'paid':
                            continue
                        
                        # Помечаем как оплаченный
                        success = await invoice_service.mark_invoice_as_paid(
                            invoice_id=invoice.invoice_id,
                            transaction_id=str(invoice.cryptomus_invoice_id),
                            payment_method=status_result.get('currency', 'crypto')
                        )
                        
                        if success and bot:
                            bot_logger.info(f"✅ POLL: Invoice {invoice.invoice_id} marked as paid. Sending notifications...")
                            notifier = NotificationService(bot)
                            
                            try:
                                await notifier.notify_client_payment_success(invoice=inv, user=user)
                                bot_logger.info(f"✅ POLL: Client notification sent to {user.telegram_id}")
                            except Exception as e:
                                bot_logger.error(f"❌ POLL: Client notification failed: {e}")
                            
                            try:
                                await notifier.notify_admins_payment_received(invoice=inv, user=user)
                                bot_logger.info(f"✅ POLL: Admin notifications sent")
                            except Exception as e:
                                bot_logger.error(f"❌ POLL: Admin notification failed: {e}")
                
                except Exception as e:
                    bot_logger.error(f"Error checking invoice {invoice.invoice_id}: {e}")
                    continue
        
        except asyncio.CancelledError:
            bot_logger.info("Payment status polling task cancelled")
            break
        except Exception as e:
            bot_logger.error(f"Error in payment polling task: {e}", exc_info=True)


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


# ========================================
# WEBHOOK HTTP HANDLERS (aiohttp)
# ========================================

async def handle_nowpayments_ipn(request: web.Request) -> web.Response:
    """
    HTTP endpoint для NOWPayments IPN webhook
    POST /webhook/nowpayments
    """
    try:
        # Читаем тело запроса
        raw_body = await request.read()
        
        # Проверка IPN подписи (если IPN secret настроен)
        ipn_secret = Config.NOWPAYMENTS_IPN_SECRET
        if ipn_secret:
            signature = request.headers.get('x-nowpayments-sig', '')
            if not signature:
                bot_logger.warning("⚠️ NOWPayments IPN without signature - REJECTED")
                return web.json_response({'status': 'error', 'message': 'Missing signature'}, status=403)
            
            if not nowpayments_service.verify_ipn_signature(raw_body, signature):
                bot_logger.warning("⚠️ NOWPayments IPN invalid signature - REJECTED")
                return web.json_response({'status': 'error', 'message': 'Invalid signature'}, status=403)
            
            bot_logger.info("✅ IPN signature verified")
        else:
            bot_logger.warning("⚠️ NOWPAYMENTS_IPN_SECRET not set — skipping signature check")
        
        import json
        data = json.loads(raw_body)
        bot_logger.info(f"📥 NOWPayments IPN received: status={data.get('payment_status', 'unknown')}, order={data.get('order_id', '?')}")
        
        result = await handle_nowpayments_webhook(data, bot)
        
        if result.get('status') == 'ok':
            return web.json_response({'status': 'ok'}, status=200)
        else:
            return web.json_response(result, status=400)
    
    except Exception as e:
        bot_logger.error(f"Error in NOWPayments IPN handler: {e}", exc_info=True)
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)


async def handle_health(request: web.Request) -> web.Response:
    """
    Health check endpoint - Railway использует для проверки состояния сервиса
    GET /health
    """
    return web.json_response({'status': 'ok'})


async def handle_root(request: web.Request) -> web.Response:
    """
    Root endpoint
    GET /
    """
    return web.json_response({'status': 'ok'})


# ========================================
# STARTUP FUNCTIONS
# ========================================

async def run_webhook():
    """
    Запуск бота в режиме webhook с aiohttp web-сервером
    """
    global bot, dp
    
    # Создание бота
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.MARKDOWN
        )
    )
    
    # Создание диспетчера
    dp = Dispatcher()
    
    # Настройка middlewares и роутеров
    setup_middlewares(dp)
    setup_admin_middlewares()
    setup_routers(dp)
    
    # Регистрация startup/shutdown handlers
    dp.startup.register(on_startup_webhook)
    dp.shutdown.register(on_shutdown)
    
    # Создание aiohttp приложения
    app = web.Application()
    
    # Настройка webhook handler для Telegram
    # Секретный токен для защиты webhook от подделки
    webhook_secret = hashlib.sha256(Config.BOT_TOKEN.encode()).hexdigest()
    
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=webhook_secret
    )
    webhook_handler.register(app, path=Config.WEBHOOK_PATH)
    
    # Регистрация дополнительных HTTP endpoints
    app.router.add_post(Config.NOWPAYMENTS_WEBHOOK_PATH, handle_nowpayments_ipn)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_root)
    
    # Настройка aiogram webhook в aiohttp
    setup_application(app, dp, bot=bot)
    
    # Запуск фоновых задач
    async def start_background_tasks(app):
        app['invoice_expiration_task'] = asyncio.create_task(expire_invoices_task())
        app['payment_polling_task'] = asyncio.create_task(check_payments_task())
    
    async def cleanup_background_tasks(app):
        for task_name in ['invoice_expiration_task', 'payment_polling_task']:
            if task_name in app:
                app[task_name].cancel()
                try:
                    await app[task_name]
                except asyncio.CancelledError:
                    pass
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    # Запуск web-сервера
    bot_logger.info(f"🌐 Starting web server on {Config.WEB_SERVER_HOST}:{Config.WEB_SERVER_PORT}")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        host=Config.WEB_SERVER_HOST,
        port=Config.WEB_SERVER_PORT
    )
    await site.start()
    
    bot_logger.info(f"✅ Web server started on port {Config.WEB_SERVER_PORT}")
    
    # Держим сервер запущенным
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def run_polling():
    """
    Запуск бота в режиме polling (для локальной разработки)
    """
    global bot, dp
    
    # Создание бота
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.MARKDOWN
        )
    )
    
    # Создание диспетчера
    dp = Dispatcher()
    
    # Настройка middlewares и роутеров
    setup_middlewares(dp)
    setup_admin_middlewares()
    setup_routers(dp)
    
    # Регистрация startup/shutdown handlers
    dp.startup.register(on_startup_polling)
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


async def main():
    """
    Главная функция - автоматически выбирает режим работы
    """
    if Config.is_webhook_mode():
        bot_logger.info("🔔 Webhook mode detected (WEBHOOK_URL or RAILWAY_PUBLIC_DOMAIN is set)")
        await run_webhook()
    else:
        bot_logger.info("🔄 Polling mode (no WEBHOOK_URL set, local development)")
        await run_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        bot_logger.info("Bot stopped by user")
    except Exception as e:
        bot_logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
