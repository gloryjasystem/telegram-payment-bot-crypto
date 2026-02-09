"""
Сервис для работы с платежами через Cryptomus API
"""
import aiohttp
import hashlib
import hmac
import json
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime

from config import Config
from utils.logger import bot_logger, log_payment
from database.models import Invoice


class CryptomusAPIError(Exception):
    """Исключение для ошибок Cryptomus API"""
    pass


class PaymentService:
    """Сервис для интеграции с Cryptomus API"""
    
    BASE_URL = "https://api.cryptomus.com/v1"
    
    def __init__(self):
        self.api_key = Config.CRYPTOMUS_API_KEY
        self.merchant_id = Config.CRYPTOMUS_MERCHANT_ID
        self.webhook_secret = Config.CRYPTOMUS_WEBHOOK_SECRET
        
        # Проверка наличия API ключей
        self.is_configured = (
            self.api_key and 
            self.api_key != "your_cryptomus_api_key_here" and
            self.merchant_id and
            self.merchant_id != "your_merchant_id_here"
        )
        
        if not self.is_configured:
            bot_logger.warning("⚠️ Cryptomus API not configured - using MOCK mode")
    
    def _generate_signature(self, data: dict) -> str:
        """
        Генерация подписи для запроса к Cryptomus API
        
        Args:
            data: Данные запроса
        
        Returns:
            str: MD5 хэш подписи
        """
        # Сортируем данные и создаем JSON строку
        json_data = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        
        # Создаем строку для подписи
        sign_string = json_data + self.api_key
        
        # MD5 хэш
        return hashlib.md5(sign_string.encode()).hexdigest()
    
    async def create_payment(self, invoice: Invoice) -> Dict[str, Any]:
        """
        Создание платежа через Cryptomus API
        
        Args:
            invoice: Объект инвойса из БД
        
        Returns:
            dict: Результат создания платежа
                - success: bool
                - payment_url: str (URL для оплаты)
                - cryptomus_invoice_id: str (UUID от Cryptomus)
                - error: str (если есть ошибка)
        
        Example:
            >>> result = await payment_service.create_payment(invoice)
            >>> if result['success']:
            >>>     payment_url = result['payment_url']
        """
        # MOCK режим (если API не настроен)
        if not self.is_configured:
            bot_logger.warning(f"Creating MOCK payment for invoice {invoice.invoice_id}")
            return {
                'success': True,
                'payment_url': f"https://example.com/mock-payment/{invoice.invoice_id}",
                'cryptomus_invoice_id': f"MOCK-{invoice.invoice_id}",
                'status': 'mock'
            }
        
        # Реальный вызов Cryptomus API
        try:
            # Данные для создания платежа
            payload = {
                "amount": str(invoice.amount),
                "currency": invoice.currency,
                "order_id": invoice.invoice_id,
                "merchant_id": self.merchant_id,
                "lifetime": 3600,  # 1 час
                "to_currency": "USDT",  # Валюта для приема платежа
            }
            
            # Генерация подписи
            signature = self._generate_signature(payload)
            
            # Заголовки
            headers = {
                "merchant": self.merchant_id,
                "sign": signature,
                "Content-Type": "application/json"
            }
            
            # HTTP запрос
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/payment",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200 or result.get('state') != 0:
                        error_msg = result.get('message', 'Unknown error')
                        bot_logger.error(f"Cryptomus API error: {error_msg}")
                        raise CryptomusAPIError(f"API error: {error_msg}")
                    
                    payment_data = result['result']
                    
                    log_payment(
                        invoice.invoice_id,
                        float(invoice.amount),
                        "created"
                    )
                    
                    return {
                        'success': True,
                        'payment_url': payment_data['url'],
                        'cryptomus_invoice_id': payment_data['uuid'],
                        'status': 'pending'
                    }
        
        except aiohttp.ClientError as e:
            bot_logger.error(f"HTTP error creating payment: {e}")
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except CryptomusAPIError as e:
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
    
    async def check_payment_status(self, cryptomus_invoice_id: str) -> Dict[str, Any]:
        """
        Проверка статуса платежа в Cryptomus
        
        Args:
            cryptomus_invoice_id: UUID платежа в Cryptomus
        
        Returns:
            dict: Информация о платеже
        """
        if not self.is_configured:
            return {
                'success': True,
                'status': 'mock',
                'is_paid': False
            }
        
        try:
            payload = {
                "uuid": cryptomus_invoice_id,
                "merchant_id": self.merchant_id
            }
            
            signature = self._generate_signature(payload)
            
            headers = {
                "merchant": self.merchant_id,
                "sign": signature,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/payment/info",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200:
                        raise CryptomusAPIError("Failed to check payment status")
                    
                    payment = result['result']
                    
                    return {
                        'success': True,
                        'status': payment['payment_status'],
                        'is_paid': payment['payment_status'] == 'paid',
                        'amount': payment['payment_amount'],
                        'currency': payment['currency']
                    }
        
        except Exception as e:
            bot_logger.error(f"Error checking payment status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_webhook_signature(self, request_body: bytes, signature: str) -> bool:
        """
        Проверка подписи webhook от Cryptomus
        
        Args:
            request_body: Тело запроса (bytes)
            signature: Подпись из заголовка
        
        Returns:
            bool: True если подпись валидна
        """
        if not self.is_configured:
            bot_logger.warning("Webhook signature check skipped - MOCK mode")
            return True
        
        try:
            # Вычисляем ожидаемую подпись
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                request_body,
                hashlib.sha256
            ).hexdigest()
            
            # Сравниваем
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if not is_valid:
                bot_logger.warning("⚠️ Invalid webhook signature!")
            
            return is_valid
        
        except Exception as e:
            bot_logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    async def process_webhook(self, webhook_data: dict) -> Dict[str, Any]:
        """
        Обработка webhook от Cryptomus
        
        Args:
            webhook_data: Данные из webhook
        
        Returns:
            dict: Результат обработки
        """
        try:
            order_id = webhook_data.get('order_id')  # Наш invoice_id
            status = webhook_data.get('status')
            payment_amount = webhook_data.get('payment_amount')
            
            bot_logger.info(f"Processing webhook for order {order_id}, status: {status}")
            
            return {
                'success': True,
                'order_id': order_id,
                'status': status,
                'amount': payment_amount,
                'is_paid': status == 'paid'
            }
        
        except Exception as e:
            bot_logger.error(f"Error processing webhook: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Глобальный экземпляр сервиса
payment_service = PaymentService()
