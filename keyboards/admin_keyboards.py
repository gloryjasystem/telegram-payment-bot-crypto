"""
Inline клавиатуры для администраторов
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ===========================================================================
#  СУЩЕСТВУЮЩИЕ КЛАВИАТУРЫ
# ===========================================================================

def get_invoice_preview_keyboard(invoice_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для предпросмотра инвойса администратором.

    Callback data:
        - confirm_invoice:{invoice_id}
        - cancel_invoice:{invoice_id}
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
    Клавиатура управления существующим инвойсом.

    Callback data:
        - view_invoice:{invoice_id}
        - cancel_invoice_confirm:{invoice_id}
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
    Клавиатура подтверждения отмены инвойса.

    Callback data:
        - cancel_invoice_yes:{invoice_id}
        - cancel_invoice_no:{invoice_id}
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
    """Клавиатура помощи для администратора."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Создание инвойса", callback_data="admin_help_invoice")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_help_stats")
    )
    return builder.as_markup()


def get_invoice_sent_keyboard() -> InlineKeyboardMarkup:
    """Пустая клавиатура (убирает кнопки после отправки)."""
    return InlineKeyboardMarkup(inline_keyboard=[])


def get_fsm_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопка «Отменить создание» для любого шага FSM.

    Callback data:
        - cancel_fsm
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отменить создание", callback_data="cancel_fsm")
    )
    return builder.as_markup()


# ===========================================================================
#  НОВЫЕ КЛАВИАТУРЫ — КАТАЛОГ УСЛУГ
# ===========================================================================

def get_service_category_keyboard() -> InlineKeyboardMarkup:
    """
    Главное меню выбора услуги при создании инвойса.

    Callback data:
        - svc:listing_pro
        - svc:top_menu
        - svc:marketfilter_verified
        - svc:custom
        - cancel_fsm
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📋 LISTING PRO",
            callback_data="svc:listing_pro"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏆 ТОП по категории",
            callback_data="svc:top_menu"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ MARKETFILTER VERIFIED",
            callback_data="svc:marketfilter_verified"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Своя услуга",
            callback_data="svc:custom"
        )
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_fsm")
    )
    return builder.as_markup()


def get_top_tier_keyboard() -> InlineKeyboardMarkup:
    """
    Выбор Tier для ТОП-размещения.

    Callback data:
        - top_tier:tier1
        - top_tier:tier2
        - top_tier:tier3
        - top_tier:tier4
        - top_tier:world
        - svc:back  (назад к главному меню)
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📈 Tier 1 — TRADING / SIGNALS / ARBITRAGE",
            callback_data="top_tier:tier1"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Tier 2 — ANALYTICS / DEFI / ECOSYSTEMS / INVESTMENTS",
            callback_data="top_tier:tier2"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📰 Tier 3 — CRYPTO NEWS / EDUCATION / ANALYTICS / GUIDES",
            callback_data="top_tier:tier3"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🎮 Tier 4 — NFT / AIRDROPS / OPINIONS",
            callback_data="top_tier:tier4"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🌍 Мировой ТОП (WORLD)",
            callback_data="top_tier:world"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="svc:back"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_fsm")
    )
    return builder.as_markup()


def get_top_category_keyboard(tier: str) -> InlineKeyboardMarkup:
    """
    Выбор конкретной категории внутри тира.

    Args:
        tier: "tier1" | "tier2" | "tier3" | "tier4" | "world"

    Callback data:
        - top_cat:{tier}:{category_slug}
        - top_tier:back  (вернуться к выбору tier)
    """
    TIER_CATEGORIES = {
        "tier1": [
            ("📈 TRADING",        "TRADING"),
            ("📡 SIGNALS",        "SIGNALS"),
            ("🔄 ARBITRAGE",      "ARBITRAGE"),
        ],
        "tier2": [
            ("📊 ANALYTICS REVIEWS",  "ANALYTICS REVIEWS"),
            ("🌐 DEFI / WEB3",        "DEFI/WEB3"),
            ("🏗 ECOSYSTEMS",         "ECOSYSTEMS"),
            ("🔍 PROJECT REVIEWS",    "PROJECT REVIEWS"),
            ("💼 INVESTMENTS",        "INVESTMENTS"),
        ],
        "tier3": [
            ("📰 CRYPTO NEWS",        "CRYPTO NEWS"),
            ("📚 EDUCATION",          "EDUCATION"),
            ("📝 ANALYTICAL POSTS",   "ANALYTICAL POSTS"),
            ("🗺 GUIDES",             "GUIDES"),
        ],
        "tier4": [
            ("🎮 NFT / GAMEFI",       "NFT/GAMEFI"),
            ("🎁 AIRDROPS",           "AIRDROPS"),
            ("💬 OPINIONS / BLOG",    "OPINIONS/BLOG"),
        ],
        "world": [],  # без выбора категории
    }

    builder = InlineKeyboardBuilder()
    categories = TIER_CATEGORIES.get(tier, [])
    for label, slug in categories:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"top_cat:{tier}:{slug}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="top_cat:back"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_fsm")
    )
    return builder.as_markup()


def get_top_position_keyboard(tier: str, category: str = "") -> InlineKeyboardMarkup:
    """
    Выбор позиции (1–10) и периода (неделя/месяц).

    Args:
        tier: "tier1" | "tier2" | "tier3" | "tier4" | "world"
        category: название категории (для отображения в back callback)

    Callback data:
        - top_pos:{tier}:{position}:week
        - top_pos:{tier}:{position}:month
        - top_tier:back  (вернуться к выбору tier/category)
    """
    builder = InlineKeyboardBuilder()

    for pos in range(1, 11):
        builder.row(
            InlineKeyboardButton(
                text=f"#{pos} — Неделя",
                callback_data=f"top_pos:{tier}:{pos}:week"
            ),
            InlineKeyboardButton(
                text=f"#{pos} — Месяц",
                callback_data=f"top_pos:{tier}:{pos}:month"
            )
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="top_cat:back"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_fsm")
    )
    return builder.as_markup()


def get_back_to_service_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура «Назад» + «Отменить» для шагов ввода своей услуги."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к выбору услуги", callback_data="svc:back"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_fsm")
    )
    return builder.as_markup()


# ===========================================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===========================================================================

def parse_invoice_callback(callback_data: str) -> tuple[str, str] | None:
    """
    Парсинг callback data для инвойсов.

    Returns:
        (action, invoice_id) или None
    """
    if ':' not in callback_data:
        return None
    parts = callback_data.split(':', 1)
    if len(parts) != 2:
        return None
    return (parts[0], parts[1])
