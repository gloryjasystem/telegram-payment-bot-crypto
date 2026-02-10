"""
Сервис для работы с платежами через NOWPayments API
"""
import aiohttp
import hashlib
import hmac
import json
from typing import Optional, Dict, Any
from datetime import datetime

from config import Config
from utils.logger import bot_logger, log_payment
from database.models import Invoice


class NOWPaymentsAPIError(Exception):
    """Исключение для ошибок NOWPayments API"""
    pass


class NOWPaymentsService:
    """Сервис для интеграции с NOWPayments API"""
    
    BASE_URL = "https://api.nowpayments.io/v1"
    
    def __init__(self):
        self.api_key = Config.NOWPAYMENTS_API_KEY
        self.ipn_secret = Config.NOWPAYMENTS_IPN_SECRET
        
        # Проверка наличия API ключей
        self.is_configured = (
            self.api_key and 
            self.api_key != "your_api_key_here"
        )
        
        if not self.is_configured:
            bot_logger.warning("⚠️ NOWPayments API not configured")
    
    async def create_payment(self, invoice: Invoice) -> Dict[str, Any]:
        """
        Создание платежа через NOWPayments Invoice API
        
        Args:
            invoice: Объект инвойса из БД
        
        Returns:
            dict: Результат создания платежа
                - success: bool
                - payment_url: str (URL для оплаты)
                - payment_id: str (ID от NOWPayments)
                - error: str (если есть ошибка)
        """
        if not self.is_configured:
            bot_logger.error("NOWPayments API not configured!")
            return {
                'success': False,
                'error': 'Payment gateway not configured'
            }
        
        try:
            # Данные для создания инвойса
            payload = {
                "price_amount": float(invoice.amount),
                "price_currency": invoice.currency.lower(),
                "order_id": invoice.invoice_id,
                "order_description": invoice.service_description[:255],  # Max 255 символов
                "ipn_callback_url": Config.NOWPAYMENTS_WEBHOOK_URL if hasattr(Config, 'NOWPAYMENTS_WEBHOOK_URL') else None,
                "success_url": f"https://t.me/{Config.SUPPORT_USERNAME}",
                "cancel_url": f"https://t.me/{Config.SUPPORT_USERNAME}",
            }
            
            # Удаляем None значения
            payload = {k: v for k, v in payload.items() if v is not None}
            
            # Заголовки
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json"
            }
            
            bot_logger.info(f"Creating NOWPayments invoice for {invoice.invoice_id}")
            
            # HTTP запрос
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/invoice",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200:
                        error_msg = result.get('message', 'Unknown error')
                        bot_logger.error(f"NOWPayments API error: {error_msg}")
                        raise NOWPaymentsAPIError(f"API error: {error_msg}")
                    
                    payment_id = result['id']
                    invoice_url = result['invoice_url']
                    
                    log_payment(
                        invoice.invoice_id,
                        float(invoice.amount),
                        "created"
                    )
                    
                    bot_logger.info(f"✅ Payment created: {payment_id}")
                    
                    return {
                        'success': True,
                        'payment_url': invoice_url,
                        'payment_id': str(payment_id),
                        'status': 'waiting'
                    }
        
        except aiohttp.ClientError as e:
            bot_logger.error(f"HTTP error creating payment: {e}")
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except NOWPaymentsAPIError as e:
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            bot_logger.error(f"Unexpected error creating payment: {e}", exc_info=True)
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    async def check_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """
        Проверка статуса платежа в NOWPayments
        
        Args:
            payment_id: ID платежа в NOWPayments
        
        Returns:
            dict: Информация о платеже
        """
        if not self.is_configured:
            return {
                'success': False,
                'error': 'Payment gateway not configured'
            }
        
        try:
            headers = {
                "x-api-key": self.api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/payment/{payment_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200:
                        raise NOWPaymentsAPIError("Failed to check payment status")
                    
                    return {
                        'success': True,
                        'status': result['payment_status'],
                        'is_paid': result['payment_status'] in ['finished', 'confirmed'],
                        'amount': result.get('price_amount'),
                        'currency': result.get('price_currency')
                    }
        
        except Exception as e:
            bot_logger.error(f"Error checking payment status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_ipn_signature(self, request_body: bytes, signature: str) -> bool:
        """
        Проверка подписи IPN от NOWPayments
        
        Args:
            request_body: Тело запроса (bytes)
            signature: Подпись из заголовка x-nowpayments-sig
        
        Returns:
            bool: True если подпись валидна
        """
        if not self.is_configured or not self.ipn_secret:
            bot_logger.warning("IPN signature check skipped - not configured")
            return False
        
        try:
            # NOWPayments требует сортировку ключей перед вычислением подписи
            data = json.loads(request_body)
            sorted_data = json.dumps(data, sort_keys=True, separators=(',', ':'))
            
            # Вычисляем ожидаемую подпись HMAC SHA512
            expected_signature = hmac.new(
                self.ipn_secret.encode('utf-8'),
                sorted_data.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()
            
            # Сравниваем (защита от timing-атак)
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if not is_valid:
                bot_logger.warning("⚠️ Invalid IPN signature!")
            
            return is_valid
        
        except Exception as e:
            bot_logger.error(f"Error verifying IPN signature: {e}")
            return False
    
    async def process_ipn(self, ipn_data: dict) -> Dict[str, Any]:
        """
        Обработка IPN (Instant Payment Notification) от NOWPayments
        
        Args:
            ipn_data: Данные из IPN
        
        Returns:
            dict: Результат обработки
        """
        try:
            order_id = ipn_data.get('order_id')  # Наш invoice_id
            payment_status = ipn_data.get('payment_status')
            payment_id = ipn_data.get('payment_id')
            
            bot_logger.info(f"Processing IPN for order {order_id}, status: {payment_status}")
            
            # Маппинг статусов NOWPayments
            # waiting - ожидание оплаты
            # confirming - подтверждение в блокчейне
            # confirmed - подтверждено
            # sending - отправка на payout address
            # partially_paid - частичная оплата
            # finished - завершено успешно
            # failed - провал
            # refunded - возврат
            # expired - истек срок
            
            is_paid = payment_status in ['finished', 'confirmed']
            is_failed = payment_status in ['failed', 'expired']
            is_partial = payment_status == 'partially_paid'
            
            return {
                'success': True,
                'order_id': order_id,
                'payment_id': payment_id,
                'status': payment_status,
                'is_paid': is_paid,
                'is_failed': is_failed,
                'is_partial': is_partial,
                'amount': ipn_data.get('price_amount'),
                'currency': ipn_data.get('price_currency'),
                'pay_amount': ipn_data.get('pay_amount'),
                'pay_currency': ipn_data.get('pay_currency')
            }
        
        except Exception as e:
            bot_logger.error(f"Error processing IPN: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Глобальный экземпляр сервиса
nowpayments_service = NOWPaymentsService()
