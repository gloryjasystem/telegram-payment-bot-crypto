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


def _build_top_service_key(tier: str, position: int, period: str) -> str:
    """service_key вида 'top_tier1_week_3'."""
    return f"top_{tier}_{period}_{position}"


def _build_top_service_description(tier: str, position: int, period: str) -> str:
    """Человекочитаемое описание ТОП-позиции (без названий категорий)."""
    tier_label  = TIER_SHORT_LABELS.get(tier, tier)
    period_label = PERIOD_LABELS.get(period, period)
    return f"ТОП {tier_label} — #{position} место в топе на {period_label}"


def _build_lava_slug(service_key: str) -> str | None:
    """Возвращает slug из маппинга или None если не задан."""
    slug = Config.LAVA_PRODUCT_MAP.get(service_key, "")
    return slug if slug else None


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
        "📝 **Создание инвойса**\n\n"
        "**Шаг 1:** Введите Telegram ID или @username клиента:\n\n"
        "_Пример: 123456789 или @username_",
        reply_markup=get_fsm_cancel_keyboard(),
        parse_mode="Markdown"
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
            "_Пример: 123456789 или @username_",
            parse_mode="Markdown"
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
                    parse_mode="Markdown"
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
        f"✅ Пользователь найден: **{user.first_name}** ({user_mention})\n\n"
        "**Шаг 2:** Выберите услугу из каталога:",
        reply_markup=get_service_category_keyboard(),
        parse_mode="Markdown"
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
    description = (
        "LISTING PRO — Размещение канала в каталоге MarketFilter\n"
        "ℹ️ Условие: каналы от 3 месяцев размещаются в очереди. "
        "Каналы младше 3 месяцев — добавляются вне очереди (та же цена $390)."
    )
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
        "🏆 **ТОП по категории**\n\nВыберите группу категорий:",
        reply_markup=get_top_tier_keyboard(),
        parse_mode="Markdown"
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
        f"✅ Пользователь: **{first_name}** ({user_mention})\n\n"
        "**Шаг 2:** Выберите услугу из каталога:",
        reply_markup=get_service_category_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
#  ШАГ 2Б — ТОП: выбор tier и позиции
# ---------------------------------------------------------------------------

@admin_router.callback_query(F.data.startswith("top_tier:"),
                              InvoiceCreationStates.WaitingForTopTier)
async def handle_top_tier(callback: CallbackQuery, state: FSMContext):
    """Выбор tier → показать выбор позиции."""
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
            f"✅ Пользователь: **{first_name}** ({user_mention})\n\n"
            "**Шаг 2:** Выберите услугу из каталога:",
            reply_markup=get_service_category_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    await state.update_data(selected_tier=tier)
    await state.set_state(InvoiceCreationStates.WaitingForTopPosition)

    tier_label = TIER_LABELS.get(tier, tier)
    await callback.message.edit_text(
        f"🏆 **{tier_label}**\n\nВыберите место и период:",
        reply_markup=get_top_position_keyboard(tier),
        parse_mode="Markdown"
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

    amount = _get_top_price(tier, position, period)
    service_key = _build_top_service_key(tier, position, period)
    description = _build_top_service_description(tier, position, period)
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
        "🏆 **ТОП по категории**\n\nВыберите группу категорий:",
        reply_markup=get_top_tier_keyboard(),
        parse_mode="Markdown"
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
        lava_slug=None,
    )
    await state.set_state(InvoiceCreationStates.WaitingForCustomAmount)

    await message.answer(
        f"✅ Описание сохранено.\n\n"
        "✏️ **Своя услуга — Шаг 2/2**\n\n"
        "Введите **сумму в USD** (например: 150 или 250.50):",
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

    await state.update_data(amount=amount)
    await state.set_state(InvoiceCreationStates.PreviewInvoice)

    # Собираем данные и сразу показываем предпросмотр через Message
    data = await state.get_data()
    await _send_preview_message(message, data)


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
        f"📝 <b>Описание:</b> {html.escape(description)}\n"
        "<i>[Произвольная услуга — без Lava URL]</i>\n\n"
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
