"""
Управление подключениями к базе данных
"""
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)
from sqlalchemy import text
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from config import Config
from .models import Base

logger = logging.getLogger(__name__)

# Глобальные переменные для engine и session factory
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """
    Инициализация базы данных
    
    Создает async engine и session factory на основе DATABASE_URL из конфига
    """
    global _engine, _async_session_factory
    
    logger.info(f"Инициализация базы данных: {Config.DATABASE_URL.split('@')[0].split('://')[0]}://***")
    
    # Определяем параметры engine в зависимости от типа БД
    engine_kwargs = {
        "echo": False,  # Установите True для отладки SQL запросов
    }
    
    # Параметры pool только для PostgreSQL, SQLite использует NullPool
    if "sqlite" not in Config.DATABASE_URL.lower():
        engine_kwargs.update({
            "pool_pre_ping": True,  # Проверка соединения перед использованием
            "pool_size": 5,  # Размер пула соединений
            "max_overflow": 10  # Максимальное количество дополнительных соединений
        })
    
    # Создание async engine
    _engine = create_async_engine(
        Config.DATABASE_URL,
        **engine_kwargs
    )
    
    # Создание session factory
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Не сбрасывать объекты после commit
        autoflush=False,  # Ручное управление flush
        autocommit=False  # Ручное управление commit
    )


async def check_and_migrate_table() -> None:
    """
    Проверка и миграция таблиц (добавление новых колонок, переименование)
    """
    if _engine is None:
        return
        
    try:
        # Пытаемся проверить только для PostgreSQL
        if "postgresql" not in Config.DATABASE_URL.lower():
            return

        async with _engine.begin() as conn:
            try:
                # --- Users migration (existing) ---
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='users' AND column_name='is_admin';"
                ))
                column_exists = result.scalar() is not None
                
                if not column_exists:
                    logger.warning("⚠️ Обнаружена устаревшая схема БД. Выполняю миграцию users...")
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;"))
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;"))
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMP WITHOUT TIME ZONE;"))
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_by BIGINT;"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_blocked ON users (is_blocked);"))
                    logger.info("✅ Миграция users выполнена")
                
                # --- Invoices migration ---
                await conn.execute(text(
                    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS bot_message_id BIGINT;"
                ))
                
                # Переименование cryptomus_invoice_id → external_invoice_id
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='invoices' AND column_name='cryptomus_invoice_id';"
                ))
                if result.scalar() is not None:
                    logger.warning("⚠️ Переименование cryptomus_invoice_id → external_invoice_id...")
                    await conn.execute(text(
                        "ALTER TABLE invoices RENAME COLUMN cryptomus_invoice_id TO external_invoice_id;"
                    ))
                    logger.info("✅ Колонка переименована")
                
                # Новые поля invoices
                await conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP WITHOUT TIME ZONE;"))
                await conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;"))
                
                # --- Payments migration ---
                # Новые поля
                await conn.execute(text("ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_category VARCHAR(20);"))
                await conn.execute(text("ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_provider VARCHAR(30);"))
                await conn.execute(text("ALTER TABLE payments ADD COLUMN IF NOT EXISTS client_email VARCHAR(255);"))
                
                # Заполняем category и provider из существующего payment_method
                await conn.execute(text("""
                    UPDATE payments SET
                        payment_category = CASE
                            WHEN payment_method LIKE 'card_ru%' THEN 'card_ru'
                            WHEN payment_method LIKE 'card_int%' THEN 'card_int'
                            ELSE 'crypto'
                        END,
                        payment_provider = CASE
                            WHEN payment_method LIKE '%lava%' THEN 'lava'
                            WHEN payment_method LIKE '%waypay%' THEN 'wayforpay'
                            ELSE 'nowpayments'
                        END
                    WHERE payment_category IS NULL AND payment_method IS NOT NULL;
                """))
                
                # Нормализуем payment_method (оставляем только валюту/тип)
                await conn.execute(text("""
                    UPDATE payments SET payment_method = CASE
                        WHEN payment_method = 'card_ru_lava' THEN 'card'
                        WHEN payment_method = 'card_int_waypay' THEN 'card'
                        WHEN payment_method = 'card_int_waypay_TEST' THEN 'card'
                        ELSE payment_method
                    END
                    WHERE payment_method LIKE 'card_%';
                """))
                
                # Удаляем дублирующие поля (проверяем что они существуют)
                for col in ['amount', 'currency', 'status']:
                    result = await conn.execute(text(
                        f"SELECT column_name FROM information_schema.columns "
                        f"WHERE table_name='payments' AND column_name='{col}';"
                    ))
                    if result.scalar() is not None:
                        logger.info(f"🗑️ Удаление payments.{col} (дублирующее поле)...")
                        await conn.execute(text(f"ALTER TABLE payments DROP COLUMN {col};"))
                
                # Индексы для аналитики
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_category ON payments(payment_category);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_provider ON payments(payment_provider);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_invoices_cancelled ON invoices(cancelled_at);"))
                
                # Удаляем старый индекс idx_payments_status
                await conn.execute(text("DROP INDEX IF EXISTS idx_payments_status;"))
                
                # --- Миграция payments.invoice_id: Integer FK → String (INV-xxx) ---
                result = await conn.execute(text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name='payments' AND column_name='invoice_id';"
                ))
                col_type = result.scalar()
                
                if col_type and col_type.lower() == 'integer':
                    logger.warning("⚠️ Миграция payments.invoice_id: Integer FK → VARCHAR (INV-xxx)...")
                    
                    # 1. Удаляем FK constraint
                    await conn.execute(text("""
                        DO $$ DECLARE r RECORD;
                        BEGIN
                            FOR r IN (
                                SELECT constraint_name FROM information_schema.table_constraints
                                WHERE table_name='payments' AND constraint_type='FOREIGN KEY'
                                AND constraint_name LIKE '%invoice%'
                            ) LOOP
                                EXECUTE 'ALTER TABLE payments DROP CONSTRAINT ' || r.constraint_name;
                            END LOOP;
                        END $$;
                    """))
                    
                    # 2. Добавляем временную колонку со строковым invoice_id
                    await conn.execute(text(
                        "ALTER TABLE payments ADD COLUMN invoice_id_new VARCHAR(50);"
                    ))
                    
                    # 3. Заполняем из таблицы invoices (id → invoice_id строковый)
                    await conn.execute(text("""
                        UPDATE payments p
                        SET invoice_id_new = i.invoice_id
                        FROM invoices i
                        WHERE p.invoice_id = i.id;
                    """))
                    
                    # 4. Удаляем старую колонку и переименовываем новую
                    await conn.execute(text("ALTER TABLE payments DROP COLUMN invoice_id;"))
                    await conn.execute(text("ALTER TABLE payments RENAME COLUMN invoice_id_new TO invoice_id;"))
                    await conn.execute(text("ALTER TABLE payments ALTER COLUMN invoice_id SET NOT NULL;"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_invoice_id ON payments(invoice_id);"))
                    
                    logger.info("✅ payments.invoice_id → VARCHAR (INV-xxx) выполнено")
                
                # --- Чистка transaction_id: убираем INV-xxx_ts_ префикс для WayForPay ---
                await conn.execute(text("""
                    UPDATE payments
                    SET transaction_id = split_part(transaction_id, '_ts_', 2)
                    WHERE transaction_id LIKE '%\\_ts\\_%' ESCAPE '\\' AND split_part(transaction_id, '_ts_', 2) != '';
                """))
                
                logger.info("✅ Структура базы данных актуальна")
                
            except Exception as e:
                logger.error(f"Ошибка проверки схемы БД: {e}")
                
    except Exception as e:
        logger.error(f"Critical error during migration check: {e}")


async def create_tables() -> None:
    """
    Создание всех таблиц в базе данных
    
    Вызывайте эту функцию при первом запуске бота
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    
    logger.info("Создание таблиц базы данных...")
    
    async with _engine.begin() as conn:
        # Создание всех таблиц, определенных в Base.metadata
        await conn.run_sync(Base.metadata.create_all)
    
    # Проверка миграций
    await check_and_migrate_table()
    
    logger.info("Таблицы базы данных готовы")


async def drop_tables() -> None:
    """
    Удаление всех таблиц из базы данных
    
    ⚠️ ВНИМАНИЕ: Используйте только для тестирования!
    Все данные будут потеряны!
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    
    logger.warning("⚠️ УДАЛЕНИЕ ВСЕХ ТАБЛИЦ БАЗЫ ДАННЫХ...")
    
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.warning("Все таблицы удалены")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Асинхронный context manager для получения database session
    """
    if _async_session_factory is None:
        raise RuntimeError("Session factory not initialized. Call init_db() first.")
    
    session = _async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        await session.close()


async def close_db() -> None:
    """
    Закрытие подключения к базе данных
    """
    global _engine
    
    if _engine is not None:
        logger.info("Закрытие подключения к базе данных...")
        await _engine.dispose()
        _engine = None
        logger.info("Подключение к базе данных закрыто")


async def get_engine() -> AsyncEngine:
    """Получить engine базы данных"""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


async def check_db_connection() -> bool:
    """
    Проверка подключения к базе данных
    """
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        logger.info("✅ Подключение к базе данных активно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе данных: {e}")
        return False
