"""
Обработчики webhook от платежных систем
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram import Bot
import json

from config import Config
from utils.logger import bot_logger
from services.nowpayments_service import nowpayments_service
from services.invoice_service import invoice_service
from services.notification_service import NotificationService
from database.models import Invoice

router = Router()


async def handle_nowpayments_webhook(request_data: dict, bot: Bot) -> dict:
    """
    Обработка IPN webhook от NOWPayments
    
    Args:
        request_data: Данные из webhook
        bot: Instance бота для отправки уведомлений
    
    Returns:
        dict: Результат обработки
    """
    try:
        # Обработка IPN
        result = await nowpayments_service.process_ipn(request_data)
        
        if not result['success']:
            bot_logger.error(f"IPN processing failed: {result.get('error')}")
            return {'status': 'error', 'message': result.get('error')}
        
        order_id = result['order_id']
        payment_status = result['status']
        is_paid = result['is_paid']
        
        bot_logger.info(f"IPN processed: {order_id} - {payment_status}")
        
        # Обновление инвойса в БД
        if is_paid:
            # Получаем данные инвойса
            invoice_data = await invoice_service.get_invoice_with_user(order_id)
            
            if not invoice_data:
                bot_logger.error(f"Invoice {order_id} not found")
                return {'status': 'error', 'message': 'Invoice not found'}
            
            invoice, user = invoice_data
            
            # Проверяем что инвойс еще не оплачен
            if invoice.status == 'paid':
                bot_logger.warning(f"Invoice {order_id} already marked as paid")
                return {'status': 'ok', 'message': 'Already processed'}
            
            # Отмечаем как оплаченный
            success = await invoice_service.mark_invoice_as_paid(
                invoice_id=order_id,
                transaction_id=str(result.get('payment_id')),
                payment_method=result.get('pay_currency', 'crypto')
            )
            
            if success:
                # Создаем экземпляр NotificationService
                notifier = NotificationService(bot)
                
                # Отправка уведомления клиенту
                await notifier.notify_client_payment_success(
                    invoice=invoice,
                    user=user
                )
                
                # Уведомление всех админов
                await notifier.notify_admins_payment_received(
                    invoice=invoice,
                    user=user
                )
                
                bot_logger.info(f"✅ Payment processed successfully: {order_id}")
            else:
                bot_logger.error(f"Failed to mark invoice {order_id} as paid")
        
        elif result.get('is_failed'):
            # Платеж провалился
            bot_logger.warning(f"Payment failed for {order_id}: {payment_status}")
            # Можно уведомить пользователя о провале
        
        elif result.get('is_partial'):
            # Частичная оплата
            bot_logger.warning(f"Partial payment for {order_id}: {payment_status}")
            # Можно обработать underpayment
        
        return {'status': 'ok'}
    
    except Exception as e:
        bot_logger.error(f"Error handling NOWPayments webhook: {e}", exc_info=True)
        return {'status': 'error', 'message': str(e)}
