"""
Обработчики админских команд — каталог услуг + FSM создания инвойса
"""
import html
from decimal import Decimal
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import Config
from database.models import User
from states import InvoiceCreationStates
from services import invoice_service, notification_service
from keyboards import (
    get_invoice_preview_keyboard,
    get_fsm_cancel_keyboard,
    parse_invoice_callback,
    # Новые клавиатуры каталога
    get_service_category_keyboard,
    get_top_tier_keyboard,
    get_top_category_keyboard,
    get_top_position_keyboard,
    get_back_to_service_keyboard,
)
from utils.validators import validate_user_id, validate_amount, validate_service_description
from utils.helpers import format_currency
from utils.logger import log_admin_action, bot_logger


# ===========================================================================
#  TIER LABEL HELPERS
# ===========================================================================

TIER_LABELS = {
    "tier1": "Тиер 1 — TRADING / SIGNALS / ARBITRAGE",
    "tier2": "Тиер 2 — ANALYTICS / DEFI / ECOSYSTEMS / INVESTMENTS",
    "tier3": "Тиер 3 — CRYPTO NEWS / EDUCATION / GUIDES",
    "tier4": "Тиер 4 — NFT / AIRDROPS / OPINIONS",
    "world": "Мировой ТОП (WORLD)",
}

# Короткие метки для описания инвойса (без категорий)
TIER_SHORT_LABELS = {
    "tier1": "Tier 1",
    "tier2": "Tier 2",
    "tier3": "Tier 3",
    "tier4": "Tier 4",
    "world": "Мировой",
}

PERIOD_LABELS = {
    "week":  "1 неделю",
    "month": "1 месяц",
}


def _get_top_price(tier: str, position: int, period: str) -> int:
    """Цена позиции в топе из Config.TOP_PRICES."""
    return Config.TOP_PRICES[tier][position][period]



# Маппинг названий категорий (из callback) → slug в lava_products.json
# Используется для построения service_key вида top_{slug}_{period}_{pos}
CATEGORY_SLUG_MAP: dict[str, str] = {
    # Tier 1
    "TRADING":           "trading",
    "SIGNALS":           "signals",
    "ARBITRAGE":         "arbitrage",
    # Tier 2
    "ANALYTICS REVIEWS": "analytics",
    "DEFI/WEB3":         "defi",
    "ECOSYSTEMS":        "ecosystems",
    "PROJECT REVIEWS":   "project_reviews",
    "INVESTMENTS":       "investments",
    # Tier 3
    "CRYPTO NEWS":       "cryptonews",
    "EDUCATION":         "education",
    "GUIDES":            "guides",
    # Tier 4
    "NFT/GAMEFI":        "nft",
    "AIRDROPS":          "airdrops",
    "OPINIONS/BLOG":     "opinions",
}


def _build_top_service_key(tier: str, position: int, period: str, category: str = "") -> str:
    """
    service_key в формате 'top_{slug}_{period}_{position}'.
    Совпадает с ключами в lava_products.json.
    Использует CATEGORY_SLUG_MAP для точного маппинга.
    Пример: category='DEFI/WEB3', pos=7, period='month' → 'top_defi_month_7'
    Для Мирового ТОП (category='') → 'top_world_month_1'
    """
    if category:
        slug = CATEGORY_SLUG_MAP.get(category, category.lower().replace(' ', '_').replace('/', '_'))
    else:
        slug = tier  # 'world'
    return f"top_{slug}_{period}_{position}"



def _build_top_service_description(tier: str, position: int, period: str, category: str = "") -> str:
    """Человекочитаемое описание ТОП-позиции с категорией."""
    period_label = PERIOD_LABELS.get(period, period)
    if category:
        return f"Размещение в ТОП #{position} категории {category} на {period_label}"
    # Мировой ТОП — без категории
    return f"Размещение в Мировой ТОП #{position} на {period_label}"


def _build_lava_slug(service_key: str) -> str | None:
    """Возвращает URL из маппинга по service_key или None если не задан."""
    slug = Config.LAVA_PRODUCT_MAP.get(service_key, "")
    return slug if slug else None


def _build_lava_url_for_amount(amount) -> str | None:
    """
    Возвращает URL Lava.top для заданной суммы в USD.
    Ищет точное совпадение, затем ближайший тир вверх из LAVA_CUSTOM_TIERS.
    Возвращает None если тиры не настроены.
    """
    if not Config.LAVA_CUSTOM_TIERS:
        return None
    try:
        amount_int = int(float(str(amount)))
    except (ValueError, TypeError):
        return None
    # Точное совпадение (включая float-ключ 0.65)
    if amount in Config.LAVA_CUSTOM_TIERS:
        return Config.LAVA_CUSTOM_TIERS[amount].get("url") or None
    if amount_int in Config.LAVA_CUSTOM_TIERS:
        return Config.LAVA_CUSTOM_TIERS[amount_int].get("url") or None
    # Ближайший тир вверх
    integer_keys = sorted(k for k in Config.LAVA_CUSTOM_TIERS if isinstance(k, int) and k >= 1)
    for key in integer_keys:
        if key >= amount_int:
            return Config.LAVA_CUSTOM_TIERS[key].get("url") or None
    # Максимальный тир (если сумма больше всех)
    if integer_keys:
        return Config.LAVA_CUSTOM_TIERS[integer_keys[-1]].get("url") or None
    return None


# ===========================================================================
#  ROUTER
# ===========================================================================

admin_router = Router(name="admin")


# ---------------------------------------------------------------------------
#  ШАГ 1 — /invoice → ввод User ID
# ---------------------------------------------------------------------------

@admin_router.message(Command("invoice"))
async def cmd_invoice_start(message: Message, state: FSMContext):
    """Начало процесса создания инвойса."""
    log_admin_action(message.from_user.id, "started invoice creation")

    await state.set_state(InvoiceCreationStates.WaitingForUserId)

    await message.answer(
        "📝 <b>Создание инвойса</b>\n\n"
        "<b>Шаг 1:</b> Введите Telegram ID или @username клиента:\n\n"
        "<i>Пример: 123456789 или @username</i>",
        reply_markup=get_fsm_cancel_keyboard(),
        parse_mode="HTML"
    )


@admin_router.message(InvoiceCreationStates.WaitingForUserId)
async def process_user_id(message: Message, state: FSMContext):
    """Обработка User ID клиента."""
    user_input = message.text.strip()

    is_numeric, user_id, username = validate_user_id(user_input)

    if not is_numeric and not username:
        await message.answer(
            "❌ Некорректный формат.\n\n"
            "Введите числовой Telegram ID или @username:\n"
            "<i>Пример: 123456789 или @username</i>",
            parse_mode="HTML"
        )
        return

    from database import get_session
    from sqlalchemy import select

    try:
        async with get_session() as session:
            if is_numeric:
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id)
                )
            else:
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
                    parse_mode="HTML"
                )
                return

            await state.update_data(
                target_user_id=user.telegram_id,
                target_user_username=user.username,
                target_user_first_name=user.first_name,
                target_db_id=user.id
            )

    except Exception as e:
        bot_logger.error(f"Error finding user: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при поиске пользователя. Попробуйте еще раз.")
        return

    # Переходим к выбору услуги из каталога
    await state.set_state(InvoiceCreationStates.WaitingForServiceCategory)

    user_mention = f"@{user.username}" if user.username else f"ID {user.telegram_id}"

    await message.answer(
        f"✅ Пользователь найден: <b>{html.escape(user.first_name)}</b> ({html.escape(user_mention)})\n\n"
        "<b>Шаг 2:</b> Выберите услугу из каталога:",
        reply_markup=get_service_category_keyboard(),
        parse_mode="HTML"
    )


# ---------------------------------------------------------------------------
#  ШАГ 2А — выбор услуги из каталога (callback svc:*)
# ---------------------------------------------------------------------------

@admin_router.callback_query(F.data == "svc:listing_pro",
                              InvoiceCreationStates.WaitingForServiceCategory)
async def handle_svc_listing_pro(callback: CallbackQuery, state: FSMContext):
    """Выбор LISTING PRO."""
    service_key = "listing_pro"
    amount = 390
    description = "LISTING PRO — Размещение канала в каталоге MarketFilter"
    lava_slug = _build_lava_slug(service_key)

    await state.update_data(
        amount=amount,
        description=description,
        service_key=service_key,
        lava_slug=lava_slug,
    )
    await _show_preview(callback, state)


@admin_router.callback_query(F.data == "svc:marketfilter_verified",
                              InvoiceCreationStates.WaitingForServiceCategory)
async def handle_svc_verified(callback: CallbackQuery, state: FSMContext):
    """Выбор MARKETFILTER VERIFIED."""
    service_key = "marketfilter_verified"
    amount = 1200
    description = "MARKETFILTER VERIFIED — Верификация канала на 1 год"
    lava_slug = _build_lava_slug(service_key)

    await state.update_data(
        amount=amount,
        description=description,
        service_key=service_key,
        lava_slug=lava_slug,
    )
    await _show_preview(callback, state)


@admin_router.callback_query(F.data == "svc:top_menu",
                              InvoiceCreationStates.WaitingForServiceCategory)
async def handle_svc_top_menu(callback: CallbackQuery, state: FSMContext):
    """Переход к выбору ТОП tier."""
    await state.set_state(InvoiceCreationStates.WaitingForTopTier)
    await callback.message.edit_text(
        "🏆 <b>ТОП по категории</b>\n\nВыберите группу категорий:",
        reply_markup=get_top_tier_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data == "svc:custom",
                              InvoiceCreationStates.WaitingForServiceCategory)
async def handle_svc_custom(callback: CallbackQuery, state: FSMContext):
    """Переход к вводу произвольной услуги."""
    await state.set_state(InvoiceCreationStates.WaitingForCustomDescription)
    await callback.message.edit_text(
        "✏️ **Своя услуга — Шаг 1/2**\n\n"
        "Введите **название услуги** (5–500 символов):\n\n"
        "_Пример: Консультация по продвижению канала_",
        reply_markup=get_back_to_service_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@admin_router.callback_query(F.data == "svc:back")
async def handle_svc_back(callback: CallbackQuery, state: FSMContext):
    """Возврат к главному меню выбора услуги."""
    await state.set_state(InvoiceCreationStates.WaitingForServiceCategory)
    data = await state.get_data()
    user_id = data.get('target_user_id', '?')
    username = data.get('target_user_username')
    first_name = data.get('target_user_first_name', '?')
    user_mention = f"@{username}" if username else f"ID {user_id}"

    await callback.message.edit_text(
        f"✅ Пользователь: <b>{html.escape(first_name)}</b> ({html.escape(user_mention)})\n\n"
        "<b>Шаг 2:</b> Выберите услугу из каталога:",
        reply_markup=get_service_category_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
#  ШАГ 2Б — ТОП: выбор tier я категории и позиции
# ---------------------------------------------------------------------------

@admin_router.callback_query(F.data.startswith("top_tier:"),
                              InvoiceCreationStates.WaitingForTopTier)
async def handle_top_tier(callback: CallbackQuery, state: FSMContext):
    """Выбор tier → переход к выбору категории (World — сразу к позиции)."""
    raw = callback.data  # "top_tier:tier1" или "top_tier:back"
    tier = raw.split(":", 1)[1]

    if tier == "back":
        # Назад к главному каталогу
        await state.set_state(InvoiceCreationStates.WaitingForServiceCategory)
        data = await state.get_data()
        user_id = data.get('target_user_id', '?')
        username = data.get('target_user_username')
        first_name = data.get('target_user_first_name', '?')
        user_mention = f"@{username}" if username else f"ID {user_id}"
        await callback.message.edit_text(
            f"✅ Пользователь: <b>{first_name}</b> ({user_mention})\n\n"
            "<b>Шаг 2:</b> Выберите услугу из каталога:",
            reply_markup=get_service_category_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await state.update_data(selected_tier=tier)

    # Мировой ТОП — без категорий, сразу к выбору позиции
    if tier == "world":
        await state.update_data(selected_category="")
        await state.set_state(InvoiceCreationStates.WaitingForTopPosition)
        await callback.message.edit_text(
            "🏆 <b>Мировой ТОП (WORLD)</b>\n\nВыберите место и период:",
            reply_markup=get_top_position_keyboard("world"),
            parse_mode="HTML"
        )
    else:
        await state.set_state(InvoiceCreationStates.WaitingForTopCategory)
        tier_label = TIER_LABELS.get(tier, tier)
        await callback.message.edit_text(
            f"🏆 <b>{tier_label}</b>\n\nВыберите категорию:",
            reply_markup=get_top_category_keyboard(tier),
            parse_mode="HTML"
        )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("top_cat:"),
                              InvoiceCreationStates.WaitingForTopCategory)
async def handle_top_category(callback: CallbackQuery, state: FSMContext):
    """
    Выбор категории → показ выбора позиции.
    Callback format: top_cat:{tier}:{category_slug} | top_cat:back
    """
    raw = callback.data  # "top_cat:tier1:TRADING" или "top_cat:back"
    parts = raw.split(":", 2)

    if len(parts) == 2 and parts[1] == "back":
        # Назад к выбору тира
        await state.set_state(InvoiceCreationStates.WaitingForTopTier)
        await callback.message.edit_text(
            "🏆 <b>ТОП по категории</b>\n\nВыберите группу категорий:",
            reply_markup=get_top_tier_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    if len(parts) < 3:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    _, tier, category = parts
    await state.update_data(selected_category=category)
    await state.set_state(InvoiceCreationStates.WaitingForTopPosition)

    await callback.message.edit_text(
        f"🏆 <b>Категория: {category}</b>\n\nВыберите место и период:",
        reply_markup=get_top_position_keyboard(tier, category),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data == "top_cat:back",
                              InvoiceCreationStates.WaitingForTopPosition)
async def handle_top_cat_back(callback: CallbackQuery, state: FSMContext):
    """Назад от выбора позиции к выбору категории."""
    data = await state.get_data()
    tier = data.get('selected_tier', 'tier1')
    if tier == 'world':
        # Для Мирового назад к выбору тира
        await state.set_state(InvoiceCreationStates.WaitingForTopTier)
        await callback.message.edit_text(
            "🏆 <b>ТОП по категории</b>\n\nВыберите группу категорий:",
            reply_markup=get_top_tier_keyboard(),
            parse_mode="HTML"
        )
    else:
        await state.set_state(InvoiceCreationStates.WaitingForTopCategory)
        tier_label = TIER_LABELS.get(tier, tier)
        await callback.message.edit_text(
            f"🏆 <b>{tier_label}</b>\n\nВыберите категорию:",
            reply_markup=get_top_category_keyboard(tier),
            parse_mode="HTML"
        )
    await callback.answer()



@admin_router.callback_query(F.data.startswith("top_pos:"),
                              InvoiceCreationStates.WaitingForTopPosition)
async def handle_top_position(callback: CallbackQuery, state: FSMContext):
    """
    Выбор позиции и периода.
    Callback format: top_pos:{tier}:{position}:{period}
    """
    parts = callback.data.split(":")  # ["top_pos", "tier1", "3", "week"]
    if len(parts) != 4:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    _, tier, pos_str, period = parts
    position = int(pos_str)

    data = await state.get_data()
    category = data.get('selected_category', '')

    amount = _get_top_price(tier, position, period)
    service_key = _build_top_service_key(tier, position, period, category)
    description = _build_top_service_description(tier, position, period, category)
    lava_slug = _build_lava_slug(service_key)

    await state.update_data(
        amount=amount,
        description=description,
        service_key=service_key,
        lava_slug=lava_slug,
    )
    await _show_preview(callback, state)



@admin_router.callback_query(F.data == "top_tier:back",
                              InvoiceCreationStates.WaitingForTopPosition)
async def handle_top_tier_back(callback: CallbackQuery, state: FSMContext):
    """Назад к вабору tier."""
    await state.set_state(InvoiceCreationStates.WaitingForTopTier)
    await callback.message.edit_text(
        "🏆 <b>ТОП по категории</b>\n\nВыберите группу категорий:",
        reply_markup=get_top_tier_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
#  ШАГ 2В — Своя услуга: ввод описания и суммы
# ---------------------------------------------------------------------------

@admin_router.message(InvoiceCreationStates.WaitingForCustomDescription)
async def process_custom_description(message: Message, state: FSMContext):
    """Обработка описания произвольной услуги."""
    description = message.text.strip()

    if len(description) < 5:
        await message.answer(
            "❌ Описание слишком короткое (минимум 5 символов).\nПопробуйте ещё раз.",
            reply_markup=get_back_to_service_keyboard()
        )
        return

    if len(description) > 500:
        await message.answer(
            "❌ Описание слишком длинное (максимум 500 символов).\nПопробуйте ещё раз.",
            reply_markup=get_back_to_service_keyboard()
        )
        return

    await state.update_data(
        description=description,
        service_key="custom",
        # lava_slug вычислится позже когда будет известна сумма
    )
    await state.set_state(InvoiceCreationStates.WaitingForCustomAmount)

    await message.answer(
        f"✅ Описание сохранено.\n\n"
        "✏️ **Своя услуга — Шаг 2/2**\n\n"
        "Введите **сумму в USD** (например: 150 или 250):",
        reply_markup=get_back_to_service_keyboard(),
        parse_mode="Markdown"
    )


@admin_router.message(InvoiceCreationStates.WaitingForCustomAmount)
async def process_custom_amount(message: Message, state: FSMContext):
    """Обработка суммы произвольной услуги."""
    amount_str = message.text.strip()

    is_valid, amount, error_msg = validate_amount(amount_str)

    if not is_valid:
        await message.answer(
            error_msg,
            reply_markup=get_back_to_service_keyboard()
        )
        return

    # ── Случай 0: сумма до $1 — тестовая карточка Lava ($0.65) ────────────
    if amount <= Decimal("1.0") and Config.LAVA_CUSTOM_TIERS and 0.65 in Config.LAVA_CUSTOM_TIERS:
        # Принудительно заменяем сумму инвойса на $0.65 (фиксированная тестовая карточка)
        test_amount = Decimal("0.65")
        _lava_url_test = _build_lava_url_for_amount(0.65) or _build_lava_url_for_amount(test_amount)
        await state.update_data(
            amount=test_amount,
            _pending_tier_usd=0.65,
            lava_slug=_lava_url_test,
        )
        await state.set_state(InvoiceCreationStates.WaitingForCustomAmountConfirm)

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Да, тестовая оплата $0.65", callback_data="tier_confirm:yes")
        kb.button(text="✏️ Ввести другую сумму",       callback_data="tier_confirm:no")
        kb.adjust(1)

        await message.answer(
            f"⚠️ <b>Сумма ${amount} — не более $1.00</b>\n\n"
            "Для сумм до <b>$1.00</b> включительно в сервисе Lava.top доступна "
            "только <b>тестовая оплата</b>.\n\n"
            "Инвойс будет создан на фиксированную сумму <b>$0.65</b>.\n"
            "Клиент увидит карточку Lava.top «Тестовая оплата» с ценой <b>$0.65</b>.\n\n"
            "Продолжить?",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        return
    # ────────────────────────────────────────────────────────────────────────

    # ── Проверяем кратность $10 для Lava-карточек ──────────────────────────
    amount_int = int(amount)
    # Берём только целые тиры (>= 1), чтобы тестовая карточка $0.65 не стала min_tier
    integer_tier_keys = [k for k in Config.LAVA_CUSTOM_TIERS.keys() if isinstance(k, int) or k >= 1]
    min_tier = min(integer_tier_keys) if integer_tier_keys else 10

    # Случай 1: сумма меньше минимального тира ($10)
    if Config.LAVA_CUSTOM_TIERS and amount_int < min_tier:
        tier_usd = min_tier
        _lava_url_min = _build_lava_url_for_amount(tier_usd)
        await state.update_data(
            amount=amount,
            _pending_tier_usd=tier_usd,
            lava_slug=_lava_url_min,
        )
        await state.set_state(InvoiceCreationStates.WaitingForCustomAmountConfirm)

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(text=f"✅ Да, карточка ${tier_usd}", callback_data="tier_confirm:yes")
        kb.button(text="✏️ Ввести другую сумму", callback_data="tier_confirm:no")
        kb.adjust(1)

        await message.answer(
            f"⚠️ <b>Сумма ${amount_int} меньше минимального тира ${min_tier}</b>\n\n"
            f"Клиент будет направлен на карточку Lava.top <b>${tier_usd}</b> "
            f"(минимальный тир).\n\n"
            f"Продолжить с карточкой <b>${tier_usd}</b>?",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        return

    # Случай 2: сумма не кратна $10
    if amount_int % 10 != 0 and Config.LAVA_CUSTOM_TIERS:
        # Вычисляем тир который получит клиент
        step = 10
        tier_usd = int(((amount_int + step - 1) // step) * step)
        # Если переполняет — берём максимальный
        max_tier = max(Config.LAVA_CUSTOM_TIERS.keys()) if Config.LAVA_CUSTOM_TIERS else 2500
        tier_usd = min(tier_usd, max_tier)

        _lava_url_rnd = _build_lava_url_for_amount(tier_usd)
        await state.update_data(
            amount=amount,
            _pending_tier_usd=tier_usd,
            lava_slug=_lava_url_rnd,
        )
        await state.set_state(InvoiceCreationStates.WaitingForCustomAmountConfirm)

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        kb.button(text=f"✅ Да, карточка ${tier_usd}", callback_data="tier_confirm:yes")
        kb.button(text="✏️ Ввести другую сумму", callback_data="tier_confirm:no")
        kb.adjust(1)

        await message.answer(
            f"⚠️ <b>Сумма ${amount_int} не кратна $10</b>\n\n"
            f"Клиент будет направлен на карточку Lava.top <b>${tier_usd}</b> "
            f"(ближайший тир вверх).\n\n"
            f"Продолжить с карточкой <b>${tier_usd}</b>?",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        return
    # ────────────────────────────────────────────────────────────────────────

    _lava_url_exact = _build_lava_url_for_amount(int(amount))
    await state.update_data(amount=amount, lava_slug=_lava_url_exact)
    await state.set_state(InvoiceCreationStates.PreviewInvoice)

    data = await state.get_data()
    await _send_preview_message(message, data)


@admin_router.callback_query(F.data.startswith("tier_confirm:"),
                              InvoiceCreationStates.WaitingForCustomAmountConfirm)
async def handle_tier_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение или отмена нестандартной цены."""
    action = callback.data.split(":")[1]  # "yes" | "no"

    if action == "no":
        # Возвращаем к вводу суммы
        await state.set_state(InvoiceCreationStates.WaitingForCustomAmount)
        await callback.message.edit_text(
            "✏️ Введите сумму в USD (кратную $10, например: 200 или 250):",
            reply_markup=get_back_to_service_keyboard()
        )
        await callback.answer()
        return

    # Продолжаем с сохранённой суммой
    data = await state.get_data()
    # Если lava_slug ещё не вычислен — вычисляем по финальной сумме
    if not data.get('lava_slug'):
        _pending_usd = data.get('_pending_tier_usd') or float(str(data.get('amount', 0)))
        _lava_url = _build_lava_url_for_amount(_pending_usd)
        if _lava_url:
            await state.update_data(lava_slug=_lava_url)
    await state.set_state(InvoiceCreationStates.PreviewInvoice)
    data = await state.get_data()
    await _send_preview_message(callback.message, data)
    await callback.answer()



# ---------------------------------------------------------------------------
#  ПРЕДПРОСМОТР
# ---------------------------------------------------------------------------

async def _show_preview(callback: CallbackQuery, state: FSMContext):
    """Показать предпросмотр (вызывается из callback-обработчиков каталога)."""
    await state.set_state(InvoiceCreationStates.PreviewInvoice)
    data = await state.get_data()

    target_user_id = data['target_user_id']
    target_username = data.get('target_user_username')
    target_first_name = data.get('target_user_first_name', 'Unknown')
    amount = data['amount']
    description = data['description']
    lava_slug = data.get('lava_slug')

    user_mention = f"@{target_username}" if target_username else f"ID {target_user_id}"

    slug_line = (
        f"\n🔗 <b>Lava URL:</b> <code>{html.escape(lava_slug)}</code>"
        if lava_slug
        else "\n<i>Lava URL: не задан (кнопка Банк РФ использует стандартный API)</i>"
    )

    preview_text = (
        "📋 <b>Предпросмотр инвойса</b>\n\n"
        f"👤 <b>Клиент:</b> {html.escape(target_first_name)} ({html.escape(user_mention)})\n"
        f"💰 <b>Сумма:</b> {html.escape(format_currency(amount, 'USD'))}\n"
        f"📝 <b>Описание:</b> {html.escape(description)}"
        f"{slug_line}\n\n"
        "Подтвердить создание и отправку инвойса клиенту?"
    )

    try:
        await callback.message.edit_text(
            preview_text,
            reply_markup=get_invoice_preview_keyboard("preview"),
            parse_mode="HTML"
        )
    except Exception as e:
        bot_logger.error(f"_show_preview edit_text failed: {e}", exc_info=True)
        await callback.message.answer(
            preview_text,
            reply_markup=get_invoice_preview_keyboard("preview"),
            parse_mode="HTML"
        )
    await callback.answer()


async def _send_preview_message(message: Message, data: dict):
    """Показать предпросмотр через обычное сообщение (поток «своя услуга»)."""
    target_user_id = data['target_user_id']
    target_username = data.get('target_user_username')
    target_first_name = data.get('target_user_first_name', 'Unknown')
    amount = data['amount']
    description = data['description']

    user_mention = f"@{target_username}" if target_username else f"ID {target_user_id}"

    preview_text = (
        "📋 <b>Предпросмотр инвойса</b>\n\n"
        f"👤 <b>Клиент:</b> {html.escape(target_first_name)} ({html.escape(user_mention)})\n"
        f"💰 <b>Сумма:</b> {html.escape(format_currency(amount, 'USD'))}\n"
        f"📝 <b>Описание:</b> {html.escape(description)}\n\n"
        "Подтвердить создание и отправку инвойса клиенту?"
    )

    await message.answer(
        preview_text,
        reply_markup=get_invoice_preview_keyboard("preview"),
        parse_mode="HTML"
    )


# ---------------------------------------------------------------------------
#  ПОДТВЕРЖДЕНИЕ / ОТМЕНА
# ---------------------------------------------------------------------------

@admin_router.callback_query(F.data.startswith("confirm_invoice:"))
async def confirm_invoice_creation(callback: CallbackQuery, state: FSMContext):
    """Подтверждение создания инвойса."""
    data = await state.get_data()

    if not data:
        await callback.answer("❌ Данные не найдены. Начните создание заново.", show_alert=True)
        return

    target_user_id = data['target_user_id']
    amount = data['amount']
    description = data['description']
    service_key = data.get('service_key')
    lava_slug = data.get('lava_slug')
    admin_id = callback.from_user.id
    admin_username = callback.from_user.username

    try:
        invoice = await invoice_service.create_invoice(
            user_id=target_user_id,
            amount=Decimal(str(amount)),
            service_description=description,
            admin_id=admin_id,
            admin_username=admin_username,
            currency="USD",
            service_key=service_key,
            lava_slug=lava_slug,
        )

        if not invoice:
            await callback.answer("❌ Ошибка создания инвойса", show_alert=True)
            await callback.message.answer(
                "❌ Не удалось создать инвойс. Проверьте логи и попробуйте снова."
            )
            await state.clear()
            return

        from database import get_session
        from sqlalchemy import select

        async with get_session() as session:
            user = await session.scalar(
                select(User).where(User.telegram_id == target_user_id)
            )

        from aiogram import Bot
        bot: Bot = callback.bot

        from services import NotificationService
        notif_service = NotificationService(bot)

        await notif_service.send_invoice_to_client(invoice, user)
        await notif_service.notify_admins_invoice_created(invoice, user, admin_id)

        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("✅ Инвойс создан и отправлен!", show_alert=False)

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
    """Отмена создания инвойса."""
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Создание инвойса отменено.")
    await callback.answer("Отменено", show_alert=False)
    log_admin_action(callback.from_user.id, "cancelled invoice creation")


@admin_router.callback_query(F.data == "cancel_fsm")
async def cancel_fsm(callback: CallbackQuery, state: FSMContext):
    """Отмена процесса FSM через кнопку."""
    await state.clear()
    await callback.message.answer("❌ Создание инвойса отменено.")
    await callback.answer("Отменено", show_alert=False)
    log_admin_action(callback.from_user.id, "cancelled FSM via button")


# ---------------------------------------------------------------------------
#  /mark_paid — Ручное подтверждение оплаты Lava.top
# ---------------------------------------------------------------------------

@admin_router.message(Command("mark_paid"))
async def cmd_mark_paid(message: Message):
    """
    Ручное подтверждение оплаты оплаченного инвойса (для Lava.top).
    Использование: /mark_paid INV-XXXXX
    """
    if message.from_user.id not in Config.ADMIN_IDS:
        return

    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Укажите ID инвойса.\n\n"
            "Использование: <code>/mark_paid INV-XXXXX</code>",
            parse_mode="HTML"
        )
        return

    invoice_id = args[1].strip().upper()

    # Проверяем что инвойс существует
    from services import invoice_service
    inv = await invoice_service.get_invoice_by_id(invoice_id)

    if not inv:
        await message.answer(f"❌ Инвойс <code>{html.escape(invoice_id)}</code> не найден.", parse_mode="HTML")
        return

    if inv.status == "paid":
        await message.answer(
            f"ℹ️ Инвойс <code>{html.escape(invoice_id)}</code> уже отмечен как оплаченный.",
            parse_mode="HTML"
        )
        return

    if inv.status != "pending":
        await message.answer(
            f"❌ Инвойс <code>{html.escape(invoice_id)}</code> имеет статус <b>{inv.status}</b> — нельзя подтвердить.",
            parse_mode="HTML"
        )
        return

    # Помечаем как оплаченный
    result = await invoice_service.mark_invoice_paid_by_admin(
        invoice_id=invoice_id,
        admin_id=message.from_user.id
    )

    if not result:
        await message.answer(
            f"❌ Не удалось подтвердить инвойс <code>{html.escape(invoice_id)}</code>. Проверьте логи.",
            parse_mode="HTML"
        )
        return

    inv_obj, user_obj = result

    # Отправляем уведомления
    from aiogram import Bot
    bot: Bot = message.bot
    from services import NotificationService
    from datetime import datetime

    inv_obj.status = "paid"
    inv_obj.paid_at = datetime.utcnow()

    notifier = NotificationService(bot)
    try:
        await notifier.notify_client_payment_success(invoice=inv_obj, user=user_obj)
        await notifier.notify_admins_payment_received(
            invoice=inv_obj, user=user_obj, payment_method="card_ru_manual"
        )
        await message.answer(
            f"✅ Инвойс <code>{html.escape(invoice_id)}</code> подтверждён!\n"
            f"Уведомления отправлены клиенту и администраторам.",
            parse_mode="HTML"
        )
        log_admin_action(message.from_user.id, f"manually confirmed payment for {invoice_id}")
    except Exception as e:
        bot_logger.error(f"Error sending notifications for manual payment {invoice_id}: {e}")
        await message.answer(
            f"⚠️ Инвойс подтверждён, но при отправке уведомлений произошла ошибка: {e}",
            parse_mode="HTML"
        )

