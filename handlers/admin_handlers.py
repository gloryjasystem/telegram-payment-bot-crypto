"""
Обработчики админских команд
"""
from decimal import Decimal
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.models import User
from states import InvoiceCreationStates
from services import invoice_service, notification_service
from keyboards import (
    get_invoice_preview_keyboard,
    get_fsm_cancel_keyboard,
    parse_invoice_callback
)
from utils.validators import validate_user_id, validate_amount, validate_service_description
from utils.helpers import format_currency, escape_markdown
from utils.logger import log_admin_action, bot_logger


# Создаем роутер для админских команд
# Этот роутер будет защищен AdminAuthMiddleware
admin_router = Router(name="admin")


@admin_router.message(Command("invoice"))
async def cmd_invoice_start(message: Message, state: FSMContext):
    """
    Начало процесса создания инвойса
    
    Запускает FSM для пошагового ввода данных:
    1. User ID клиента
    2. Сумма
    3. Описание услуги
    4. Предпросмотр и подтверждение
    """
    log_admin_action(message.from_user.id, "started invoice creation")
    
    # Устанавливаем первое состояние FSM
    await state.set_state(InvoiceCreationStates.WaitingForUserId)
    
    await message.answer(
        "📝 **Создание инвойса**\n\n"
        "**Шаг 1/3:** Введите Telegram ID или @username клиента:\n\n"
        "_Пример: 123456789 или @username_",
        reply_markup=get_fsm_cancel_keyboard(),
        parse_mode="Markdown"
    )


@admin_router.message(InvoiceCreationStates.WaitingForUserId)
async def process_user_id(message: Message, state: FSMContext):
    """
    Обработка User ID клиента (шаг 1/3)
    """
    user_input = message.text.strip()
    
    # Валидация User ID
    is_numeric, user_id, username = validate_user_id(user_input)
    
    if not is_numeric and not username:
        await message.answer(
            "❌ Некорректный формат.\n\n"
            "Введите числовой Telegram ID или @username:\n"
            "_Пример: 123456789 или @username_",
            parse_mode="Markdown"
        )
        return
    
    # Поиск пользователя в БД
    from database import get_session
    from sqlalchemy import select
    
    try:
        async with get_session() as session:
            if is_numeric:
                # Поиск по Telegram ID
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id)
                )
            else:
                # Поиск по username (убираем @ если есть)
                clean_username = username.lstrip('@')
                user = await session.scalar(
                    select(User).where(User.username == clean_username)
                )
            
            if not user:
                await message.answer(
                    f"❌ Пользователь {user_input} не найден в базе данных.\n\n"
                    "Возможные причины:\n"
                    "• Пользователь еще не запускал бота (/start)\n"
                    "• Неверный ID или username\n\n"
                    "Попросите пользователя сначала запустить бота, затем попробуйте снова.",
                    parse_mode="Markdown"
                )
                return
            
            # Сохраняем данные пользователя в FSM
            await state.update_data(
                target_user_id=user.telegram_id,
                target_user_username=user.username,
                target_user_first_name=user.first_name,
                target_db_id=user.id
            )
    
    except Exception as e:
        bot_logger.error(f"Error finding user: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при поиске пользователя. Попробуйте еще раз."
        )
        return
    
    # Переход к следующему шагу
    await state.set_state(InvoiceCreationStates.WaitingForAmount)
    
    user_mention = f"@{user.username}" if user.username else f"ID {user.telegram_id}"
    
    await message.answer(
        f"✅ Пользователь найден: {user.first_name} ({user_mention})\n\n"
        f"**Шаг 2/3:** Введите сумму платежа в USD:\n\n"
        f"_Пример: 150 или 150.50_\n"
        f"_Максимум: $999,999.99_",
        parse_mode="Markdown"
    )


@admin_router.message(InvoiceCreationStates.WaitingForAmount)
async def process_amount(message: Message, state: FSMContext):
    """
    Обработка суммы платежа (шаг 2/3)
    """
    amount_str = message.text.strip()
    
    # Валидация суммы
    is_valid, amount, error_msg = validate_amount(amount_str)
    
    if not is_valid:
        await message.answer(error_msg)
        return
    
    # Сохраняем сумму
    await state.update_data(amount=amount)
    
    # Переход к следующему шагу
    await state.set_state(InvoiceCreationStates.WaitingForDescription)
    
    await message.answer(
        f"✅ Сумма: {format_currency(amount, 'USD')}\n\n"
        f"**Шаг 3/3:** Введите описание услуги:\n\n"
        f"_Минимум 10 символов, максимум 500_\n"
        f"_Пример: Размещение рекламы на 7 дней в топ-разделе_",
        parse_mode="Markdown"
    )


@admin_router.message(InvoiceCreationStates.WaitingForDescription)
async def process_description(message: Message, state: FSMContext):
    """
    Обработка описания услуги (шаг 3/3)
    """
    description = message.text.strip()
    
    # Валидация описания
    is_valid, error_msg = validate_service_description(description)
    
    if not is_valid:
        await message.answer(error_msg)
        return
    
    # Сохраняем описание
    await state.update_data(description=description)
    
    # Переход к предпросмотру
    await state.set_state(InvoiceCreationStates.PreviewInvoice)
    
    # Получаем все данные из FSM
    data = await state.get_data()
    
    target_user_id = data['target_user_id']
    target_username = data.get('target_user_username')
    target_first_name = data.get('target_user_first_name', 'Unknown')
    amount = data['amount']
    
    user_mention = f"@{target_username}" if target_username else f"ID {target_user_id}"
    
    # Формируем предпросмотр (все динамические части экранируем для MarkdownV2)
    preview_text = f"""
📋 *Предпросмотр инвойса*

👤 *Клиент:* {escape_markdown(target_first_name)} \\({escape_markdown(user_mention)}\\)
💰 *Сумма:* {escape_markdown(format_currency(amount, 'USD'))}
📝 *Описание:* {escape_markdown(description)}

Подтвердить создание и отправку инвойса клиенту?
"""
    
    await message.answer(
        preview_text,
        reply_markup=get_invoice_preview_keyboard("preview"),
        parse_mode="MarkdownV2"
    )


@admin_router.callback_query(F.data.startswith("confirm_invoice:"))
async def confirm_invoice_creation(callback: CallbackQuery, state: FSMContext):
    """
    Подтверждение создания инвойса
    """
    # Получаем данные из FSM
    data = await state.get_data()
    
    if not data:
        await callback.answer("❌ Данные не найдены. Начните создание заново.", show_alert=True)
        return
    
    target_user_id = data['target_user_id']
    amount = data['amount']
    description = data['description']
    admin_id = callback.from_user.id
    
    # Создаем инвойс через сервис
    try:
        invoice = await invoice_service.create_invoice(
            user_id=target_user_id,
            amount=Decimal(str(amount)),
            service_description=description,
            admin_id=admin_id,
            currency="USD"
        )
        
        if not invoice:
            await callback.answer("❌ Ошибка создания инвойса", show_alert=True)
            await callback.message.answer(
                "❌ Не удалось создать инвойс. Проверьте логи и попробуйте снова."
            )
            await state.clear()
            return
        
        # Получаем пользователя для отправки
        from database import get_session
        from sqlalchemy import select
        
        async with get_session() as session:
            user = await session.scalar(
                select(User).where(User.telegram_id == target_user_id)
            )
        
        # Отправляем инвойс клиенту
        from aiogram import Bot
        bot: Bot = callback.bot
        
        # Создаем временный notification_service
        from services import NotificationService
        notif_service = NotificationService(bot)
        
        await notif_service.send_invoice_to_client(invoice, user)
        
        # Уведомляем админа об успехе
        await notif_service.notify_admins_invoice_created(invoice, user, admin_id)
        
        # Удаляем кнопки из предпросмотра
        await callback.message.edit_reply_markup(reply_markup=None)
        
        await callback.answer("✅ Инвойс создан и отправлен!", show_alert=False)
        
        # Очищаем FSM
        await state.clear()
        
        log_admin_action(
            admin_id,
            f"created and sent invoice {invoice.invoice_id} to user {target_user_id}"
        )
    
    except Exception as e:
        bot_logger.error(f"Error creating invoice: {e}", exc_info=True)
        await callback.answer("❌ Ошибка создания инвойса", show_alert=True)
        await callback.message.answer(
            "❌ Произошла ошибка при создании инвойса. Попробуйте снова."
        )
        await state.clear()


@admin_router.callback_query(F.data.startswith("cancel_invoice:"))
async def cancel_invoice_creation(callback: CallbackQuery, state: FSMContext):
    """
    Отмена создания инвойса
    """
    await state.clear()
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Создание инвойса отменено.")
    
    await callback.answer("Отменено", show_alert=False)
    
    log_admin_action(callback.from_user.id, "cancelled invoice creation")


@admin_router.callback_query(F.data == "cancel_fsm")
async def cancel_fsm(callback: CallbackQuery, state: FSMContext):
    """
    Отмена процесса FSM через кнопку
    """
    await state.clear()
    
    await callback.message.answer("❌ Создание инвойса отменено.")
    await callback.answer("Отменено", show_alert=False)
    
    log_admin_action(callback.from_user.id, "cancelled FSM via button")


