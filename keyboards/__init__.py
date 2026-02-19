"""
Keyboards package
Содержит inline клавиатуры для пользователей и администраторов
"""

# User keyboards
from .user_keyboards import (
    get_welcome_keyboard,
    get_invoice_keyboard,
    get_help_keyboard,
    get_payment_success_keyboard,
    get_history_keyboard,
    get_terms_keyboard,
    get_refund_policy_keyboard
)

# Admin keyboards
from .admin_keyboards import (
    get_invoice_preview_keyboard,
    get_invoice_management_keyboard,
    get_cancel_confirmation_keyboard,
    get_admin_help_keyboard,
    get_invoice_sent_keyboard,
    get_fsm_cancel_keyboard,
    parse_invoice_callback,
    # Каталог услуг (новое)
    get_service_category_keyboard,
    get_top_tier_keyboard,
    get_top_category_keyboard,
    get_top_position_keyboard,
    get_back_to_service_keyboard,
)

__all__ = [
    # User keyboards
    "get_welcome_keyboard",
    "get_invoice_keyboard",
    "get_help_keyboard",
    "get_payment_success_keyboard",
    "get_history_keyboard",
    "get_terms_keyboard",
    "get_refund_policy_keyboard",
    # Admin keyboards
    "get_invoice_preview_keyboard",
    "get_invoice_management_keyboard",
    "get_cancel_confirmation_keyboard",
    "get_admin_help_keyboard",
    "get_invoice_sent_keyboard",
    "get_fsm_cancel_keyboard",
    "parse_invoice_callback",
    # Каталог услуг (новое)
    "get_service_category_keyboard",
    "get_top_tier_keyboard",
    "get_top_category_keyboard",
    "get_top_position_keyboard",
    "get_back_to_service_keyboard",
]
