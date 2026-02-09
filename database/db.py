"""
Управление подключениями к базе данных
"""
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)
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
    
    logger.info(f"Инициализация базы данных: {Config.DATABASE_URL}")
    
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
    
    logger.info("База данных инициализирована успешно")


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
    
    logger.info("Таблицы базы данных созданы успешно")


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
    
    Использование:
        async with get_session() as session:
            # Выполнение операций с БД
            user = await session.get(User, user_id)
            await session.commit()
    
    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy
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
    
    Вызывайте при завершении работы бота для корректного закрытия соединений
    """
    global _engine
    
    if _engine is not None:
        logger.info("Закрытие подключения к базе данных...")
        await _engine.dispose()
        _engine = None
        logger.info("Подключение к базе данных закрыто")


# Вспомогательные функции для удобства

async def get_engine() -> AsyncEngine:
    """Получить engine базы данных"""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


async def check_db_connection() -> bool:
    """
    Проверка подключения к базе данных
    
    Returns:
        bool: True если подключение успешно, False в противном случае
    """
    try:
        async with get_session() as session:
            # Простой запрос для проверки соединения
            await session.execute("SELECT 1")
        logger.info("✅ Подключение к базе данных активно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе данных: {e}")
        return False
