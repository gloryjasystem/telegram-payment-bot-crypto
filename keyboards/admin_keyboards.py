"""
Inline клавиатуры для администраторов
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_invoice_preview_keyboard(invoice_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для предпросмотра инвойса администратором
    
    Показывает кнопки подтверждения или отмены создания инвойса
    
    Args:
        invoice_id: ID инвойса для подтверждения
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками подтверждения/отмены
    
    Callback data:
        - confirm_invoice:{invoice_id} - подтвердить и отправить инвойс
        - cancel_invoice:{invoice_id} - отменить создание инвойса
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить и отправить",
            callback_data=f"confirm_invoice:{invoice_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"cancel_invoice:{invoice_id}"
        )
    )
    
    return builder.as_markup()


def get_invoice_management_keyboard(invoice_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура управления существующим инвойсом
    
    Позволяет админу просмотреть статус или отменить инвойс
    
    Args:
        invoice_id: ID инвойса
    
    Returns:
        InlineKeyboardMarkup: Клавиатура управления инвойсом
    
    Callback data:
        - view_invoice:{invoice_id} - просмотреть детали инвойса
        - cancel_invoice:{invoice_id} - отменить инвойс
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📋 Просмотреть детали",
            callback_data=f"view_invoice:{invoice_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🚫 Отменить инвойс",
            callback_data=f"cancel_invoice_confirm:{invoice_id}"
        )
    )
    
    return builder.as_markup()


def get_cancel_confirmation_keyboard(invoice_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения отмены инвойса
    
    Дополнительная защита от случайной отмены
    
    Args:
        invoice_id: ID инвойса для отмены
    
    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    
    Callback data:
        - cancel_invoice_yes:{invoice_id} - подтвердить отмену
        - cancel_invoice_no:{invoice_id} - не отменять
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, отменить",
            callback_data=f"cancel_invoice_yes:{invoice_id}"
        ),
        InlineKeyboardButton(
            text="❌ Нет",
            callback_data=f"cancel_invoice_no:{invoice_id}"
        )
    )
    
    return builder.as_markup()


def get_admin_help_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура помощи для администратора
    
    Показывает доступные команды
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с командами
    
    Callback data:
        - admin_help_invoice - помощь по созданию инвойса
        - admin_help_stats - помощь по статистике
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📝 Создание инвойса",
            callback_data="admin_help_invoice"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data="admin_help_stats"
        )
    )
    
    return builder.as_markup()


def get_invoice_sent_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура после успешной отправки инвойса клиенту
    
    Returns:
        InlineKeyboardMarkup: Пустая клавиатура (для удаления предыдущих кнопок)
    """
    # Возвращаем пустую клавиатуру, чтобы убрать кнопки после отправки
    return InlineKeyboardMarkup(inline_keyboard=[])


def get_fsm_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для отмены процесса создания инвойса (FSM)
    
    Returns:
        InlineKeyboardMarkup: Кнопка отмены
    
    Callback data:
        - cancel_fsm - отменить процесс создания
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить создание",
            callback_data="cancel_fsm"
        )
    )
    
    return builder.as_markup()


# Вспомогательные функции для callback data parsing

def parse_invoice_callback(callback_data: str) -> tuple[str, str] | None:
    """
    Парсинг callback data для инвойсов
    
    Args:
        callback_data: Строка callback data
    
    Returns:
        tuple[str, str] | None: (action, invoice_id) или None если формат неверный
    
    Examples:
        >>> parse_invoice_callback("confirm_invoice:INV-123")
        ('confirm_invoice', 'INV-123')
        
        >>> parse_invoice_callback("view_invoice:INV-456")
        ('view_invoice', 'INV-456')
        
        >>> parse_invoice_callback("invalid")
        None
    """
    if ':' not in callback_data:
        return None
    
    parts = callback_data.split(':', 1)
    if len(parts) != 2:
        return None
    
    action, invoice_id = parts
    return (action, invoice_id)
