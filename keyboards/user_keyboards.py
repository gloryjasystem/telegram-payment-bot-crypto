"""
Inline клавиатуры для пользователей
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """
    Приветственная клавиатура для команды /start
    
    Кнопки:
    - Условия обслуживания
    - Политика возврата
    - Поддержка
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с тремя кнопками
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📋 Условия обслуживания",
            url=Config.TERMS_OF_SERVICE_URL
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="💰 Политика возврата",
            url=Config.REFUND_POLICY_URL
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="💬 Поддержка",
            url=f"https://t.me/{Config.SUPPORT_USERNAME}"
        )
    )
    
    return builder.as_markup()


def get_invoice_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для инвойса с кнопкой оплаты через Web App
    
    Args:
        payment_url: URL страницы оплаты Cryptomus
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой оплаты и поддержкой
    
    Note:
        Использует WebApp для встроенной оплаты (открывается внутри Telegram)
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка оплаты с WebApp (открывается внутри Telegram)
    builder.row(
        InlineKeyboardButton(
            text="💳 Оплатить",
            web_app=WebAppInfo(url=payment_url)
        )
    )
    
    # Кнопка поддержки (на случай вопросов)
    builder.row(
        InlineKeyboardButton(
            text="💬 Поддержка",
            url=f"https://t.me/{Config.SUPPORT_USERNAME}"
        )
    )
    
    return builder.as_markup()


def get_help_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для команды /help
    
    Кнопки:
    - Условия обслуживания
    - Политика возврата
    - Поддержка
    
    Returns:
        InlineKeyboardMarkup: Клавиатура помощи
    """
    # Используем ту же клавиатуру что и для welcome
    return get_welcome_keyboard()


def get_payment_success_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура после успешной оплаты
    
    Кнопки:
    - Связаться с поддержкой
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой поддержки
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💬 Связаться с поддержкой",
            url=f"https://t.me/{Config.SUPPORT_USERNAME}"
        )
    )
    
    return builder.as_markup()


def get_terms_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для просмотра условий обслуживания
    
    Returns:
        InlineKeyboardMarkup: Кнопка с условиями
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📋 Условия обслуживания",
            url=Config.TERMS_OF_SERVICE_URL
        )
    )
    
    return builder.as_markup()


def get_refund_policy_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для просмотра политики возврата
    
    Returns:
        InlineKeyboardMarkup: Кнопка с политикой возврата
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💰 Политика возврата",
            url=Config.REFUND_POLICY_URL
        )
    )
    
    return builder.as_markup()
