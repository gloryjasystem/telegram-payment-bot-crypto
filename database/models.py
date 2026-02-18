"""
Модели базы данных для Telegram Payment Bot
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger, String, Text, DateTime, Numeric, Integer,
    ForeignKey, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import Optional, List


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class User(Base):
    """
    Модель пользователя Telegram
    
    Хранит информацию о пользователях, которые взаимодействуют с ботом
    """
    __tablename__ = "users"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Telegram данные
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Admin и блокировка
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    blocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    blocked_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="user")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Invoice(Base):
    """
    Модель инвойса (счета на оплату)
    
    Хранит информацию о выставленных счетах для оплаты услуг.
    Каждый инвойс привязан к пользователю Telegram и создаётся администратором.
    """
    __tablename__ = "invoices"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Уникальный человеко-читаемый ID (INV-2024-XXXXX)
    invoice_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    
    # Пользователь-получатель счёта
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Сумма и валюта
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    
    # Описание услуги
    service_description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Статус жизненного цикла: pending → paid / expired / cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    
    # Данные платёжной системы
    payment_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_invoice_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Администратор, создавший инвойс (telegram_id)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    # ID сообщения бота в чате пользователя (для редактирования при отмене)
    bot_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="invoices")
    
    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, invoice_id={self.invoice_id}, amount={self.amount}, status={self.status})>"


class Payment(Base):
    """
    Модель платежа (запись об оплате инвойса)
    
    Создаётся при подтверждении оплаты от платёжного провайдера.
    Содержит информацию о способе, провайдере и категории оплаты.
    """
    __tablename__ = "payments"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Человеко-читаемый ID инвойса (INV-xxx)
    invoice_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # ID транзакции у платёжного провайдера
    transaction_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Категория оплаты: crypto / card_ru / card_int
    payment_category: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Платёжный провайдер: nowpayments / lava / wayforpay
    payment_provider: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    
    # Конкретный метод оплаты: BTC, ETH, USDT, card и т.д.
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Email клиента (для карточных оплат)
    client_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, invoice_id={self.invoice_id}, transaction_id={self.transaction_id}, provider={self.payment_provider}, method={self.payment_method})>"


# Индексы для оптимизации запросов
Index("idx_invoices_status_created", Invoice.status, Invoice.created_at)
Index("idx_payments_category", Payment.payment_category)
Index("idx_payments_provider", Payment.payment_provider)

