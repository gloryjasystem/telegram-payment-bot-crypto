"""
Сервис для работы с платежами через NOWPayments API

Этот файл оставлен для обратной совместимости.
Основная логика платежей — в nowpayments_service.py
"""
from .nowpayments_service import nowpayments_service, NOWPaymentsAPIError

# Псевдоним для удобства
PaymentAPIError = NOWPaymentsAPIError

# Экспортируемый экземпляр сервиса (для обратной совместимости)
payment_service = nowpayments_service
