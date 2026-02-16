"""
Сервис для карточных платежей через Lava.top (РФ) и WayForPay (международные)
"""
import hashlib
import hmac
import json
import time
from typing import Optional, Dict, Any

import aiohttp

from config import Config
from utils.logger import bot_logger


class CardPaymentService:
    """Сервис для создания карточных платежей"""
    
    LAVA_API_URL = "https://api.lava.top/business/invoice/create"
    WAYPAY_API_URL = "https://api.wayforpay.com/api"
    
    # ========================================
    # LAVA.TOP (Банк РФ — Рубли)
    # ========================================
    
    async def create_lava_payment(
        self,
        invoice_id: str,
        amount_rub: float,
        email: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Создание платежа через Lava.top
        
        Args:
            invoice_id: ID инвойса из бота
            amount_rub: Сумма в рублях
            email: Email покупателя
            description: Описание услуги
            
        Returns:
            dict: {'success': bool, 'payment_url': str} или {'success': False, 'error': str}
        """
        try:
            if not Config.LAVA_SECRET_KEY:
                return {'success': False, 'error': 'LAVA_SECRET_KEY не настроен'}
            
            payload = {
                "sum": amount_rub,
                "orderId": invoice_id,
                "hookUrl": self._get_webhook_url("lava"),
                "successUrl": "https://t.me",
                "failUrl": "https://t.me",
                "expire": 3600,  # 1 час
                "customFields": invoice_id,
                "comment": description,
                "buyerEmail": email
            }
            
            # Lava.top signature: SHA256 HMAC of JSON body
            body_json = json.dumps(payload, separators=(',', ':'))
            signature = hmac.new(
                Config.LAVA_SECRET_KEY.encode(),
                body_json.encode(),
                hashlib.sha256
            ).hexdigest()
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Signature": signature
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.LAVA_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    result = await resp.json()
                    bot_logger.info(f"Lava.top response: {resp.status} — {result}")
                    
                    if resp.status == 200 and result.get("data", {}).get("url"):
                        return {
                            'success': True,
                            'payment_url': result["data"]["url"],
                            'payment_id': result["data"].get("id", "")
                        }
                    else:
                        error_msg = result.get("message", result.get("error", "Unknown error"))
                        return {'success': False, 'error': f"Lava.top: {error_msg}"}
        
        except Exception as e:
            bot_logger.error(f"Error creating Lava.top payment: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def verify_lava_webhook(self, data: dict, signature: str) -> bool:
        """Проверка подписи вебхука от Lava.top"""
        try:
            if not Config.LAVA_SECRET_KEY:
                return False
            body_json = json.dumps(data, separators=(',', ':'))
            expected = hmac.new(
                Config.LAVA_SECRET_KEY.encode(),
                body_json.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            bot_logger.error(f"Lava webhook signature verification error: {e}")
            return False
    
    # ========================================
    # WAYPAY (Иностранный банк — USD)
    # ========================================
    
    async def create_waypay_payment(
        self,
        invoice_id: str,
        amount_usd: float,
        email: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Создание платежа через WayForPay
        
        Args:
            invoice_id: ID инвойса из бота
            amount_usd: Сумма в USD
            email: Email покупателя
            description: Описание услуги
            
        Returns:
            dict: {'success': bool, 'payment_url': str} или {'success': False, 'error': str}
        """
        try:
            if not Config.WAYPAY_MERCHANT_LOGIN or not Config.WAYPAY_MERCHANT_SECRET:
                return {'success': False, 'error': 'WayForPay credentials не настроены'}
            
            merchant_domain = self._get_base_domain()
            order_date = int(time.time())
            
            # Format amounts consistently (WayForPay/PHP uses '10' not '10.0')
            amount_str = self._format_amount(amount_usd)
            
            # Параметры для подписи (порядок важен!)
            sign_string = ";".join([
                Config.WAYPAY_MERCHANT_LOGIN,
                merchant_domain,
                invoice_id,
                str(order_date),
                amount_str,
                "USD",
                description,
                "1",
                amount_str
            ])
            
            bot_logger.debug(f"WayForPay sign_string: {sign_string}")
            
            signature = hmac.new(
                Config.WAYPAY_MERCHANT_SECRET.encode(),
                sign_string.encode(),
                hashlib.md5
            ).hexdigest()
            
            # Amount as number for JSON payload
            amount_num = int(amount_usd) if amount_usd == int(amount_usd) else round(amount_usd, 2)
            
            payload = {
                "transactionType": "CREATE_INVOICE",
                "merchantAccount": Config.WAYPAY_MERCHANT_LOGIN,
                "merchantDomainName": merchant_domain,
                "merchantSignature": signature,
                "apiVersion": 1,
                "language": "RU",
                "serviceUrl": self._get_webhook_url("waypay"),
                "orderReference": invoice_id,
                "orderDate": order_date,
                "amount": amount_num,
                "currency": "USD",
                "productName": [description],
                "productPrice": [amount_num],
                "productCount": [1],
                "clientEmail": email
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.WAYPAY_API_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    result = await resp.json()
                    bot_logger.info(f"WayForPay response: {resp.status} — {result}")
                    
                    if result.get("invoiceUrl"):
                        return {
                            'success': True,
                            'payment_url': result["invoiceUrl"],
                            'payment_id': result.get("orderReference", "")
                        }
                    else:
                        error_msg = result.get("reason", result.get("reasonCode", "Unknown error"))
                        return {'success': False, 'error': f"WayForPay: {error_msg}"}
        
        except Exception as e:
            bot_logger.error(f"Error creating WayForPay payment: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def verify_waypay_webhook(self, data: dict) -> bool:
        """Проверка подписи вебхука от WayForPay"""
        try:
            if not Config.WAYPAY_MERCHANT_SECRET:
                return False
            
            # WayForPay signature строится из определённых полей
            sign_fields = [
                data.get("merchantAccount", ""),
                data.get("orderReference", ""),
                str(data.get("amount", "")),
                data.get("currency", ""),
                str(data.get("authCode", "")),
                data.get("cardPan", ""),
                data.get("transactionStatus", ""),
                data.get("reasonCode", "")
            ]
            sign_string = ";".join(sign_fields)
            
            expected = hmac.new(
                Config.WAYPAY_MERCHANT_SECRET.encode(),
                sign_string.encode(),
                hashlib.md5
            ).hexdigest()
            
            return hmac.compare_digest(expected, data.get("merchantSignature", ""))
        except Exception as e:
            bot_logger.error(f"WayForPay webhook signature verification error: {e}")
            return False
    
    # ========================================
    # Helpers
    # ========================================
    
    @staticmethod
    def _format_amount(amount: float) -> str:
        """Format amount for WayForPay signature (PHP-compatible)"""
        if amount == int(amount):
            return str(int(amount))  # 10.0 -> '10'
        return f"{amount:.2f}"  # 10.55 -> '10.55'
    
    def _get_base_domain(self) -> str:
        """Получение домена для WayForPay"""
        config = Config()
        base_url = config.BASE_WEBHOOK_URL
        if base_url:
            # Убираем https://
            return base_url.replace("https://", "").replace("http://", "").split("/")[0]
        return "localhost"
    
    def _get_webhook_url(self, provider: str) -> str:
        """Формирование URL для вебхука"""
        config = Config()
        base_url = config.BASE_WEBHOOK_URL
        if provider == "lava":
            return f"{base_url}{Config.LAVA_WEBHOOK_PATH}"
        elif provider == "waypay":
            return f"{base_url}{Config.WAYPAY_WEBHOOK_PATH}"
        return ""


# Глобальный экземпляр
card_payment_service = CardPaymentService()
