"""
Обработчики команд пользователя
"""
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from database.models import User
from services import NotificationService
from keyboards import get_welcome_keyboard, get_help_keyboard
from utils.logger import log_user_action, bot_logger


# Создаем роутер для пользовательских команд
user_router = Router(name="user")


@user_router.message(CommandStart())
async def cmd_start(message: Message, db_user: User):
    """
    Обработчик команды /start
    
    Отправляет приветственное сообщение с кнопками:
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
• Оплачивать их удобным способом (криптовалюта)
• Просматривать историю платежей

📋 После получения инвойса вы увидите кнопку для оплаты.

⚡️ Процесс оплаты быстрый и безопасный - все транзакции защищены.

Ознакомьтесь с условиями обслуживания и политикой возврата ниже.

Если у вас есть вопросы - обращайтесь в поддержку! 💬
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
/terms - Условия обслуживания
/refund - Политика возврата
"""
    
    await message.answer(
        help_text,
        reply_markup=get_help_keyboard(),
        parse_mode="Markdown"
    )


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
