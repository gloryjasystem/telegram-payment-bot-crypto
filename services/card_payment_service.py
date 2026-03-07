"""
Сервис для карточных платежей через Lava.top (РФ) и WayForPay (международные)
"""
import hashlib
import hmac
import json
import time
from typing import Dict, Any

from config import Config
from utils.logger import bot_logger
from utils.http_retry import api_request_with_retry


class CardPaymentService:
    """Сервис для создания карточных платежей"""
    
    LAVA_API_URL = "https://gate.lava.top/api/v3/invoice"
    WAYPAY_API_URL = "https://api.wayforpay.com/api"
    

    
    # ========================================
    # LAVA.TOP V3 (Банк РФ — Рубли)
    # ========================================
    
    async def create_lava_payment(
        self,
        invoice_id: str,
        offer_id: str,
        amount_rub: float,
        email: str,
        description: str,
        currency: str = "RUB"
    ) -> Dict[str, Any]:
        """
        Создание платежа через Lava.top V3 API с привязкой к нашему invoice_id.

        Args:
            invoice_id: ID инвойса из бота (INV-XXXXX) — передаётся как metadata → придёт в webhook
            offer_id:   UUID оффера из lava_products.json (второй UUID в URL продукта)
            amount_rub: Сумма в рублях (для логирования)
            email:      Email покупателя
            description: Описание услуги (для логирования)
            currency:   Валюта платежа ('RUB' или 'USD'), по умолчанию 'RUB'

        Returns:
            dict: {'success': bool, 'payment_url': str} или {'success': False, 'error': str}
        """
        try:
            if not Config.LAVA_API_KEY:
                return {'success': False, 'error': 'LAVA_API_KEY не настроен'}
            if not offer_id:
                return {'success': False, 'error': 'offer_id не задан для данной услуги'}

            # Payload по Lava.top V3 Swagger:
            #   offerId   — UUID оффера (определяет продукт и цену на Lava.top)
            #   email     — email покупателя (предзаполняется на странице оплаты)
            #   currency  — валюта (RUB или USD)
            #   metadata  — произвольная строка; Lava.top вернёт её в webhook → наш INV-XXXXX
            payload = {
                "email": email,
                "offerId": offer_id,
                "currency": currency,
                "metadata": invoice_id      # ← ключевое поле: вернётся в webhook
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Api-Key": Config.LAVA_API_KEY
            }

            body_json = json.dumps(payload)
            bot_logger.info(f"🔄 Lava.top V3 invoice: POST {self.LAVA_API_URL}")
            bot_logger.info(f"🔄 invoice_id={invoice_id}, offer_id={offer_id}, amount≈{amount_rub}₽, email={email}")

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
                    bot_logger.info(f"✅ Lava.top invoice created: payment_id={payment_id}, url={payment_url}")
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
