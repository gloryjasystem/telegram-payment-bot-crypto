"""
Обработчики команд пользователя
"""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery

from database.models import User
from services import NotificationService, invoice_service
from keyboards import get_welcome_keyboard, get_help_keyboard, get_history_keyboard
from utils.helpers import format_currency, format_datetime
from utils.logger import log_user_action, bot_logger


# Создаем роутер для пользовательских команд
user_router = Router(name="user")


@user_router.message(CommandStart())
async def cmd_start(message: Message, db_user: User):
    """
    Обработчик команды /start
    
    Отправляет приветственное сообщение с кнопками:
    - Мои платежи
    - Условия обслуживания
    - Политика возврата
    - Поддержка
    
    Args:
        message: Входящее сообщение
        db_user: Пользователь из БД (добавлен UserAuthMiddleware)
    """
    log_user_action(message.from_user.id, message.from_user.username, "started bot")
    
    welcome_text = f"""
Привет, {message.from_user.first_name}! 👋

Добро пожаловать в платежного бота **MarketFilter**.

Здесь вы можете:
• Получать счета за услуги от администраторов
• Оплачивать их удобным способом (💳 картой или ₿ криптовалютой)
• Просматривать историю платежей

📋 После получения инвойса вы увидите кнопки для оплаты.

⚡️ Процесс оплаты быстрый и безопасный — все транзакции защищены.

Ознакомьтесь с условиями обслуживания и политикой возврата ниже.

Если у вас есть вопросы — обращайтесь в поддержку! 💬
"""
    
    await message.answer(
        welcome_text,
        reply_markup=get_welcome_keyboard(),
        parse_mode="Markdown"
    )
    
    bot_logger.info(f"User {message.from_user.id} started the bot")


@user_router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Обработчик команды /help
    
    Показывает справочную информацию о боте
    """
    log_user_action(message.from_user.id, message.from_user.username, "requested help")
    
    help_text = """
📚 **Справка по использованию бота**

**Основные возможности:**

💰 **Оплата счетов**
После получения инвойса от администратора, вы увидите сообщение с кнопкой "Оплатить". Нажмите на нее и следуйте инструкциям.

📋 **Поддерживаемые криптовалюты:**
- Bitcoin (BTC)
- Ethereum (ETH)
- Tether (USDT)
- И другие популярные криптовалюты

⏱ **Время действия инвойса:**
Инвойс действителен в течение 1 часа с момента создания.

✅ **После оплаты:**
Вы получите автоматическое подтверждение, и наши менеджеры свяжутся с вами для выполнения услуги.

📞 **Поддержка:**
Если у вас возникли вопросы или проблемы, свяжитесь с поддержкой через кнопку ниже.

**Доступные команды:**
/start - Начать работу с ботом
/help - Показать эту справку
/history - История платежей
/terms - Условия обслуживания
/refund - Политика возврата
"""
    
    await message.answer(
        help_text,
        reply_markup=get_help_keyboard(),
        parse_mode="Markdown"
    )


@user_router.message(Command("history"))
async def cmd_history(message: Message):
    """
    Обработчик команды /history
    
    Показывает историю платежей пользователя
    """
    log_user_action(message.from_user.id, message.from_user.username, "requested payment history")
    
    invoices = await invoice_service.get_user_invoices(message.from_user.id)
    
    if not invoices:
        text = (
            "📜 **История платежей**\n\n"
            "У вас пока нет платежей.\n\n"
            "Когда администратор создаст для вас инвойс "
            "и вы его оплатите — он появится здесь."
        )
    else:
        status_emoji = {
            "paid": "✅",
            "pending": "⏳",
            "cancelled": "❌",
            "expired": "⌛"
        }
        
        total_paid = sum(inv.amount for inv in invoices if inv.status == "paid")
        
        text = f"📜 **История платежей** ({len(invoices)})\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, inv in enumerate(invoices, 1):
            emoji = status_emoji.get(inv.status, "❓")
            date_str = format_datetime(inv.created_at, "short") if inv.created_at else "—"
            
            text += f"{i}. {emoji} {inv.service_description}\n"
            text += f"   💵 {format_currency(inv.amount, inv.currency)} | 🕐 {date_str}\n\n"
        
        if total_paid > 0:
            text += f"💰 Всего оплачено: **{format_currency(total_paid, 'USD')}**"
    
    await message.answer(
        text,
        reply_markup=get_history_keyboard(),
        parse_mode="Markdown"
    )


@user_router.callback_query(F.data == "payment_history")
async def callback_payment_history(callback: CallbackQuery):
    """
    Обработчик кнопки 'Мои платежи' из главного меню
    """
    invoices = await invoice_service.get_user_invoices(callback.from_user.id)
    
    if not invoices:
        text = (
            "📜 **История платежей**\n\n"
            "У вас пока нет платежей.\n\n"
            "Когда администратор создаст для вас инвойс "
            "и вы его оплатите — он появится здесь."
        )
    else:
        status_emoji = {
            "paid": "✅",
            "pending": "⏳",
            "cancelled": "❌",
            "expired": "⌛"
        }
        
        total_paid = sum(inv.amount for inv in invoices if inv.status == "paid")
        
        text = f"📜 **История платежей** ({len(invoices)})\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, inv in enumerate(invoices, 1):
            emoji = status_emoji.get(inv.status, "❓")
            date_str = format_datetime(inv.created_at, "short") if inv.created_at else "—"
            
            entry = (
                f"{i}. {emoji} {inv.service_description}\n"
                f"   💵 {format_currency(inv.amount, inv.currency)} | 🕐 {date_str}\n\n"
            )
            # Telegram limit: 4096 chars. Stop adding entries if getting close.
            if len(text) + len(entry) > 3800:
                text += f"_...и ещё {len(invoices) - i + 1} записей_\n\n"
                break
            text += entry
        
        if total_paid > 0:
            text += f"💰 Всего оплачено: **{format_currency(total_paid, 'USD')}**"
    
    await callback.answer()
    # Отправляем новым сообщением (edit_text ограничен 4096 символами и не работает
    # если нажата кнопка из сообщения инвойса с другой разметкой)
    await callback.message.answer(
        text,
        reply_markup=get_history_keyboard(),
        parse_mode="Markdown"
    )



@user_router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    """
    Обработчик кнопки 'Назад' — возвращает в главное меню
    """
    welcome_text = f"""
Привет, {callback.from_user.first_name}! 👋

Добро пожаловать в платежного бота **MarketFilter**.

Здесь вы можете:
• Получать счета за услуги от администраторов
• Оплачивать их удобным способом (💳 картой или ₿ криптовалютой)
• Просматривать историю платежей

📋 После получения инвойса вы увидите кнопки для оплаты.

⚡️ Процесс оплаты быстрый и безопасный — все транзакции защищены.

Ознакомьтесь с условиями обслуживания и политикой возврата ниже.

Если у вас есть вопросы — обращайтесь в поддержку! 💬
"""
    
    await callback.message.edit_text(
        welcome_text,
        reply_markup=get_welcome_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@user_router.message(Command("terms"))
async def cmd_terms(message: Message):
    """
    Обработчик команды /terms
    
    Показывает ссылку на условия обслуживания
    """
    log_user_action(message.from_user.id, message.from_user.username, "requested terms")
    
    from config import Config
    from keyboards import get_terms_keyboard
    
    terms_text = f"""
📋 **Условия обслуживания**

Пожалуйста, ознакомьтесь с нашими условиями обслуживания по ссылке ниже:

{Config.TERMS_OF_SERVICE_URL}

Используя этого бота, вы автоматически соглашаетесь с условиями обслуживания.
"""
    
    await message.answer(
        terms_text,
        reply_markup=get_terms_keyboard(),
        parse_mode="Markdown",
        disable_web_page_preview=False
    )


@user_router.message(Command("refund"))
async def cmd_refund(message: Message):
    """
    Обработчик команды /refund
    
    Показывает ссылку на политику возврата
    """
    log_user_action(message.from_user.id, message.from_user.username, "requested refund policy")
    
    from config import Config
    from keyboards import get_refund_policy_keyboard
    
    refund_text = f"""
💰 **Политика возврата**

Пожалуйста, ознакомьтесь с нашей политикой возврата по ссылке ниже:

{Config.REFUND_POLICY_URL}

Если вы хотите запросить возврат средств, пожалуйста, свяжитесь с поддержкой.
"""
    
    await message.answer(
        refund_text,
        reply_markup=get_refund_policy_keyboard(),
        parse_mode="Markdown",
        disable_web_page_preview=False
    )
