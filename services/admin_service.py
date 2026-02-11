"""
Сервис для админских операций
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from database.models import User, Invoice, Payment
from utils.logger import bot_logger


class AdminService:
    """Сервис для управления пользователями и аналитики"""
    
    async def block_user(
        self,
        user_id: int,
        admin_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """
        Блокировка пользователя
        
        Args:
            user_id: Telegram ID пользователя для блокировки
            admin_id: Telegram ID админа, который блокирует
            reason: Причина блокировки (опционально)
        
        Returns:
            bool: True если успешно заблокирован
        """
        try:
            async with get_session() as session:
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id)
                )
                
                if not user:
                    bot_logger.warning(f"User {user_id} not found for blocking")
                    return False
                
                if user.is_blocked:
                    bot_logger.warning(f"User {user_id} already blocked")
                    return False
                
                # Блокируем пользователя
                user.is_blocked = True
                user.blocked_at = datetime.utcnow()
                user.blocked_by = admin_id
                
                await session.commit()
                
                bot_logger.info(f"User {user_id} blocked by admin {admin_id}")
                return True
                
        except Exception as e:
            bot_logger.error(f"Error blocking user {user_id}: {e}", exc_info=True)
            return False
    
    async def unblock_user(self, user_id: int) -> bool:
        """
        Разблокировка пользователя
        
        Args:
            user_id: Telegram ID пользователя
        
        Returns:
            bool: True если успешно разблокирован
        """
        try:
            async with get_session() as session:
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id)
                )
                
                if not user:
                    bot_logger.warning(f"User {user_id} not found for unblocking")
                    return False
                
                if not user.is_blocked:
                    bot_logger.warning(f"User {user_id} is not blocked")
                    return False
                
                # Разблокируем
                user.is_blocked = False
                user.blocked_at = None
                user.blocked_by = None
                
                await session.commit()
                
                bot_logger.info(f"User {user_id} unblocked")
                return True
                
        except Exception as e:
            bot_logger.error(f"Error unblocking user {user_id}: {e}", exc_info=True)
            return False
    
    async def add_admin(self, user_id: int, granter_id: int) -> bool:
        """
        Выдача админских прав
        
        Args:
            user_id: Telegram ID пользователя
            granter_id: ID админа, который выдает права
        
        Returns:
            bool: True если успешно
        """
        try:
            async with get_session() as session:
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id)
                )
                
                if not user:
                    bot_logger.warning(f"User {user_id} not found for admin grant")
                    return False
                
                if user.is_admin:
                    bot_logger.warning(f"User {user_id} is already admin")
                    return False
                
                user.is_admin = True
                await session.commit()
                
                bot_logger.info(f"Admin rights granted to {user_id} by {granter_id}")
                return True
                
        except Exception as e:
            bot_logger.error(f"Error granting admin to {user_id}: {e}", exc_info=True)
            return False
    
    async def remove_admin(self, user_id: int, remover_id: int) -> bool:
        """
        Снятие админских прав
        
        Args:
            user_id: Telegram ID пользователя
            remover_id: ID админа, который снимает права
        
        Returns:
            bool: True если успешно
        """
        try:
            async with get_session() as session:
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id)
                )
                
                if not user:
                    bot_logger.warning(f"User {user_id} not found for admin removal")
                    return False
                
                if not user.is_admin:
                    bot_logger.warning(f"User {user_id} is not admin")
                    return False
                
                # Проверка что не последний админ
                admin_count = await session.scalar(
                    select(func.count()).select_from(User).where(User.is_admin == True)
                )
                
                if admin_count <= 1:
                    bot_logger.warning("Cannot remove last admin")
                    return False
                
                user.is_admin = False
                await session.commit()
                
                bot_logger.info(f"Admin rights removed from {user_id} by {remover_id}")
                return True
                
        except Exception as e:
            bot_logger.error(f"Error removing admin from {user_id}: {e}", exc_info=True)
            return False
    
    async def get_users_list(
        self,
        status: str = "all",
        limit: int = 50,
        offset: int = 0
    ) -> List[User]:
        """
        Получение списка пользователей с фильтром
        
        Args:
            status: "all", "active", "blocked", "admins"
            limit: Максимум пользователей
            offset: Смещение для пагинации
        
        Returns:
            List[User]: Список пользователей
        """
        try:
            async with get_session() as session:
                query = select(User)
                
                if status == "blocked":
                    query = query.where(User.is_blocked == True)
                elif status == "active":
                    query = query.where(User.is_blocked == False)
                elif status == "admins":
                    query = query.where(User.is_admin == True)
                
                query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)
                
                result = await session.execute(query)
                users = result.scalars().all()
                
                return list(users)
                
        except Exception as e:
            bot_logger.error(f"Error getting users list: {e}", exc_info=True)
            return []
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получение общей статистики бота
        
        Returns:
            Dict с метриками
        """
        try:
            async with get_session() as session:
                # Общее количество пользователей
                total_users = await session.scalar(
                    select(func.count()).select_from(User)
                )
                
                # Заблокированные пользователи
                blocked_users = await session.scalar(
                    select(func.count()).select_from(User).where(User.is_blocked == True)
                )
                
                # Активные админы
                admin_count = await session.scalar(
                    select(func.count()).select_from(User).where(User.is_admin == True)
                )
                
                # Статистика инвойсов
                total_invoices = await session.scalar(
                    select(func.count()).select_from(Invoice)
                )
                
                paid_invoices = await session.scalar(
                    select(func.count()).select_from(Invoice).where(Invoice.status == 'paid')
                )
                
                pending_invoices = await session.scalar(
                    select(func.count()).select_from(Invoice).where(Invoice.status == 'pending')
                )
                
                cancelled_invoices = await session.scalar(
                    select(func.count()).select_from(Invoice).where(Invoice.status == 'cancelled')
                )
                
                # Общий доход
                total_revenue = await session.scalar(
                    select(func.sum(Invoice.amount)).where(Invoice.status == 'paid')
                ) or Decimal('0.00')
                
                # Конверсия
                conversion_rate = (paid_invoices / total_invoices * 100) if total_invoices > 0 else 0
                
                return {
                    'total_users': total_users or 0,
                    'active_users': (total_users or 0) - (blocked_users or 0),
                    'blocked_users': blocked_users or 0,
                    'admin_count': admin_count or 0,
                    'total_invoices': total_invoices or 0,
                    'paid_invoices': paid_invoices or 0,
                    'pending_invoices': pending_invoices or 0,
                    'cancelled_invoices': cancelled_invoices or 0,
                    'total_revenue': total_revenue,
                    'conversion_rate': round(conversion_rate, 2)
                }
                
        except Exception as e:
            bot_logger.error(f"Error getting statistics: {e}", exc_info=True)
            return {}
    
    async def get_revenue_report(self, period: str = "all") -> Dict[str, Any]:
        """
        Отчет по доходам за период
        
        Args:
            period: "today", "week", "month", "all"
        
        Returns:
            Dict с отчетом
        """
        try:
            async with get_session() as session:
                # Определяем временной период
                now = datetime.utcnow()
                start_date = None
                
                if period == "today":
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif period == "week":
                    start_date = now - timedelta(days=7)
                elif period == "month":
                    start_date = now - timedelta(days=30)
                
                # Базовый запрос
                query = select(Invoice).where(Invoice.status == 'paid').options(selectinload(Invoice.payments))
                
                if start_date:
                    query = query.where(Invoice.paid_at >= start_date)
                
                result = await session.execute(query)
                invoices = result.scalars().all()
                
                if not invoices:
                    return {
                        'period': period,
                        'total_revenue': Decimal('0.00'),
                        'invoice_count': 0,
                        'average_amount': Decimal('0.00'),
                        'top_currency': 'USD'
                    }
                
                total_revenue = sum(inv.amount for inv in invoices)
                invoice_count = len(invoices)
                average_amount = total_revenue / invoice_count if invoice_count > 0 else Decimal('0.00')
                
                # Топ криптовалюта (из payments)
                payment_methods = {}
                for invoice in invoices:
                    for payment in invoice.payments:
                        method = payment.payment_method or 'Unknown'
                        payment_methods[method] = payment_methods.get(method, 0) + 1
                
                top_currency = max(payment_methods, key=payment_methods.get) if payment_methods else 'USDT'
                
                return {
                    'period': period,
                    'total_revenue': total_revenue,
                    'invoice_count': invoice_count,
                    'average_amount': average_amount,
                    'top_currency': top_currency,
                    'payment_methods': payment_methods
                }
                
        except Exception as e:
            bot_logger.error(f"Error getting revenue report: {e}", exc_info=True)
            return {}
    
    async def is_user_blocked(self, user_id: int) -> bool:
        """
        Проверка заблокирован ли пользователь
        
        Args:
            user_id: Telegram ID
        
        Returns:
            bool: True если заблокирован
        """
        try:
            async with get_session() as session:
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id)
                )
                
                return user.is_blocked if user else False
                
        except Exception as e:
            bot_logger.error(f"Error checking if user blocked: {e}", exc_info=True)
            return False
    
    async def is_user_admin(self, user_id: int) -> bool:
        """
        Проверка является ли пользователь админом
        
        Args:
            user_id: Telegram ID
        
        Returns:
            bool: True если админ
        """
        try:
            async with get_session() as session:
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id)
                )
                
                return user.is_admin if user else False
                
        except Exception as e:
            bot_logger.error(f"Error checking if user is admin: {e}", exc_info=True)
            return False


# Создаем глобальный экземпляр сервиса
admin_service = AdminService()
