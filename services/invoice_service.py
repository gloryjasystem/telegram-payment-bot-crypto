"""
Сервис для управления инвойсами
"""
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from database import Invoice, User, Payment, get_session
from utils.logger import bot_logger, log_admin_action
from utils.helpers import generate_invoice_id
from services.nowpayments_service import nowpayments_service as payment_service


class InvoiceService:
    """Сервис для работы с инвойсами"""
    
    async def create_invoice(
        self,
        user_id: int,
        amount: Decimal,
        service_description: str,
        admin_id: int,
        admin_username: Optional[str] = None,
        currency: str = "USD",
        service_key: Optional[str] = None,
        lava_slug: Optional[str] = None,
    ) -> Optional[Invoice]:
        """
        Создание нового инвойса
        
        Args:
            user_id: Telegram ID получателя
            amount: Сумма платежа
            service_description: Описание услуги
            admin_id: Telegram ID админа создавшего инвойс
            currency: Валюта (по умолчанию USD)
        
        Returns:
            Invoice: Созданный инвойс или None при ошибке
        """
        try:
            async with get_session() as session:
                # Проверяем существует ли пользователь
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id)
                )
                
                if not user:
                    bot_logger.error(f"User {user_id} not found in database")
                    return None
                
                # Генерация уникального Invoice ID
                invoice_id = generate_invoice_id()
                
                # Создание инвойса
                invoice = Invoice(
                    invoice_id=invoice_id,
                    user_id=user.telegram_id,
                    amount=amount,
                    currency=currency,
                    service_description=service_description,
                    status="pending",
                    admin_id=admin_id,
                    admin_username=admin_username,
                    service_key=service_key,
                    lava_slug=lava_slug,
                    created_at=datetime.utcnow()
                )
                
                session.add(invoice)
                await session.flush()  # Получаем ID инвойса
                
                # Создание платежной ссылки через NOWPayments
                payment_result = await payment_service.create_payment(invoice)
                
                if payment_result['success']:
                    invoice.payment_url = payment_result['payment_url']
                    invoice.external_invoice_id = payment_result['payment_id']
                else:
                    bot_logger.error(f"Failed to create payment: {payment_result.get('error')}")
                    # Инвойс все равно создаем, но без payment_url
                
                # commit выполняется автоматически в get_session()
                
                log_admin_action(
                    admin_id,
                    f"created invoice {invoice.invoice_id} for user {user_id}, amount: ${amount}"
                )
                
                bot_logger.info(f"✅ Invoice {invoice.invoice_id} created successfully")
                
                return invoice
        
        except Exception as e:
            bot_logger.error(f"Error creating invoice: {e}", exc_info=True)
            return None
    
    async def get_invoice_by_id(self, invoice_id: str) -> Optional[Invoice]:
        """
        Получение инвойса по Invoice ID
        
        Args:
            invoice_id: ID инвойса (формат: INV-xxxxx)
        
        Returns:
            Invoice: Объект инвойса или None
        """
        try:
            async with get_session() as session:
                invoice = await session.scalar(
                    select(Invoice)
                    .where(Invoice.invoice_id == invoice_id)
                    .options(selectinload(Invoice.user))
                )
                return invoice
        except Exception as e:
            bot_logger.error(f"Error getting invoice {invoice_id}: {e}")
            return None
    
    async def get_user_invoices(self, telegram_id: int) -> List[Invoice]:
        """
        Получение всех инвойсов пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
        
        Returns:
            List[Invoice]: Список инвойсов
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(Invoice)
                    .where(Invoice.user_id == telegram_id)
                    .order_by(Invoice.created_at.desc())
                )
                
                return list(result.scalars().all())
        except Exception as e:
            bot_logger.error(f"Error getting user invoices: {e}")
            return []
    
    async def get_pending_invoices(self) -> List[Invoice]:
        """
        Получение всех неоплаченных инвойсов
        
        Returns:
            List[Invoice]: Список pending инвойсов
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(Invoice)
                    .where(Invoice.status == "pending")
                    .order_by(Invoice.created_at.desc())
                    .options(selectinload(Invoice.user))
                )
                return list(result.scalars().all())
        except Exception as e:
            bot_logger.error(f"Error getting pending invoices: {e}")
            return []
    
    async def mark_invoice_as_paid(
        self,
        invoice_id: str,
        transaction_id: str,
        payment_category: Optional[str] = None,
        payment_provider: Optional[str] = None,
        payment_method: Optional[str] = None,
        client_email: Optional[str] = None
    ) -> bool:
        """
        Отметить инвойс как оплаченный
        
        Args:
            invoice_id: ID инвойса
            transaction_id: ID транзакции от платежной системы
            payment_category: Категория (crypto / card_ru / card_int)
            payment_provider: Провайдер (nowpayments / lava / wayforpay)
            payment_method: Конкретный метод (BTC, ETH, USDT, card и т.д.)
            client_email: Email клиента (для карточных оплат)
        
        Returns:
            bool: True если успешно обновлено
        """
        try:
            async with get_session() as session:
                invoice = await session.scalar(
                    select(Invoice).where(Invoice.invoice_id == invoice_id)
                )
                
                if not invoice:
                    bot_logger.error(f"Invoice {invoice_id} not found")
                    return False
                
                # Определяем эффективный transaction_id (external_invoice_id если есть)
                effective_transaction_id = invoice.external_invoice_id or transaction_id
                
                # Проверка на дубликат транзакции (идемпотентность)
                existing_payment = await session.scalar(
                    select(Payment).where(Payment.transaction_id == effective_transaction_id)
                )
                
                if existing_payment:
                    bot_logger.warning(f"Payment with transaction_id {effective_transaction_id} already exists. Skipping duplicate.")
                    # Если инвойс еще не оплачен (например, частичная оплата или логическая ошибка), отмечаем
                    if invoice.status != "paid":
                        invoice.status = "paid"
                        invoice.paid_at = datetime.utcnow()
                        # commit выполняется автоматически в get_session()
                        bot_logger.info(f"Updated invoice {invoice_id} status to PAID (recovered from duplicate payment)")
                    # Возвращаем False — платёж уже обработан, уведомления отправлять НЕ НУЖНО
                    return False

                # Обновление инвойса
                invoice.status = "paid"
                invoice.paid_at = datetime.utcnow()
                
                # Создание записи о платеже
                payment = Payment(
                    invoice_id=invoice.invoice_id,
                    transaction_id=effective_transaction_id,
                    payment_category=payment_category,
                    payment_provider=payment_provider,
                    payment_method=payment_method,
                    client_email=client_email,
                    admin_username=invoice.admin_username,
                    created_at=datetime.utcnow(),
                    confirmed_at=datetime.utcnow()
                )
                
                session.add(payment)
                # commit выполняется автоматически в get_session()
                
                bot_logger.info(f"✅ Invoice {invoice_id} marked as paid ({payment_category}/{payment_provider}/{payment_method})")
                
                return True
        
        except Exception as e:
            bot_logger.error(f"Error marking invoice as paid: {e}", exc_info=True)
            return False
    
    async def cancel_invoice(self, invoice_id: str, admin_id: int) -> bool:
        """
        Отмена инвойса
        
        Args:
            invoice_id: ID инвойса
            admin_id: Telegram ID админа
        
        Returns:
            bool: True если успешно отменено
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    update(Invoice)
                    .where(Invoice.invoice_id == invoice_id)
                    .where(Invoice.status == "pending")
                    .values(status="cancelled", cancelled_at=datetime.utcnow())
                )
                
                # commit выполняется автоматически в get_session()
                
                if result.rowcount > 0:
                    log_admin_action(admin_id, f"cancelled invoice {invoice_id}")
                    bot_logger.info(f"Invoice {invoice_id} cancelled by admin {admin_id}")
                    return True
                else:
                    bot_logger.warning(f"Invoice {invoice_id} not found or already processed")
                    return False
        
        except Exception as e:
            bot_logger.error(f"Error cancelling invoice: {e}")
            return False
    
    async def expire_old_invoices(self, hours: int = 1) -> int:
        """
        Истечение срока старых неоплаченных инвойсов
        
        Args:
            hours: Часы до истечения (по умолчанию 1)
        
        Returns:
            int: Количество инвойсов с истекшим сроком
        """
        try:
            expiry_time = datetime.utcnow() - timedelta(hours=hours)
            
            async with get_session() as session:
                result = await session.execute(
                    update(Invoice)
                    .where(Invoice.status == "pending")
                    .where(Invoice.created_at < expiry_time)
                    .values(status="expired")
                )
                
                # commit выполняется автоматически в get_session()
                
                expired_count = result.rowcount
                
                if expired_count > 0:
                    bot_logger.info(f"Expired {expired_count} old invoices")
                
                return expired_count
        
        except Exception as e:
            bot_logger.error(f"Error expiring old invoices: {e}")
            return 0
    
    async def get_invoice_with_user(self, invoice_id: str) -> Optional[tuple[Invoice, User]]:
        """
        Получение инвойса вместе с данными пользователя
        
        Args:
            invoice_id: ID инвойса
        
        Returns:
            tuple[Invoice, User]: Инвойс и пользователь или None
        """
        try:
            async with get_session() as session:
                invoice = await session.scalar(
                    select(Invoice)
                    .where(Invoice.invoice_id == invoice_id)
                )
                
                if not invoice:
                    return None
                
                # Загружаем пользователя по telegram_id
                user = await session.scalar(
                    select(User).where(User.telegram_id == invoice.user_id)
                )
                
                if user:
                    return (invoice, user)
                
                return None
        
        except Exception as e:
            bot_logger.error(f"Error getting invoice with user: {e}")
            return None

    async def find_pending_lava_invoice_by_amount(
        self,
        amount_rub: float,
        tolerance: float = 5.0
    ) -> Optional[str]:
        """
        Поиск pending инвойса с lava_slug по сумме в рублях.
        Используется когда Lava.top webhook не содержит order_id.

        Args:
            amount_rub: Сумма которую заплатил клиент (в рублях)
            tolerance: Допустимое отклонение суммы в рублях

        Returns:
            str: invoice_id если найден, иначе None
        """
        try:
            from config import Config
            rate = Config.USD_TO_RUB_RATE

            async with get_session() as session:
                # Берём все pending lava-инвойсы (с lava_slug != NULL)
                result = await session.execute(
                    select(Invoice)
                    .where(Invoice.status == "pending")
                    .where(Invoice.lava_slug.isnot(None))
                    .order_by(Invoice.created_at.desc())
                    .limit(50)
                )
                invoices = list(result.scalars().all())

            for inv in invoices:
                # Конвертируем USD сумму инвойса в рубли для сравнения
                expected_rub = float(inv.amount) * rate
                if abs(expected_rub - amount_rub) <= tolerance:
                    bot_logger.info(
                        f"🔍 Found lava invoice by amount: {inv.invoice_id} "
                        f"(expected ≈{expected_rub:.0f}₽, got {amount_rub:.0f}₽)"
                    )
                    return inv.invoice_id

            bot_logger.warning(
                f"🔍 No pending lava invoice found for amount {amount_rub:.0f}₽"
            )
            return None

        except Exception as e:
            bot_logger.error(f"Error finding lava invoice by amount: {e}", exc_info=True)
            return None

    async def mark_invoice_paid_by_admin(
        self,
        invoice_id: str,
        admin_id: int
    ) -> Optional[tuple]:
        """
        Ручное подтверждение оплаты администратором (/mark_paid).

        Returns:
            tuple(Invoice, User) если успешно, иначе None
        """
        success = await self.mark_invoice_as_paid(
            invoice_id=invoice_id,
            transaction_id=f"MANUAL-{admin_id}",
            payment_category="card_ru",
            payment_provider="lava",
            payment_method="manual_confirm"
        )
        if not success:
            return None
        return await self.get_invoice_with_user(invoice_id)


# Глобальный экземпляр сервиса
invoice_service = InvoiceService()
