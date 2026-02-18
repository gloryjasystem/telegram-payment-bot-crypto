"""
Сервис для отправки уведомлений администраторам и клиентам
"""
from typing import List
from aiogram import Bot
from aiogram.types import Message

from config import Config
from database.models import Invoice, User
from utils.logger import bot_logger
from utils.helpers import format_currency, format_datetime, format_user_mention
from keyboards import (
    get_invoice_keyboard,
    get_payment_success_keyboard
)


class NotificationService:
    """Сервис для отправки уведомлений"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_invoice_to_client(self, invoice: Invoice, user: User) -> bool:
        """
        Отправка инвойса клиенту
        
        Args:
            invoice: Объект инвойса
            user: Объект пользователя
        
        Returns:
            bool: True если успешно отправлено
        """
        try:
            # Формирование сообщения для клиента
            message_text = f"""
📋 **Инвойс #{invoice.invoice_id}**

💰 **Сумма:** {format_currency(invoice.amount, invoice.currency)}
📝 **Услуга:** {invoice.service_description}

⏱ Срок оплаты: 1 час

Для оплаты нажмите кнопку ниже:
"""
            
            # Формируем URL для WebApp карточной оплаты
            import urllib.parse
            config = Config()
            base_url = config.BASE_WEBHOOK_URL
            card_webapp_url = None
            
            if base_url:
                card_params = urllib.parse.urlencode({
                    'service': invoice.service_description,
                    'amount': str(invoice.amount),
                    'currency': invoice.currency,
                    'invoice_id': invoice.invoice_id,
                    'rate': str(Config.USD_TO_RUB_RATE)
                })
                card_webapp_url = f"{base_url}/webapp/index.html?{card_params}"
            
            # Отправка сообщения с кнопками оплаты (крипто + карта)
            sent_message = await self.bot.send_message(
                chat_id=user.telegram_id,
                text=message_text,
                reply_markup=get_invoice_keyboard(
                    payment_url=invoice.payment_url,
                    card_webapp_url=card_webapp_url
                ),
                parse_mode="Markdown"
            )
            
            # Сохраняем ID сообщения для возможности редактирования при отмене
            try:
                from database import get_session
                from sqlalchemy import update as sql_update
                from database.models import Invoice as InvoiceModel
                
                async with get_session() as session:
                    await session.execute(
                        sql_update(InvoiceModel)
                        .where(InvoiceModel.invoice_id == invoice.invoice_id)
                        .values(bot_message_id=sent_message.message_id)
                    )
                    # commit выполняется автоматически в get_session()
                bot_logger.info(f"Saved bot_message_id={sent_message.message_id} for invoice {invoice.invoice_id}")
            except Exception as e:
                bot_logger.warning(f"Could not save bot_message_id: {e}")
            
            bot_logger.info(f"Invoice {invoice.invoice_id} sent to user {user.telegram_id}")
            return True
        
        except Exception as e:
            bot_logger.error(f"Error sending invoice to client: {e}", exc_info=True)
            return False
    
    async def notify_admins_invoice_created(
        self,
        invoice: Invoice,
        user: User,
        admin_id: int
    ) -> None:
        """
        Уведомление администратора о создании инвойса
        
        Args:
            invoice: Созданный инвойс
            user: Получатель инвойса
            admin_id: ID админа который создал инвойс
        """
        try:
            user_mention = format_user_mention(
                user.telegram_id,
                user.username,
                user.first_name
            )
            
            message_text = f"""
✅ **Инвойс создан успешно**

📋 **Invoice ID:** `{invoice.invoice_id}`
👤 **Клиент:** {user_mention}
💰 **Сумма:** {format_currency(invoice.amount, invoice.currency)}
📝 **Описание:** {invoice.service_description}
🕐 **Создан:** {format_datetime(invoice.created_at, "short")}

Инвойс отправлен клиенту.
"""
            
            await self.bot.send_message(
                chat_id=admin_id,
                text=message_text,
                parse_mode="Markdown"
            )
        
        except Exception as e:
            bot_logger.error(f"Error notifying admin about invoice creation: {e}")
    
    @staticmethod
    def _format_payment_method(payment_method: str) -> str:
        """Маппинг технического payment_method в человеко-читаемый текст"""
        m = payment_method.lower()
        if 'card_ru' in m or 'lava' in m:
            return '💳 Банк РФ (Lava.top)'
        elif 'card_int' in m or 'waypay' in m:
            if 'test' in m:
                return '🧪 Тест WayForPay'
            return '🌐 Иностранный банк (WayForPay)'
        
        # Крипто — показываем валюту
        return f'₿ Крипто ({payment_method.upper()})'
    
    async def notify_admins_payment_received(
        self,
        invoice: Invoice,
        user: User,
        payment_method: str = ""
    ) -> None:
        """
        Уведомление всех администраторов об успешной оплате
        
        Args:
            invoice: Оплаченный инвойс
            user: Плательщик
            payment_method: Способ оплаты (card_ru_lava, card_int_waypay, BTC и т.д.)
        """
        try:
            user_mention = format_user_mention(
                user.telegram_id,
                user.username,
                user.first_name
            )
            
            # Форматируем способ оплаты
            method_display = self._format_payment_method(payment_method) if payment_method else "Не указан"
            
            # Загружаем email клиента из таблицы payments
            client_email = None
            try:
                from database import get_session
                from database.models import Payment
                from sqlalchemy import select
                
                async with get_session() as session:
                    payment = await session.scalar(
                        select(Payment)
                        .where(Payment.invoice_id == invoice.invoice_id)
                        .order_by(Payment.created_at.desc())
                    )
                    if payment and payment.client_email:
                        client_email = payment.client_email
            except Exception as e:
                bot_logger.warning(f"Could not load client_email for notification: {e}")
            
            # Строка email для уведомления
            email_line = f"\n✉️ **Email:** {client_email}" if client_email else ""
            
            message_text = f"""
💰 **ПЛАТЕЖ ПОЛУЧЕН**

📋 **Invoice ID:** `{invoice.invoice_id}`
👤 **Клиент:** {user_mention}
💵 **Сумма:** {format_currency(invoice.amount, invoice.currency)}
📝 **Услуга:** {invoice.service_description}
💳 **Оплата:** {method_display}{email_line}
🕐 **Оплачен:** {format_datetime(invoice.paid_at, "short")}

Необходимо выполнить услугу для клиента.
"""
            
            # Отправка всем администраторам
            for admin_id in Config.ADMIN_IDS:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=message_text,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    bot_logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        except Exception as e:
            bot_logger.error(f"Error notifying admins about payment: {e}")
    
    async def notify_client_payment_success(
        self,
        invoice: Invoice,
        user: User
    ) -> bool:
        """
        Уведомление клиента об успешной оплате
        
        Args:
            invoice: Оплаченный инвойс
            user: Клиент
        
        Returns:
            bool: True если успешно отправлено
        """
        try:
            message_text = f"""
✅ **Оплата получена!**

📋 **Инвойс:** `{invoice.invoice_id}`
💰 **Сумма:** {format_currency(invoice.amount, invoice.currency)}
📝 **Услуга:** {invoice.service_description}

Благодарим за оплату! 🎉

Наши менеджеры свяжутся с вами в ближайшее время для выполнения услуги.

Если у вас есть вопросы, обращайтесь в поддержку.
"""
            
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=message_text,
                reply_markup=get_payment_success_keyboard(),
                parse_mode="Markdown"
            )
            
            # Редактируем оригинальное сообщение инвойса (убираем кнопки оплаты)
            if invoice.bot_message_id:
                try:
                    paid_at_str = format_datetime(invoice.paid_at, "short") if invoice.paid_at else ""
                    edited_text = (
                        f"✅ **Инвойс #{invoice.invoice_id} — ОПЛАЧЕНО**\n\n"
                        f"💰 **Сумма:** {format_currency(invoice.amount, invoice.currency)}\n"
                        f"📝 **Услуга:** {invoice.service_description}\n"
                    )
                    if paid_at_str:
                        edited_text += f"🕐 **Оплачено:** {paid_at_str}\n"
                    edited_text += "\n✅ Спасибо за оплату!"
                    
                    await self.bot.edit_message_text(
                        chat_id=user.telegram_id,
                        message_id=invoice.bot_message_id,
                        text=edited_text,
                        parse_mode="Markdown",
                        reply_markup=None  # Убираем кнопки оплаты
                    )
                    bot_logger.info(f"Edited original invoice message for {invoice.invoice_id} → PAID")
                except Exception as e:
                    bot_logger.warning(f"Could not edit original invoice message: {e}")
            
            bot_logger.info(f"Payment success notification sent to user {user.telegram_id}")
            return True
        
        except Exception as e:
            bot_logger.error(f"Error notifying client about payment success: {e}")
            return False
    
    async def notify_admin_invoice_cancelled(
        self,
        invoice_id: str,
        admin_id: int
    ) -> None:
        """
        Уведомление админа об отмене инвойса
        
        Args:
            invoice_id: ID отмененного инвойса
            admin_id: ID админа
        """
        try:
            message_text = f"""
🚫 **Инвойс отменен**

📋 **Invoice ID:** `{invoice_id}`

Инвойс был успешно отменен.
"""
            
            await self.bot.send_message(
                chat_id=admin_id,
                text=message_text,
                parse_mode="Markdown"
            )
        
        except Exception as e:
            bot_logger.error(f"Error notifying admin about cancellation: {e}")
    
    async def notify_client_invoice_cancelled(
        self,
        invoice: Invoice,
        user: User
    ) -> bool:
        """
        Уведомление клиента об отмене инвойса
        
        Args:
            invoice: Отмененный инвойс
            user: Клиент
        
        Returns:
            bool: True если успешно отправлено
        """
        try:
            from keyboards import get_payment_success_keyboard
            
            message_text = f"""
🚫 **Инвойс отменён**

📋 **Инвойс:** `{invoice.invoice_id}`
💰 **Сумма:** {format_currency(invoice.amount, invoice.currency)}
📝 **Услуга:** {invoice.service_description}

Ваш инвойс был отменён администратором. Оплата по нему более невозможна.

Если у вас есть вопросы — обращайтесь в поддержку.
"""
            
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=message_text,
                reply_markup=get_payment_success_keyboard(),
                parse_mode="Markdown"
            )
            
            bot_logger.info(f"Cancellation notification sent to user {user.telegram_id} for invoice {invoice.invoice_id}")
            return True
        
        except Exception as e:
            bot_logger.error(f"Error notifying client about invoice cancellation: {e}")
            return False
    
    async def send_welcome_message(self, user_telegram_id: int, first_name: str) -> bool:
        """
        Отправка приветственного сообщения новому пользователю
        
        Args:
            user_telegram_id: Telegram ID пользователя
            first_name: Имя пользователя
        
        Returns:
            bool: True если успешно отправлено
        """
        try:
            from keyboards import get_welcome_keyboard
            
            message_text = f"""
Привет, {first_name}! 👋

Добро пожаловать в платежного бота **MarketFilter**.

Здесь вы можете:
• Оплачивать счета за услуги
• Получать инвойсы от администраторов (💳 картой или ₿ криптовалютой)
• Просматривать историю платежей

После получения инвойса вы сможете оплатить его удобным способом.

📋 Ознакомьтесь с условиями обслуживания и политикой возврата ниже.

Если у вас есть вопросы — обращайтесь в поддержку! 💬
"""
            
            await self.bot.send_message(
                chat_id=user_telegram_id,
                text=message_text,
                reply_markup=get_welcome_keyboard(),
                parse_mode="Markdown"
            )
            
            return True
        
        except Exception as e:
            bot_logger.error(f"Error sending welcome message: {e}")
            return False
    
    async def broadcast_to_admins(self, message: str) -> int:
        """
        Рассылка сообщения всем администраторам
        
        Args:
            message: Текст сообщения
        
        Returns:
            int: Количество успешно отправленных сообщений
        """
        sent_count = 0
        
        for admin_id in Config.ADMIN_IDS:
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="Markdown"
                )
                sent_count += 1
            except Exception as e:
                bot_logger.error(f"Failed to send broadcast to admin {admin_id}: {e}")
        
        return sent_count


# Примечание: Экземпляр NotificationService создается в bot.py после инициализации Bot
# notification_service = NotificationService(bot)
