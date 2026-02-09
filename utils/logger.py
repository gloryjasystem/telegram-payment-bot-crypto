"""
Конфигурация системы логирования
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import colorlog

from config import Config


def setup_logger(name: str = __name__) -> logging.Logger:
    """
    Создание и настройка logger с цветным выводом в консоль и записью в файл
    
    Args:
        name: Имя logger (обычно __name__ модуля)
    
    Returns:
        logging.Logger: Настроенный logger
    """
    logger = logging.getLogger(name)
    
    # Если logger уже настроен, возвращаем его
    if logger.handlers:
        return logger
    
    # Устанавливаем уровень логирования из конфига
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Формат для файлов
    file_formatter = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)-8s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Цветной формат для консоли
    console_formatter = colorlog.ColoredFormatter(
        fmt='%(log_color)s[%(asctime)s] %(levelname)-8s%(reset)s - %(name)s - %(message)s',
        datefmt='%H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    
    # Handler для консоли с цветным выводом
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Handler для файла с ротацией
    log_file = Path(Config.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        filename=Config.LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,  # Хранить последние 5 файлов
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Handler для ошибок (отдельный файл)
    error_log_file = log_file.parent / f"{log_file.stem}_errors{log_file.suffix}"
    error_handler = RotatingFileHandler(
        filename=str(error_log_file),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)
    
    # Предотвращаем дублирование логов
    logger.propagate = False
    
    return logger


# Создаем главный logger бота
bot_logger = setup_logger("bot")


def log_user_action(user_id: int, username: str | None, action: str) -> None:
    """
    Логирование действий пользователя
    
    Args:
        user_id: Telegram ID пользователя
        username: Username пользователя (может быть None)
        action: Описание действия
    """
    username_str = f"@{username}" if username else f"ID:{user_id}"
    bot_logger.info(f"👤 User {username_str} - {action}")


def log_admin_action(admin_id: int, action: str) -> None:
    """
    Логирование действий администратора
    
    Args:
        admin_id: Telegram ID администратора
        action: Описание действия
    """
    bot_logger.info(f"👑 Admin {admin_id} - {action}")


def log_payment(invoice_id: str, amount: float, status: str) -> None:
    """
    Логирование платежных операций
    
    Args:
        invoice_id: ID инвойса
        amount: Сумма платежа
        status: Статус платежа
    """
    bot_logger.info(f"💰 Payment {invoice_id} - ${amount} - Status: {status}")


def log_error(error: Exception, context: str = "") -> None:
    """
    Логирование ошибок с дополнительным контекстом
    
    Args:
        error: Исключение
        context: Дополнительный контекст ошибки
    """
    context_str = f" ({context})" if context else ""
    bot_logger.error(f"❌ Error{context_str}: {type(error).__name__}: {str(error)}", exc_info=True)


# Примеры использования:
# from utils.logger import bot_logger, log_user_action
# 
# bot_logger.info("Bot started")
# log_user_action(123456, "john_doe", "sent /start command")
