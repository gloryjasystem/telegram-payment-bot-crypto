"""
Сервис для карточных платежей через Lava.top (РФ) и WayForPay (международные)
"""
import hashlib
import hmac
import json
import math
import time
from typing import Optional, Dict, Any, Tuple

import aiohttp

from config import Config
from utils.logger import bot_logger
from utils.http_retry import api_request_with_retry


class CardPaymentService:
    """Сервис для создания карточных платежей"""
    
    LAVA_API_URL = "https://gate.lava.top/api/v3/invoice"
    WAYPAY_API_URL = "https://api.wayforpay.com/api"
    
    # Маппинг ключевых слов из описания услуги → короткий тип
    SERVICE_TYPE_MAP = {
        "реклам": "ad",       # "Размещение рекламы" → "ad"
        "верификац": "ver",   # "Верификация профилей" → "ver"
        "сертификац": "ver",  # "Сертификация" → "ver"
    }
    
    def _get_lava_offer_id(self, amount_rub: float, description: str) -> Tuple[str, int]:
        """
        Определяет offer_id по описанию услуги и сумме.
        Ищет ближайший оффер для данного типа услуги.
        
        Приоритет: точное совпадение → ближайший >= сумма → ближайший < сумма
        """
        # 1. Определить тип услуги по ключевым словам
        service_type = "ad"  # default
        desc_lower = description.lower()
        for keyword, stype in self.SERVICE_TYPE_MAP.items():
            if keyword in desc_lower:
                service_type = stype
                break
        
        target = int(amount_rub)
        
        # 2. Собрать все офферы для этого типа услуги
        prefix = f"{service_type}_"
        available_offers = {}
        for key, offer_id in Config.LAVA_OFFER_MAP.items():
            if key.startswith(prefix):
                try:
                    price = int(key[len(prefix):])
                    available_offers[price] = offer_id
                except ValueError:
                    continue
        
        if not available_offers:
            raise ValueError(
                f"Нет офферов для типа '{service_type}' (услуга: {description}). "
                f"Доступные ключи: {list(Config.LAVA_OFFER_MAP.keys())}"
            )
        
        # 3. Точное совпадение
        if target in available_offers:
            bot_logger.info(f"🔍 Offer: {description} {target}₽ → exact match → {available_offers[target]}")
            return available_offers[target], target
        
        # 4. Ближайший оффер >= суммы
        higher = sorted([p for p in available_offers if p >= target])
        if higher:
            best = higher[0]
            bot_logger.info(f"🔍 Offer: {description} {target}₽ → nearest↑ {best}₽ → {available_offers[best]}")
            return available_offers[best], best
        
        # 5. Если нет >= суммы, берём максимальный доступный
        best = max(available_offers.keys())
        bot_logger.warning(f"⚠️ Offer: {description} {target}₽ → нет оффера >= суммы, используем максимальный {best}₽")
        return available_offers[best], best
    
    # ========================================
    # LAVA.TOP V3 (Банк РФ — Рубли)
    # ========================================
    
    async def create_lava_payment(
        self,
        invoice_id: str,
        amount_rub: float,
        email: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Создание платежа через Lava.top V3 API
        
        Args:
            invoice_id: ID инвойса из бота
            amount_rub: Сумма в рублях
            email: Email покупателя
            description: Описание услуги
            
        Returns:
            dict: {'success': bool, 'payment_url': str} или {'success': False, 'error': str}
        """
        try:
            if not Config.LAVA_API_KEY:
                return {'success': False, 'error': 'LAVA_API_KEY не настроен'}
            if not Config.LAVA_OFFER_MAP:
                return {'success': False, 'error': 'LAVA_OFFER_MAP не настроен (нет офферов)'}
            
            # Подбираем offer_id по описанию услуги и сумме
            try:
                offer_id, rounded_amount = self._get_lava_offer_id(amount_rub, description)
            except ValueError as e:
                return {'success': False, 'error': str(e)}
            
            # Payload по Swagger: email + offerId + currency (amount определяется оффером)
            payload = {
                "email": email,
                "offerId": offer_id,
                "currency": "RUB"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Api-Key": Config.LAVA_API_KEY
            }
            
            body_json = json.dumps(payload)
            bot_logger.info(f"🔄 Lava.top V3: POST {self.LAVA_API_URL}")
            bot_logger.info(f"🔄 Payload: {body_json}")
            bot_logger.info(f"🔄 Auth: Bearer {Config.LAVA_API_KEY[:8]}...{Config.LAVA_API_KEY[-4:]}")
            
            resp = await api_request_with_retry(
                "POST", self.LAVA_API_URL,
                headers=headers,
                data=body_json,
                timeout=30,
            )
            
            bot_logger.info(f"Lava.top response: status={resp['status']}")
            bot_logger.info(f"Lava.top body: {resp['body'][:500]}")
            
            result = resp['json']
            if result is None:
                return {'success': False, 'error': f"Lava.top ({resp['status']}): невалидный JSON: {resp['body'][:300]}"}
            
            # Swagger: 201 = успешное создание контракта
            if resp['status'] in (200, 201):
                payment_url = result.get("paymentUrl") or result.get("url")
                payment_id = result.get("id", "")
                
                if payment_url:
                    return {
                        'success': True,
                        'payment_url': payment_url,
                        'payment_id': str(payment_id)
                    }
                else:
                    return {'success': False, 'error': f"Lava.top: URL не получен. Ответ: {result}"}
            else:
                error_msg = result.get("error", result.get("message", str(result)))
                return {'success': False, 'error': f"Lava.top ({resp['status']}): {error_msg}"}
        
        except Exception as e:
            bot_logger.error(f"Error creating Lava.top V3 payment: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def verify_lava_webhook(self, data: dict, signature: str) -> bool:
        """Проверка вебхука от Lava.top (V3 использует Bearer-авторизацию)"""
        try:
            if not Config.LAVA_API_KEY:
                return False
            # V3 webhook может отправлять подпись в заголовке Authorization
            # Проверяем Bearer токен
            if signature.startswith("Bearer "):
                return signature[7:] == Config.LAVA_API_KEY
            # Fallback: проверяем как HMAC если Lava отправляет Signature
            body_json = json.dumps(data, separators=(',', ':'))
            expected = hmac.new(
                Config.LAVA_API_KEY.encode(),
                body_json.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            bot_logger.error(f"Lava webhook verification error: {e}")
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
            # ========== TEST MODE: simulate successful payment ==========
            if Config.WAYPAY_TEST_MODE:
                config = Config()
                base_url = config.BASE_WEBHOOK_URL
                test_url = f"{base_url}/test/waypay-success?invoice_id={invoice_id}&amount={amount_usd}&email={email}&service={description}"
                bot_logger.info(f"🧪 WAYPAY TEST MODE: Returning test payment URL for {invoice_id}")
                return {
                    'success': True,
                    'payment_url': test_url,
                    'payment_id': f'TEST-{invoice_id}'
                }
            
            if not Config.WAYPAY_MERCHANT_LOGIN or not Config.WAYPAY_MERCHANT_SECRET:
                return {'success': False, 'error': 'WayForPay credentials не настроены'}
            
            merchant_domain = self._get_base_domain()
            order_date = int(time.time())
            
            # Unique orderReference to avoid 'Duplicate Order ID' on retries
            unique_order_ref = f"{invoice_id}_ts_{order_date}"
            
            # Format amounts consistently (WayForPay/PHP uses '10' not '10.0')
            amount_str = self._format_amount(amount_usd)
            
            # Параметры для подписи (порядок важен!)
            sign_string = ";".join([
                Config.WAYPAY_MERCHANT_LOGIN,
                merchant_domain,
                unique_order_ref,
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
                "orderReference": unique_order_ref,
                "orderDate": order_date,
                "amount": amount_num,
                "currency": "USD",
                "productName": [description],
                "productPrice": [amount_num],
                "productCount": [1],
                "clientEmail": email
            }
            
            resp = await api_request_with_retry(
                "POST", self.WAYPAY_API_URL,
                json_data=payload,
                timeout=30,
            )
            
            result = resp['json'] or {}
            bot_logger.info(f"WayForPay response: {resp['status']} — {result}")
            
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
                str(data.get("merchantAccount", "")),
                str(data.get("orderReference", "")),
                str(data.get("amount", "")),
                str(data.get("currency", "")),
                str(data.get("authCode", "")),
                str(data.get("cardPan", "")),
                str(data.get("transactionStatus", "")),
                str(data.get("reasonCode", ""))
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
