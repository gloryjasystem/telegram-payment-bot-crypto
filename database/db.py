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
    Проверка и миграция таблицы users (добавление новых колонок)
    """
    if _engine is None:
        return
        
    try:
        # Пытаемся проверить только для PostgreSQL
        if "postgresql" not in Config.DATABASE_URL.lower():
            return

        async with _engine.begin() as conn:
            # Проверяем наличие колонки is_admin
            try:
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='users' AND column_name='is_admin';"
                ))
                column_exists = result.scalar() is not None
                
                if not column_exists:
                    logger.warning("⚠️ Обнаружена устаревшая схема БД. Выполняю миграцию...")
                    
                    # Добавляем колонки
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;"))
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;"))
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMP WITHOUT TIME ZONE;"))
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_by BIGINT;"))
                    
                    # Создаем индекс
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_blocked ON users (is_blocked);"))
                    
                    logger.info("✅ Миграция базы данных выполнена успешно")
                else:
                    logger.info("✅ Структура базы данных актуальна")
                
                # Миграция: bot_message_id для инвойсов
                await conn.execute(text(
                    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS bot_message_id BIGINT;"
                ))
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
