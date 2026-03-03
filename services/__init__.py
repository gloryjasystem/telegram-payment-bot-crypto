"""
Services package
Содержит бизнес-логику: платежи, инвойсы, уведомления
"""

from .nowpayments_service import nowpayments_service, NOWPaymentsAPIError
from .invoice_service import InvoiceService, invoice_service
from .notification_service import NotificationService
from .admin_service import AdminService, admin_service

# Обратная совместимость — payment_service = nowpayments_service
payment_service = nowpayments_service

__all__ = [
    "nowpayments_service",
    "NOWPaymentsAPIError",
    "payment_service",
    "InvoiceService",
    "invoice_service",
    "NotificationService",
    "AdminService",
    "admin_service"
]
