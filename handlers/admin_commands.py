"""
Расширенные админские команды
"""
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from decimal import Decimal

from config import Config
from services.admin_service import admin_service
from services import invoice_service
from utils.validators import validate_user_id
from utils.helpers import format_currency, format_datetime
from utils.logger import log_admin_action, bot_logger


# Роутер для расширенных админских команд
admin_commands_router = Router(name="admin_commands")


@admin_commands_router.message(Command("block"))
async def cmd_block_user(message: Message):
    """Блокировка пользователя"""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "❌ Использование: `/block <user_id или @username>`\n\n"
            "Пример: `/block 123456789` или `/block @username`",
            parse_mode="Markdown"
        )
        return
    
    user_input = args[1].strip()
    is_numeric, user_id, username = validate_user_id(user_input)
    
    if not is_numeric and not username:
        await message.answer("❌ Некорректный формат ID или username")
        return
    
    # Определяем ID пользователя
    from database import get_session
    from database.models import User
    from sqlalchemy import select
    
    async with get_session() as session:
        if is_numeric:
            target_user = await session.scalar(select(User).where(User.telegram_id == user_id))
        else:
            clean_username = username.lstrip('@')
            target_user = await session.scalar(select(User).where(User.username == clean_username))
        
        if not target_user:
            await message.answer(f"❌ Пользователь {user_input} не найден")
            return
        
        target_user_id = target_user.telegram_id
        target_username = target_user.username
    
    # Проверка что не блокируем себя
    if target_user_id == message.from_user.id:
        await message.answer("❌ Вы не можете заблокировать себя")
        return
    
    # Блокируем
    success = await admin_service.block_user(target_user_id, message.from_user.id)
    
    if success:
        user_mention = f"@{target_username}" if target_username else f"ID {target_user_id}"
        await message.answer(f"✅ Пользователь {user_mention} заблокирован")
        log_admin_action(message.from_user.id, f"blocked user {target_user_id}")
    else:
        await message.answer("❌ Не удалось заблокировать пользователя (возможно уже заблокирован)")


@admin_commands_router.message(Command("unblock"))
async def cmd_unblock_user(message: Message):
    """Разблокировка пользователя"""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "❌ Использование: `/unblock <user_id или @username>`\n\n"
            "Пример: `/unblock 123456789`",
            parse_mode="Markdown"
        )
        return
    
    user_input = args[1].strip()
    is_numeric, user_id, username = validate_user_id(user_input)
    
    if not is_numeric and not username:
        await message.answer("❌ Некорректный формат ID или username")
        return
    
    # Определяем ID
    from database import get_session
    from database.models import User
    from sqlalchemy import select
    
    async with get_session() as session:
        if is_numeric:
            target_user = await session.scalar(select(User).where(User.telegram_id == user_id))
        else:
            clean_username = username.lstrip('@')
            target_user = await session.scalar(select(User).where(User.username == clean_username))
        
        if not target_user:
            await message.answer(f"❌ Пользователь {user_input} не найден")
            return
        
        target_user_id = target_user.telegram_id
        target_username = target_user.username
    
    # Разблокируем
    success = await admin_service.unblock_user(target_user_id)
    
    if success:
        user_mention = f"@{target_username}" if target_username else f"ID {target_user_id}"
        await message.answer(f"✅ Пользователь {user_mention} разблокирован")
        log_admin_action(message.from_user.id, f"unblocked user {target_user_id}")
    else:
        await message.answer("❌ Не удалось разблокировать (возможно не был заблокирован)")


@admin_commands_router.message(Command("addadmin"))
async def cmd_add_admin(message: Message):
    """Выдача админ прав"""
    # Только основной админ может добавлять других
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.answer("❌ Только главный администратор может назначать других админов")
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "❌ Использование: `/addadmin <user_id или @username>`",
            parse_mode="Markdown"
        )
        return
    
    user_input = args[1].strip()
    is_numeric, user_id, username = validate_user_id(user_input)
    
    if not is_numeric and not username:
        await message.answer("❌ Некорректный формат")
        return
    
    from database import get_session
    from database.models import User
    from sqlalchemy import select
    
    async with get_session() as session:
        if is_numeric:
            target_user = await session.scalar(select(User).where(User.telegram_id == user_id))
        else:
            clean_username = username.lstrip('@')
            target_user = await session.scalar(select(User).where(User.username == clean_username))
        
        if not target_user:
            await message.answer(f"❌ Пользователь {user_input} не найден")
            return
        
        target_user_id = target_user.telegram_id
        target_username = target_user.username
    
    success = await admin_service.add_admin(target_user_id, message.from_user.id)
    
    if success:
        user_mention = f"@{target_username}" if target_username else f"ID {target_user_id}"
        await message.answer(f"✅ Админские права выданы пользователю {user_mention}")
        log_admin_action(message.from_user.id, f"granted admin to {target_user_id}")
    else:
        await message.answer("❌ Не удалось выдать права (возможно уже админ)")


@admin_commands_router.message(Command("removeadmin"))
async def cmd_remove_admin(message: Message):
    """Снятие админ прав"""
    # Только основной админ
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.answer("❌ Только главный администратор может снимать других админов")
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "❌ Использование: `/removeadmin <user_id или @username>`",
            parse_mode="Markdown"
        )
        return
    
    user_input = args[1].strip()
    is_numeric, user_id, username = validate_user_id(user_input)
    
    if not is_numeric and not username:
        await message.answer("❌ Некорректный формат")
        return
    
    from database import get_session
    from database.models import User
    from sqlalchemy import select
    
    async with get_session() as session:
        if is_numeric:
            target_user = await session.scalar(select(User).where(User.telegram_id == user_id))
        else:
            clean_username = username.lstrip('@')
            target_user = await session.scalar(select(User).where(User.username == clean_username))
        
        if not target_user:
            await message.answer(f"❌ Пользователь {user_input} не найден")
            return
        
        target_user_id = target_user.telegram_id
        target_username = target_user.username
    
    # Нельзя снять с себя
    if target_user_id == message.from_user.id:
        await message.answer("❌ Вы не можете снять права с себя")
        return
    
    success = await admin_service.remove_admin(target_user_id, message.from_user.id)
    
    if success:
        user_mention = f"@{target_username}" if target_username else f"ID {target_user_id}"
        await message.answer(f"✅ Админские права сняты с {user_mention}")
        log_admin_action(message.from_user.id, f"removed admin from {target_user_id}")
    else:
        await message.answer("❌ Не удалось снять права")


@admin_commands_router.message(Command("users"))
async def cmd_list_users(message: Message):
    """Список пользователей"""
    args = message.text.split()
    status = args[1] if len(args) > 1 else "all"
    
    if status not in ["all", "active", "blocked", "admins"]:
        await message.answer(
            "❌ Допустимые статусы: `all`, `active`, `blocked`, `admins`",
            parse_mode="Markdown"
        )
        return
    
    users = await admin_service.get_users_list(status=status, limit=20)
    
    if not users:
        await message.answer(f"Пользователей со статусом '{status}' не найдено")
        return
    
    # Формируем список
    status_emoji = {
        "all": "👥",
        "active": "✅",
        "blocked": "🚫",
        "admins": "👑"
    }
    
    text = f"{status_emoji.get(status, '👥')} **Пользователи ({status})** - {len(users)}\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, user in enumerate(users, 1):
        username_str = f"@{user.username}" if user.username else "нет username"
        admin_badge = " 👑" if user.is_admin else ""
        blocked_badge = " 🚫" if user.is_blocked else ""
        
        text += f"{i}. {user.first_name} ({username_str}){admin_badge}{blocked_badge}\n"
        text += f"   ID: `{user.telegram_id}`\n"
        text += f"   Регистрация: {format_datetime(user.created_at, 'short')}\n\n"
    
    await message.answer(text, parse_mode="Markdown")
    log_admin_action(message.from_user.id, f"listed users ({status})")


@admin_commands_router.message(Command("admins"))
async def cmd_list_admins(message: Message):
    """Список админов"""
    admins = await admin_service.get_users_list(status="admins")
    
    if not admins:
        await message.answer("Админов не найдено")
        return
    
    text = "👑 **Администраторы** - {}\n".format(len(admins))
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, admin in enumerate(admins, 1):
        username_str = f"@{admin.username}" if admin.username else "нет username"
        is_super = " ⭐" if admin.telegram_id in Config.ADMIN_IDS else ""
        
        text += f"{i}. {admin.first_name} ({username_str}){is_super}\n"
        text += f"   ID: `{admin.telegram_id}`\n\n"
    
    await message.answer(text, parse_mode="Markdown")


@admin_commands_router.message(Command("stats"))
async def cmd_statistics(message: Message):
    """Статистика бота"""
    stats = await admin_service.get_statistics()
    
    if not stats:
        await message.answer("❌ Не удалось получить статистику")
        return
    
    text = "📊 **Статистика бота**\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    text += f"👥 **Пользователи:**\n"
    text += f"   Всего: {stats['total_users']}\n"
    text += f"   Активных: {stats['active_users']}\n"
    text += f"   Заблокировано: {stats['blocked_users']}\n"
    text += f"   Админов: {stats['admin_count']}\n\n"
    
    text += f"📋 **Инвойсы:**\n"
    text += f"   Всего: {stats['total_invoices']}\n"
    text += f"   ✅ Оплачено: {stats['paid_invoices']}\n"
    text += f"   ⏳ В ожидании: {stats['pending_invoices']}\n"
    text += f"   ❌ Отменено: {stats['cancelled_invoices']}\n\n"
    
    text += f"💰 **Финансы:**\n"
    text += f"   Общий доход: {format_currency(stats['total_revenue'], 'USD')}\n"
    text += f"   Конверсия: {stats['conversion_rate']}%\n"
    
    await message.answer(text, parse_mode="Markdown")
    log_admin_action(message.from_user.id, "viewed statistics")


@admin_commands_router.message(Command("revenue"))
async def cmd_revenue_report(message: Message):
    """Отчет по доходам"""
    args = message.text.split()
    period = args[1] if len(args) > 1 else "all"
    
    if period not in ["today", "week", "month", "all"]:
        await message.answer(
            "❌ Допустимые периоды: `today`, `week`, `month`, `all`",
            parse_mode="Markdown"
        )
        return
    
    report = await admin_service.get_revenue_report(period=period)
    
    if not report:
        await message.answer("❌ Не удалось получить отчет")
        return
    
    period_names = {
        "today": "Сегодня",
        "week": "За неделю",
        "month": "За месяц",
        "all": "За все время"
    }
    
    text = f"💵 **Доходы - {period_names[period]}**\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    text += f"💰 Общая сумма: {format_currency(report['total_revenue'], 'USD')}\n"
    text += f"📋 Инвойсов: {report['invoice_count']}\n"
    text += f"📊 Средний чек: {format_currency(report['average_amount'], 'USD')}\n"
    text += f"🏆 Популярная крипта: {report['top_currency']}\n"
    
    await message.answer(text, parse_mode="Markdown")
    log_admin_action(message.from_user.id, f"viewed revenue ({period})")


@admin_commands_router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot):
    """Рассылка сообщения всем пользователям"""
    # Только главный админ
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.answer("❌ Только главный администратор может делать рассылки")
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "❌ Использование: `/broadcast <сообщение>`\n\n"
            "Пример: `/broadcast Важное объявление для всех!`",
            parse_mode="Markdown"
        )
        return
    
    broadcast_text = args[1]
    
    # Получаем всех активных пользователей
    users = await admin_service.get_users_list(status="active", limit=1000)
    
    if not users:
        await message.answer("Нет пользователей для рассылки")
        return
    
    # Подтверждение
    await message.answer(
        f"📢 Начинаю рассылку {len(users)} пользователям...",
        parse_mode="Markdown"
    )
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"📢 **Сообщение от администратора:**\n\n{broadcast_text}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception as e:
            failed += 1
            bot_logger.warning(f"Failed to send broadcast to {user.telegram_id}: {e}")
    
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"Отправлено: {sent}\n"
        f"Не удалось: {failed}"
    )
    
    log_admin_action(message.from_user.id, f"broadcast to {sent} users")


@admin_commands_router.message(Command("notify"))
async def cmd_notify_user(message: Message, bot: Bot):
    """Отправка личного сообщения пользователю"""
    args = message.text.split(maxsplit=2)
    
    if len(args) < 3:
        await message.answer(
            "❌ Использование: `/notify <user_id> <сообщение>`\n\n"
            "Пример: `/notify 123456789 Ваш платеж обработан`",
            parse_mode="Markdown"
        )
        return
    
    user_input = args[1]
    notify_text = args[2]
    
    is_numeric, user_id, username = validate_user_id(user_input)
    
    if not is_numeric and not username:
        await message.answer("❌ Некорректный ID")
        return
    
    # Находим пользователя
    from database import get_session
    from database.models import User
    from sqlalchemy import select
    
    async with get_session() as session:
        if is_numeric:
            target_user = await session.scalar(select(User).where(User.telegram_id == user_id))
        else:
            clean_username = username.lstrip('@')
            target_user = await session.scalar(select(User).where(User.username == clean_username))
        
        if not target_user:
            await message.answer(f"❌ Пользователь {user_input} не найден")
            return
        
        target_user_id = target_user.telegram_id
    
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=f"💬 **Сообщение от администратора:**\n\n{notify_text}",
            parse_mode="Markdown"
        )
        
        await message.answer(f"✅ Сообщение отправлено пользователю {user_input}")
        log_admin_action(message.from_user.id, f"notified user {target_user_id}")
        
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить сообщение: {e}")
        bot_logger.error(f"Failed to notify user {target_user_id}: {e}")


@admin_commands_router.message(Command("cancel"))
async def cmd_cancel_invoice(message: Message):
    """Отмена инвойса"""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "❌ Использование: `/cancel <invoice_id>`\n\n"
            "Пример: `/cancel INV-1739115123`",
            parse_mode="Markdown"
        )
        return
    
    invoice_id = args[1].strip()
    
    # Отмена через invoice_service
    success = await invoice_service.cancel_invoice(invoice_id)
    
    if success:
        await message.answer(f"✅ Инвойс `{invoice_id}` отменен", parse_mode="Markdown")
        log_admin_action(message.from_user.id, f"cancelled invoice {invoice_id}")
    else:
        await message.answer(f"❌ Не удалось отменить инвойс (возможно не найден или уже оплачен)")


@admin_commands_router.message(Command("help_admin"))
async def cmd_admin_help(message: Message):
    """Справка по админским командам"""
    text = "📚 **Админские команды**\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    text += "**Управление пользователями:**\n"
    text += "`/block <user_id>` - Заблокировать пользователя\n"
    text += "`/unblock <user_id>` - Разблокировать\n"
    text += "`/users [status]` - Список пользователей\n"
    text += "   • `all` - все\n"
    text += "   • `active` - активные\n"
    text += "   • `blocked` - заблокированные\n"
    text += "   • `admins` - администраторы\n\n"
    
    text += "**Управление админами:**\n"
    text += "`/addadmin <user_id>` - Выдать права админа\n"
    text += "`/removeadmin <user_id>` - Снять права\n"
    text += "`/admins` - Список админов\n\n"
    
    text += "**Аналитика:**\n"
    text += "`/stats` - Общая статистика\n"
    text += "`/revenue [period]` - Отчет по доходам\n"
    text += "   • `today` - сегодня\n"
    text += "   • `week` - неделя\n"
    text += "   • `month` - месяц\n"
    text += "   • `all` - все время\n\n"
    
    text += "**Коммуникация:**\n"
    text += "`/broadcast <текст>` - Рассылка всем\n"
    text += "`/notify <user_id> <текст>` - Личное сообщение\n\n"
    
    text += "**Инвойсы:**\n"
    text += "`/invoice` - Создать инвойс\n"
    text += "`/cancel <invoice_id>` - Отменить инвойс\n"
    
    await message.answer(text, parse_mode="Markdown")
