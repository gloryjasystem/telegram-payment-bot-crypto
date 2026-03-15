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
    - Мои платежи
    - Условия обслуживания
    - Политика возврата
    - Поддержка
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📜 Мои платежи",
            callback_data="payment_history"
        )
    )
    
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


def get_invoice_keyboard(payment_url: str, card_webapp_url: str = None) -> InlineKeyboardMarkup:
    """
    Клавиатура для инвойса с кнопками оплаты
    
    Args:
        payment_url: URL страницы оплаты крипто (NOWPayments)
        card_webapp_url: URL Mini App для оплаты картой (опционально)
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками оплаты и поддержкой
    """
    import urllib.parse
    builder = InlineKeyboardBuilder()
    
    # Кнопка оплаты картой (временно заморожена — показывает всплывающее уведомление)
    builder.row(
        InlineKeyboardButton(
            text="💳 Оплатить картой",
            callback_data="card_payment_disabled"
        )
    )
    
    # Кнопка оплаты крипто с WebApp (открывается внутри Telegram)
    try:
        from config import Config
        config = Config()
        base_url = config.BASE_WEBHOOK_URL
    except Exception:
        base_url = None
        
    if base_url:
        encoded_url = urllib.parse.quote(payment_url, safe='')
        crypto_url = f"{base_url}/webapp/redirect.html?url={encoded_url}"
    else:
        crypto_url = payment_url

    builder.row(
        InlineKeyboardButton(
            text="₿ Оплатить крипто",
            web_app=WebAppInfo(url=crypto_url)
        )
    )
    
    # Кнопка поддержки (на случай вопросов)
    builder.row(
        InlineKeyboardButton(
            text="📄 Договор оферты",
            url=Config.OFERTA_URL
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


def get_history_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для истории платежей
    
    Кнопки:
    - Связаться с поддержкой
    - Назад (в главное меню)
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💬 Связаться с поддержкой",
            url=f"https://t.me/{Config.SUPPORT_USERNAME}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="back_to_main"
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
