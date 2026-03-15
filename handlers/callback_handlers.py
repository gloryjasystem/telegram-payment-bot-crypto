"""
Обработчики callback запросов (inline кнопок)
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from services import invoice_service, payment_service
from utils.logger import bot_logger, log_user_action
from utils.helpers import format_currency, format_datetime


# Создаем роутер для callback'ов
callback_router = Router(name="callbacks")


@callback_router.callback_query(F.data == "admin_help_invoice")
async def callback_admin_help_invoice(callback: CallbackQuery):
    """
    Помощь по созданию инвойса для админа
    """
    help_text = """
📝 **Инструкция по созданию инвойса**

1. Используйте команду `/invoice`
2. Введите Telegram ID или @username клиента
3. Введите сумму в USD (например: 150 или 150.50)
4. Введите описание услуги (минимум 10 символов)
5. Проверьте предпросмотр и подтвердите

**Требования:**
• Клиент должен запустить бота (/start) до создания инвойса
• Сумма: от $0.01 до $999,999.99
• Описание: от 10 до 500 символов

**Важно:**
• Инвойс действует 1 час
• После оплаты вы получите уведомление
• Клиент может оплатить криптовалютой
"""
    
    await callback.answer()
    await callback.message.answer(help_text, parse_mode="Markdown")


@callback_router.callback_query(F.data == "admin_help_stats")
async def callback_admin_help_stats(callback: CallbackQuery):
    """
    Помощь по статистике (заглушка для будущей функции)
    """
    await callback.answer(
        "📊 Функция статистики находится в разработке",
        show_alert=True
    )


@callback_router.callback_query(F.data.startswith("view_invoice:"))
async def callback_view_invoice(callback: CallbackQuery):
    """
    Просмотр деталей инвойса
    """
    # Парсим invoice_id из callback data
    from keyboards import parse_invoice_callback
    
    result = parse_invoice_callback(callback.data)
    if not result:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return
    
    action, invoice_id = result
    
    # Получаем инвойс с пользователем
    invoice_data = await invoice_service.get_invoice_with_user(invoice_id)
    
    if not invoice_data:
        await callback.answer("❌ Инвойс не найден", show_alert=True)
        return
    
    invoice, user = invoice_data
    
    # Формируем детальную информацию
    user_mention = f"@{user.username}" if user.username else f"ID {user.telegram_id}"
    
    status_emoji = {
        "pending": "⏳",
        "paid": "✅",
        "expired": "⌛️",
        "cancelled": "🚫"
    }
    
    status_text = {
        "pending": "Ожидает оплаты",
        "paid": "Оплачен",
        "expired": "Истек",
        "cancelled": "Отменен"
    }
    
    details_text = f"""
📋 **Детали инвойса**

**ID:** `{invoice.invoice_id}`
**Статус:** {status_emoji.get(invoice.status, '❓')} {status_text.get(invoice.status, invoice.status)}

👤 **Клиент:** {user.first_name} ({user_mention})
💰 **Сумма:** {format_currency(invoice.amount, invoice.currency)}
📝 **Описание:** {invoice.service_description}

🕐 **Создан:** {format_datetime(invoice.created_at, "full")}
"""
    
    if invoice.paid_at:
        details_text += f"✅ **Оплачен:** {format_datetime(invoice.paid_at, 'full')}\n"
    
    if invoice.payment_url:
        details_text += f"\n🔗 [Ссылка на оплату]({invoice.payment_url})"
    
    await callback.answer()
    await callback.message.answer(
        details_text,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


@callback_router.callback_query(F.data.startswith("cancel_invoice_confirm:"))
async def callback_cancel_invoice_confirm(callback: CallbackQuery):
    """
    Запрос подтверждения отмены инвойса
    """
    from keyboards import parse_invoice_callback, get_cancel_confirmation_keyboard
    
    result = parse_invoice_callback(callback.data)
    if not result:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return
    
    action, invoice_id = result
    
    await callback.answer()
    await callback.message.answer(
        f"⚠️ **Подтверждение отмены**\n\n"
        f"Вы уверены что хотите отменить инвойс `{invoice_id}`?\n\n"
        f"Это действие нельзя отменить.",
        reply_markup=get_cancel_confirmation_keyboard(invoice_id),
        parse_mode="Markdown"
    )


@callback_router.callback_query(F.data.startswith("cancel_invoice_yes:"))
async def callback_cancel_invoice_yes(callback: CallbackQuery):
    """
    Подтверждение отмены инвойса
    """
    from keyboards import parse_invoice_callback
    
    result = parse_invoice_callback(callback.data)
    if not result:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return
    
    action, invoice_id = result
    admin_id = callback.from_user.id
    
    # Отменяем инвойс
    success = await invoice_service.cancel_invoice(invoice_id, admin_id)
    
    if success:
        await callback.answer("✅ Инвойс отменен", show_alert=False)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"✅ Инвойс `{invoice_id}` успешно отменен.",
            parse_mode="Markdown"
        )
    else:
        await callback.answer(
            "❌ Не удалось отменить инвойс (возможно уже оплачен или отменен)",
            show_alert=True
        )


@callback_router.callback_query(F.data.startswith("cancel_invoice_no:"))
async def callback_cancel_invoice_no(callback: CallbackQuery):
    """
    Отказ от отмены инвойса
    """
    await callback.answer("Действие отменено", show_alert=False)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Отмена инвойса прервана.")



@callback_router.callback_query(F.data == "card_payment_disabled")
async def callback_card_payment_disabled(callback: CallbackQuery):
    """
    Временная заморозка оплаты картой — показывает всплывающее уведомление
    """
    await callback.answer(
        "Этот способ оплаты временно не доступен. "
        "Пожалуйста, воспользуйтесь оплатой в криптовалюте или обратитесь в поддержку за помощью.",
        show_alert=True
    )


# ПРИМЕЧАНИЕ: catch-all обработчик callback'ов намеренно удалён.
# Он перехватывал payment_history и другие пользовательские callback'и
# раньше, чем успевал сработать user_router.
# Неизвестные callback'и теперь просто игнорируются aiogram'ом.
