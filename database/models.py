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
    
    Хранит информацию о выставленных счетах для оплаты услуг
    """
    __tablename__ = "invoices"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Invoice данные
    invoice_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    service_description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Статус: pending, paid, expired, cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    
    # Cryptomus данные
    payment_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cryptomus_invoice_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Администратор, создавший инвойс
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="invoices")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="invoice")
    
    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, invoice_id={self.invoice_id}, amount={self.amount}, status={self.status})>"


class Payment(Base):
    """
    Модель платежа
    
    Хранит информацию о фактических платежных транзакциях от Cryptomus
    """
    __tablename__ = "payments"
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Payment данные
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Метод оплаты (BTC, ETH, USDT и т.д.)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, transaction_id={self.transaction_id}, amount={self.amount}, status={self.status})>"


# Индексы для оптимизации запросов
Index("idx_invoices_status_created", Invoice.status, Invoice.created_at)
Index("idx_payments_status", Payment.status)
