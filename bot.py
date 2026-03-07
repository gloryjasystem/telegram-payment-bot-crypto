"""
Главный файл Telegram бота для обработки платежей через NOWPayments
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

# Временный кэш для передачи email из WebApp в Lava-вебхук
# Lava.top не возвращает email в payload вебхука, поэтому храним его здесь
# ключ: invoice_id, значение: email
_lava_email_cache: dict[str, str] = {}


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
            
            # Истекаем старые инвойсы (старше 24 часов) и редактируем их сообщения
            expired_count = await invoice_service.expire_old_invoices(bot=bot)
            
            if expired_count > 0:
                bot_logger.info(f"⌛️ Expired {expired_count} old invoice(s)")
                # Уведомляем администраторов о истёкших инвойсах
                if bot:
                    from services.notification_service import NotificationService
                    notifier = NotificationService(bot)
                    try:
                        await notifier.broadcast_to_admins(
                            f"⌛️ *Истекли инвойсы*\n\n"
                            f"За последние 5 минут истёк срок у *{expired_count}* инвойс(ов).\n"
                            f"Клиенты уже уведомлены автоматически."
                        )
                    except Exception as e:
                        bot_logger.error(f"Failed to notify admins about expired invoices: {e}")
        
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
                    if not invoice.external_invoice_id:
                        continue
                    
                    # Запрашиваем статус у NOWPayments
                    status_result = await nowpayments_service.check_payment_status(
                        str(invoice.external_invoice_id)
                    )
                    
                    if not status_result.get('success'):
                        continue
                    
                    payment_status = status_result.get('status', '')
                    
                    if status_result.get('is_paid'):
                        bot_logger.info(f"💰 POLL: Invoice {invoice.invoice_id} is PAID (status: {payment_status})")
                        
                        # Получаем СВЕЖИЕ данные инвойса с пользователем (защита от race condition)
                        invoice_data = await invoice_service.get_invoice_with_user(invoice.invoice_id)
                        if not invoice_data:
                            continue
                        
                        inv, user = invoice_data
                        
                        # Проверяем что ещё не помечен как оплаченный (свежие данные из БД)
                        if inv.status == 'paid':
                            bot_logger.info(f"⏭ POLL: Invoice {invoice.invoice_id} already paid (likely by webhook). Skipping.")
                            continue
                        
                        crypto_currency = status_result.get('currency', 'crypto')
                        
                        # Помечаем как оплаченный
                        success = await invoice_service.mark_invoice_as_paid(
                            invoice_id=invoice.invoice_id,
                            transaction_id=str(invoice.external_invoice_id),
                            payment_category='crypto',
                            payment_provider='nowpayments',
                            payment_method=crypto_currency
                        )
                        
                        if success and bot:
                            # Обновляем локальный объект инвойса
                            from datetime import datetime
                            inv.status = 'paid'
                            inv.paid_at = datetime.utcnow()
                            
                            bot_logger.info(f"✅ POLL: Invoice {invoice.invoice_id} marked as paid. Sending notifications...")
                            notifier = NotificationService(bot)
                            
                            try:
                                await notifier.notify_client_payment_success(invoice=inv, user=user)
                                bot_logger.info(f"✅ POLL: Client notification sent to {user.telegram_id}")
                            except Exception as e:
                                bot_logger.error(f"❌ POLL: Client notification failed: {e}")
                            
                            try:
                                await notifier.notify_admins_payment_received(invoice=inv, user=user, payment_method=crypto_currency)
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

        # Проверка IPN подписи (предупреждение, но NOT блокируем — иначе платёж не доходит)
        ipn_secret = Config.NOWPAYMENTS_IPN_SECRET
        if ipn_secret:
            signature = request.headers.get('x-nowpayments-sig', '')
            if not signature:
                bot_logger.warning("⚠️ NOWPayments IPN: no x-nowpayments-sig header — proceeding anyway")
            else:
                is_valid = nowpayments_service.verify_ipn_signature(raw_body, signature)
                if not is_valid:
                    bot_logger.warning("⚠️ NOWPayments IPN: signature mismatch — proceeding anyway (warn-only)")
                else:
                    bot_logger.info("✅ NOWPayments IPN signature verified")
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
# CARD PAYMENT HANDLERS
# ========================================

_RATE_LIMIT_STORE: dict = {}
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 60


def _get_custom_tier(amount_usd: float) -> dict:
    """
    Находит наиболее подходящий тир для данной цены.
    Приоритет: точное совпадение → ближайший вверх (округляем до шага $10) → максимальный.
    Возвращает {offer_id, price_rub} или {} если офферов нет.
    """
    tiers = Config.LAVA_CUSTOM_TIERS
    if not tiers:
        return {}

    # До $1.00 включительно — всегда тестовая карточка ($0.65)
    if amount_usd <= 1.0 and 0.65 in tiers:
        return tiers[0.65]

    target = int(round(amount_usd))
    # 1. Точное совпадение
    if target in tiers:
        return tiers[target]
    # 2. Ближайший тир >= цены (округляем вверх до шага $10)
    step = 10
    rounded_up = ((target + step - 1) // step) * step
    if rounded_up in tiers:
        return tiers[rounded_up]
    # 3. Максимальный доступный
    best = max(tiers.keys())
    return tiers[best]

def _check_rate_limit(ip: str) -> bool:
    """Проверяет rate limit. Возвращает True если запрос разрешён."""
    import time as _time
    now = _time.time()
    
    # Чистим старые записи (раз в 100 запросов)
    if len(_RATE_LIMIT_STORE) > 500:
        expired = [k for k, v in _RATE_LIMIT_STORE.items() if not v or v[-1] < now - _RATE_LIMIT_WINDOW]
        for k in expired:
            del _RATE_LIMIT_STORE[k]
    
    timestamps = _RATE_LIMIT_STORE.get(ip, [])
    # Убираем старые
    timestamps = [t for t in timestamps if t > now - _RATE_LIMIT_WINDOW]
    
    if len(timestamps) >= _RATE_LIMIT_MAX:
        _RATE_LIMIT_STORE[ip] = timestamps
        return False
    
    timestamps.append(now)
    _RATE_LIMIT_STORE[ip] = timestamps
    return True

async def handle_create_card_payment(request: web.Request) -> web.Response:
    """
    API endpoint для создания карточного платежа из Mini App
    POST /api/create-card-payment
    Body: {invoice_id, method, email, amount_usd, amount_rub, service}
    """
    # Rate limiting: 5 req / 60s per IP
    client_ip = request.remote or request.headers.get('X-Forwarded-For', 'unknown')
    if not _check_rate_limit(client_ip):
        bot_logger.warning(f"🚫 Rate limit exceeded for {client_ip}")
        return web.json_response(
            {'success': False, 'error': 'Too many requests. Please wait and try again.'},
            status=429
        )
    
    try:
        import json
        from services.card_payment_service import card_payment_service
        
        data = await request.json()
        bot_logger.info(f"📥 Card payment request: {data}")
        
        invoice_id = data.get('invoice_id', '')
        method = data.get('method', '')  # 'ru' or 'international'
        email = data.get('email', '')
        amount_usd = float(data.get('amount_usd', 0))
        amount_rub = float(data.get('amount_rub', 0))
        service = data.get('service', 'Оплата услуги')
        
        if not invoice_id or not method or not email:
            return web.json_response(
                {'success': False, 'error': 'Missing required fields'},
                status=400
            )
        
        if method == 'ru':
            # Lava.top: определяем тир и offer_id
            tier_url = ''
            offer_id = ''
            try:
                inv = await invoice_service.get_invoice_by_id(invoice_id)
                if inv and inv.service_key:
                    tier_url = Config.LAVA_PRODUCT_MAP.get(inv.service_key, '')
                if not tier_url:
                    tier = _get_custom_tier(amount_usd)
                    tier_url = tier.get('url', '')
                    offer_id = tier.get('offer_id', '')
                    if tier_url and not offer_id:
                        # Извлекаем offer_id из URL: .../products/{product_id}/{offer_id}
                        parts = tier_url.rstrip('/').split('/')
                        offer_id = parts[-1] if len(parts) >= 2 else ''
                    if tier_url:
                        bot_logger.info(f"🔍 Custom tier fallback: ${amount_usd} → {tier_url[:60]}")
                elif not offer_id:
                    parts = tier_url.rstrip('/').split('/')
                    offer_id = parts[-1] if len(parts) >= 2 else ''
            except Exception as _e:
                bot_logger.warning(f"Could not load tier for {invoice_id}: {_e}")

            if not tier_url and not offer_id:
                return web.json_response({
                    'success': False,
                    'error': 'Для этой услуги не задан URL в lava_products.json.'
                }, status=400)

            # ── Сначала пробуем Lava V3 API (дает webhook → автозакрытие WebApp + уведомления) ──
            if offer_id and Config.LAVA_API_KEY:
                from services.card_payment_service import card_payment_service as _cps
                lava_result = await _cps.create_lava_payment(
                    invoice_id=invoice_id,
                    offer_id=offer_id,
                    amount_rub=amount_rub,
                    email=email,
                    description=service,
                    currency="USD",  # TODO: вернуть "RUB" для продакшена
                )
                if lava_result.get('success') and lava_result.get('payment_url'):
                    lava_payment_id = lava_result.get('payment_id', '')
                    if lava_payment_id:
                        await invoice_service.set_external_invoice_id(invoice_id, lava_payment_id)
                        bot_logger.info(f"💾 Saved Lava contractId={lava_payment_id} for {invoice_id}")
                    # Сохраняем email в кэше — Lava webhook его не возвращает
                    if email:
                        _lava_email_cache[invoice_id] = email
                    bot_logger.info(f"✅ Lava.top V3 invoice created for {invoice_id}: {lava_result['payment_url'][:80]}")
                    return web.json_response({
                        'success': True,
                        'payment_url': lava_result['payment_url']
                    })

                else:
                    bot_logger.warning(f"⚠️ Lava V3 failed ({lava_result.get('error')}), fallback to direct redirect")

            # ── Fallback: прямой редирект (без webhook) ──
            if not tier_url:
                return web.json_response({
                    'success': False,
                    'error': 'Для этой услуги не задан URL.'
                }, status=400)

            bot_logger.info(f"✅ Lava.top direct redirect: {tier_url[:80]}")
            import urllib.parse as _up
            params = _up.urlencode({'currency': 'RUB', 'email': email})
            separator = '&' if '?' in tier_url else '?'
            return web.json_response({
                'success': True,
                'payment_url': f"{tier_url}{separator}{params}"
            })


        # WayForPay — иностранный банк, доллары
        from services.card_payment_service import card_payment_service as _wp
        result = await _wp.create_waypay_payment(
            invoice_id=invoice_id,
            amount_usd=amount_usd,
            email=email,
            description=service
        )

        if result.get('success'):
            bot_logger.info(f"✅ WayForPay payment created: {result.get('payment_url', '')[:80]}")
            return web.json_response({
                'success': True,
                'payment_url': result['payment_url']
            })
        else:
            bot_logger.warning(f"⚠️ WayForPay failed: {result.get('error')}")
            return web.json_response({
                'success': False,
                'error': result.get('error', 'Payment creation failed')
            }, status=400)

    
    except Exception as e:
        bot_logger.error(f"Error in card payment handler: {e}", exc_info=True)
        return web.json_response(
            {'success': False, 'error': str(e)},
            status=500
        )


async def handle_lava_webhook(request: web.Request) -> web.Response:
    """
    Webhook endpoint для Lava.top V3
    POST /webhook/lava
    """
    try:
        import json
        from services.card_payment_service import card_payment_service
        from services.notification_service import NotificationService

        raw_body = await request.read()

        # ── Верификация webhook secret ──────────────────────────────
        expected_secret = Config.LAVA_WEBHOOK_SECRET
        if expected_secret:
            # Lava.top "API key вашего сервиса" может слать ключ в разных заголовках
            auth_header = request.headers.get('Authorization', '')
            x_api_key   = request.headers.get('X-Api-Key', '')
            x_lava_sig  = request.headers.get('X-Lava-Signature', '')

            received_key = (
                auth_header.replace('Bearer ', '').strip()
                or x_api_key.strip()
                or x_lava_sig.strip()
            )

            if received_key and received_key != expected_secret:
                bot_logger.warning(
                    f"🚫 Lava webhook: invalid API key — rejecting. "
                    f"Got headers: Auth='{auth_header[:12]}...' "
                    f"X-Api-Key='{x_api_key[:12]}...' "
                    f"X-Lava-Sig='{x_lava_sig[:12]}...'"
                )
                return web.Response(status=403, text='Forbidden')
            elif not received_key:
                bot_logger.warning("🚫 Lava webhook: no API key in any header — rejecting")
                return web.Response(status=403, text='Forbidden')
        else:
            bot_logger.warning("⚠️ LAVA_WEBHOOK_SECRET not set — skipping secret check")


        data = json.loads(raw_body)
        bot_logger.info(f"📥 Lava.top webhook received: {data}")

        # ── Извлекаем статус и order_id ────────────────────────────
        status = data.get('status', '')
        # V3 API: наш invoice_id может быть в metadata, orderId или order_id
        order_id = (
            data.get('metadata', '')
            or data.get('orderId', '')
            or data.get('order_id', '')
        )
        # Если не нашли — ищем по contractId (Lava V3 webhook)
        if not order_id:
            contract_id = data.get('contractId', '')
            if contract_id:
                order_id = await invoice_service.get_invoice_by_external_id(contract_id)
                if order_id:
                    bot_logger.info(f"✅ Lava webhook: found invoice {order_id} by contractId={contract_id}")
        client_email = (
            data.get('email')
            or data.get('buyer_email')
            or data.get('buyerEmail', '')
        )

        if status not in ('success', 'completed', 'paid'):
            bot_logger.info(f"ℹ️ Lava webhook: status={status} — nothing to do")
            return web.json_response({'status': 'ok'})

        # ── Если order_id не пришёл — ищем инвойс по сумме ────────
        if not order_id:
            bot_logger.warning(
                "⚠️ Lava webhook: no order_id in payload — trying to find invoice by amount"
            )
            # Lava.top может слать сумму в разных полях
            amount_paid = float(
                data.get('amount')
                or data.get('sum')
                or data.get('total', 0)
                or 0
            )
            if amount_paid > 0:
                order_id = await invoice_service.find_pending_lava_invoice_by_amount(
                    amount_rub=amount_paid
                )
            if not order_id:
                bot_logger.error(
                    f"❌ Lava webhook: cannot identify invoice "
                    f"(no order_id, amount={amount_paid}). "
                    f"Use /mark_paid <invoice_id> to confirm manually."
                )
                # Возвращаем 200 чтобы Lava не ретраила
                return web.json_response({'status': 'ok'})

        # ── Проверяем, не обработан ли уже ────────────────────────
        existing = await invoice_service.get_invoice_by_id(order_id)
        if existing and existing.status == 'paid':
            bot_logger.info(f"⏭ Lava webhook: invoice {order_id} already paid")
            return web.json_response({'status': 'ok'})

        # Извлекаем Lava transaction ID
        lava_invoice_id = str(data.get('id', '') or data.get('invoice_id', ''))

        # ── Помечаем инвойс как оплаченный ────────────────────────
        # Lava не шлёт email в webhook — берём его из кэша (email был сохранён при создании)
        effective_email = client_email or _lava_email_cache.pop(order_id, None)
        success = await invoice_service.mark_invoice_as_paid(
            invoice_id=order_id,
            transaction_id=lava_invoice_id or order_id,
            payment_category='card_ru',
            payment_provider='lava',
            payment_method='card',
            client_email=effective_email or None
        )


        if success and bot:
            invoice_data = await invoice_service.get_invoice_with_user(order_id)
            if invoice_data:
                inv, user = invoice_data
                notifier = NotificationService(bot)
                try:
                    await notifier.notify_client_payment_success(invoice=inv, user=user)
                    await notifier.notify_admins_payment_received(
                        invoice=inv, user=user, payment_method='card_ru_lava'
                    )
                    bot_logger.info(f"✅ Lava payment confirmed for {order_id}")
                except Exception as e:
                    bot_logger.error(f"Notification error after Lava payment: {e}")
        elif not success:
            bot_logger.error(f"❌ Failed to mark invoice {order_id} as paid")

        return web.json_response({'status': 'ok'})

    except Exception as e:
        bot_logger.error(f"Error in Lava webhook: {e}", exc_info=True)
        return web.json_response({'status': 'error'}, status=500)



async def handle_waypay_webhook(request: web.Request) -> web.Response:
    """
    Webhook endpoint для WayForPay
    POST /webhook/waypay
    """
    try:
        import json
        from services.card_payment_service import card_payment_service
        from services.notification_service import NotificationService
        
        data = await request.json()
        bot_logger.info(f"📥 WayForPay webhook: {data}")
        
        # Проверка подписи
        if not card_payment_service.verify_waypay_webhook(data):
            bot_logger.warning("🚫 WayForPay webhook signature mismatch — rejecting")
            return web.Response(status=403, text='Forbidden')
        
        transaction_status = data.get('transactionStatus', '')
        order_ref = data.get('orderReference', '')
        
        # Extract original invoice_id (remove _ts_ timestamp suffix)
        invoice_id = order_ref.split('_ts_')[0] if '_ts_' in order_ref else order_ref
        
        if transaction_status == 'Approved' and invoice_id:
            # Извлекаем email клиента из webhook-данных
            client_email = data.get('email') or data.get('clientEmail', '')
            
            # Извлекаем чистый transaction_id (только timestamp, без INV-xxx_ts_ префикса)
            clean_transaction_id = order_ref.split('_ts_')[1] if '_ts_' in order_ref else order_ref
            
            success = await invoice_service.mark_invoice_as_paid(
                invoice_id=invoice_id,
                transaction_id=clean_transaction_id,
                payment_category='card_int',
                payment_provider='wayforpay',
                payment_method='card',
                client_email=client_email or None
            )
            
            if success and bot:
                invoice_data = await invoice_service.get_invoice_with_user(invoice_id)
                if invoice_data:
                    inv, user = invoice_data
                    from datetime import datetime
                    inv.status = 'paid'
                    inv.paid_at = datetime.utcnow()
                    
                    notifier = NotificationService(bot)
                    try:
                        await notifier.notify_client_payment_success(invoice=inv, user=user)
                        await notifier.notify_admins_payment_received(invoice=inv, user=user, payment_method='card_int')
                        bot_logger.info(f"✅ WayForPay payment confirmed for {order_ref}")
                    except Exception as e:
                        bot_logger.error(f"Notification error after WayForPay payment: {e}")
            
            # WayForPay требует ответ определённого формата
            import time
            return web.json_response({
                'orderReference': order_ref,
                'status': 'accept',
                'time': int(time.time()),
                'signature': ''  # Подпись ответа
            })
        
        return web.json_response({'status': 'ok'})
    
    except Exception as e:
        bot_logger.error(f"Error in WayForPay webhook: {e}", exc_info=True)
        return web.json_response({'status': 'error'}, status=500)


async def handle_payment_status(request: web.Request) -> web.Response:
    """
    GET /api/payment-status?invoice_id=INV-XXXXX
    WebApp polling endpoint — возвращает статус инвойса.
    """
    invoice_id = request.rel_url.query.get('invoice_id', '').strip()
    if not invoice_id:
        return web.json_response({'error': 'invoice_id required'}, status=400)
    try:
        inv = await invoice_service.get_invoice_by_id(invoice_id)
        if not inv:
            return web.json_response({'status': 'not_found', 'paid': False})
        return web.json_response({
            'status': inv.status,
            'paid': inv.status == 'paid'
        })
    except Exception as e:
        bot_logger.error(f"payment-status error: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def handle_waypay_test_success(request: web.Request) -> web.Response:
    """
    TEST ONLY: Simulates a successful WayForPay payment.
    GET /test/waypay-success?invoice_id=INV-xxx&amount=150&email=test@test.com&service=...
    """
    if not Config.WAYPAY_TEST_MODE:
        return web.json_response({'error': 'Test mode is disabled'}, status=403)
    
    try:
        from services.notification_service import NotificationService
        
        inv_id = request.query.get('invoice_id', '')
        amount = request.query.get('amount', '0')
        email = request.query.get('email', '')
        service = request.query.get('service', '')
        
        bot_logger.info(f"🧪 TEST: Simulating successful payment for {inv_id}")
        
        if inv_id:
            # Mark invoice as paid
            success = await invoice_service.mark_invoice_as_paid(
                invoice_id=inv_id,
                transaction_id=f'TEST-{inv_id}',
                payment_category='card_int',
                payment_provider='wayforpay',
                payment_method='card',
                client_email=email or None
            )
            
            if success and bot:
                invoice_data = await invoice_service.get_invoice_with_user(inv_id)
                if invoice_data:
                    inv, user = invoice_data
                    from datetime import datetime
                    inv.status = 'paid'
                    inv.paid_at = datetime.utcnow()
                    
                    notifier = NotificationService(bot)
                    try:
                        await notifier.notify_client_payment_success(invoice=inv, user=user)
                        await notifier.notify_admins_payment_received(invoice=inv, user=user, payment_method='card_int')
                        bot_logger.info(f"✅ TEST: Payment confirmed + notifications sent for {inv_id}")
                    except Exception as e:
                        bot_logger.error(f"TEST: Notification error: {e}")
        
        # Return a simple HTML page
        html = f"""
        <html><head><meta charset="utf-8"><title>Тестовая оплата</title>
        <style>body{{font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f0fdf4;}}
        .card{{background:white;border-radius:16px;padding:40px;box-shadow:0 4px 24px rgba(0,0,0,0.08);text-align:center;max-width:400px;}}
        h1{{color:#16a34a;font-size:24px;}}p{{color:#64748b;font-size:14px;}}</style></head>
        <body><div class="card">
        <h1>✅ Тестовая оплата успешна!</h1>
        <p><b>Инвойс:</b> {inv_id}</p>
        <p><b>Сумма:</b> {amount} USD</p>
        <p><b>Email:</b> {email}</p>
        <p><b>Услуга:</b> {service}</p>
        <p style="margin-top:20px;color:#16a34a;">Инвойс помечен как оплаченный.<br>Уведомления отправлены.</p>
        </div></body></html>
        """
        return web.Response(text=html, content_type='text/html')
    
    except Exception as e:
        bot_logger.error(f"Error in test payment handler: {e}", exc_info=True)
        return web.json_response({'error': str(e)}, status=500)


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
    
    # Карточные платежи: API + вебхуки
    app.router.add_post('/api/create-card-payment', handle_create_card_payment)
    app.router.add_post(Config.LAVA_WEBHOOK_PATH, handle_lava_webhook)
    app.router.add_post(Config.WAYPAY_WEBHOOK_PATH, handle_waypay_webhook)
    app.router.add_get('/api/payment-status', handle_payment_status)
    
    # Test mode endpoint — DISABLED in production for security
    # To test payments use /mark_paid <invoice_id> admin command instead
    if Config.WAYPAY_TEST_MODE:
        bot_logger.warning("⚠️ WAYPAY_TEST_MODE is enabled — test endpoint is intentionally disabled for security. Use /mark_paid instead.")
    
    # Статические файлы для WebApp Mini App
    import os
    webapp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webapp')
    if os.path.isdir(webapp_dir):
        app.router.add_static('/webapp/', webapp_dir)
        bot_logger.info(f"📱 WebApp Mini App served from /webapp/")
    
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
