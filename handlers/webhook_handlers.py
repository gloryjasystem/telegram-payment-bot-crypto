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
                bot_logger.error(f"❌ Invoice {order_id} not found in database!")
                return {'status': 'error', 'message': 'Invoice not found'}
            
            invoice, user = invoice_data
            bot_logger.info(f"📋 Found invoice {order_id} for user {user.telegram_id}")
            
            # Проверяем что инвойс еще не оплачен
            if invoice.status == 'paid':
                bot_logger.warning(f"Invoice {order_id} already marked as paid")
                return {'status': 'ok', 'message': 'Already processed'}
            
            crypto_currency = result.get('pay_currency', 'crypto')
            
            # Отмечаем как оплаченный
            success = await invoice_service.mark_invoice_as_paid(
                invoice_id=order_id,
                transaction_id=str(result.get('payment_id')),
                payment_category='crypto',
                payment_provider='nowpayments',
                payment_method=crypto_currency
            )
            
            if success:
                # Обновляем локальный объект инвойса, чтобы в уведомлении была дата
                from datetime import datetime
                invoice.status = 'paid'
                invoice.paid_at = datetime.utcnow()

                bot_logger.info(f"✅ Invoice {order_id} marked as paid. Sending notifications...")
                
                # Создаем экземпляр NotificationService
                notifier = NotificationService(bot)
                
                # Отправка уведомления клиенту
                try:
                    await notifier.notify_client_payment_success(
                        invoice=invoice,
                        user=user
                    )
                    bot_logger.info(f"✅ Client notification sent to {user.telegram_id}")
                except Exception as e:
                    bot_logger.error(f"❌ Failed to send client notification: {e}", exc_info=True)
                
                # Уведомление всех админов
                try:
                    await notifier.notify_admins_payment_received(
                        invoice=invoice,
                        user=user,
                        payment_method=crypto_currency
                    )
                    bot_logger.info(f"✅ Admin notifications sent")
                except Exception as e:
                    bot_logger.error(f"❌ Failed to send admin notifications: {e}", exc_info=True)
                
                bot_logger.info(f"✅ Payment processed successfully: {order_id}")
            else:
                bot_logger.error(f"❌ Failed to mark invoice {order_id} as paid in DB")
        
        elif result.get('is_failed'):
            # Платеж провалился — уведомляем клиента и администраторов
            bot_logger.warning(f"Payment failed for {order_id}: {payment_status}")
            
            invoice_data = await invoice_service.get_invoice_with_user(order_id)
            if invoice_data:
                invoice, user = invoice_data
                if invoice.status == 'pending':
                    notifier = NotificationService(bot)
                    try:
                        reason = "expired" if payment_status == "expired" else "failed"
                        await notifier.notify_client_payment_failed(
                            invoice=invoice,
                            user=user,
                            reason=reason
                        )
                        bot_logger.info(f"✅ Failure notification sent to {user.telegram_id}")
                    except Exception as e:
                        bot_logger.error(f"❌ Failed to send failure notification: {e}")
                    
                    # Уведомляем администраторов
                    try:
                        await notifier.broadcast_to_admins(
                            f"⚠️ *Платёж не прошёл*\n\n"
                            f"📋 Invoice: `{order_id}`\n"
                            f"📊 Статус NOWPayments: `{payment_status}`\n"
                            f"👤 Клиент TG ID: `{user.telegram_id}`"
                        )
                    except Exception as e:
                        bot_logger.error(f"❌ Failed to notify admins about failed payment: {e}")
        
        elif result.get('is_partial'):
            # Частичная оплата — уведомляем клиента
            bot_logger.warning(f"Partial payment for {order_id}: {payment_status}")
            
            invoice_data = await invoice_service.get_invoice_with_user(order_id)
            if invoice_data:
                invoice, user = invoice_data
                notifier = NotificationService(bot)
                try:
                    await notifier.notify_client_payment_failed(
                        invoice=invoice,
                        user=user,
                        reason="partially_paid"
                    )
                except Exception as e:
                    bot_logger.error(f"❌ Failed to send partial payment notification: {e}")
        
        elif payment_status in ('confirming', 'confirmed', 'sending'):
            # Промежуточные статусы — только лог, уведомления не нужны
            bot_logger.info(f"⏳ Payment in progress for {order_id}: {payment_status}")
        
        return {'status': 'ok'}
    
    except Exception as e:
        bot_logger.error(f"Error handling NOWPayments webhook: {e}", exc_info=True)
        return {'status': 'error', 'message': str(e)}
