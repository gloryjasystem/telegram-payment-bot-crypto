"""
Функции валидации пользовательского ввода
"""
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple
import re

from utils.logger import bot_logger


def validate_amount(amount_str: str) -> Tuple[bool, Optional[Decimal], Optional[str]]:
    """
    Валидация суммы платежа
    
    Правила:
    - Должна быть положительным числом
    - Максимум 2 знака после запятой
    - Не более 999999.99
    
    Args:
        amount_str: Строка с суммой (например: "150" или "150.50")
    
    Returns:
        Tuple[bool, Optional[Decimal], Optional[str]]:
            - bool: True если валидация прошла успешно
            - Decimal: Сумма в формате Decimal (если валидация успешна)
            - str: Сообщение об ошибке (если валидация не прошла)
    
    Examples:
        >>> validate_amount("150")
        (True, Decimal('150'), None)
        
        >>> validate_amount("150.50")
        (True, Decimal('150.50'), None)
        
        >>> validate_amount("-10")
        (False, None, "Сумма должна быть положительным числом")
        
        >>> validate_amount("abc")
        (False, None, "Некорректный формат суммы. Используйте числа, например: 150 или 150.50")
    """
    # Удаляем пробелы
    amount_str = amount_str.strip()
    
    # Заменяем запятую на точку (на случай если пользователь ввел 150,50)
    amount_str = amount_str.replace(',', '.')
    
    try:
        amount = Decimal(amount_str)
    except (InvalidOperation, ValueError):
        return (
            False, 
            None, 
            "❌ Некорректный формат суммы. Используйте числа, например: 150 или 150.50"
        )
    
    # Проверка на положительное число
    if amount <= 0:
        return (
            False, 
            None, 
            "❌ Сумма должна быть положительным числом"
        )
    
    # Проверка на максимальную сумму
    if amount > Decimal('999999.99'):
        return (
            False, 
            None, 
            "❌ Сумма слишком большая. Максимум: $999,999.99"
        )
    
    # Проверка на количество знаков после запятой
    if amount.as_tuple().exponent < -2:
        return (
            False, 
            None, 
            "❌ Максимум 2 знака после запятой. Например: 150.50"
        )
    
    return (True, amount, None)


def validate_user_id(user_input: str) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Валидация User ID
    
    Принимает:
    - Числовой Telegram ID (например: 123456789)
    - Username с @ (например: @username)
    - Username без @ (например: username)
    
    Args:
        user_input: Строка с User ID или username
    
    Returns:
        Tuple[bool, Optional[int], Optional[str]]:
            - bool: True если это числовой ID
            - int: User ID (если это число)
            - str: Username (если это @username) или None
    
    Examples:
        >>> validate_user_id("123456789")
        (True, 123456789, None)
        
        >>> validate_user_id("@johndoe")
        (False, None, "johndoe")
        
        >>> validate_user_id("johndoe")
        (False, None, "johndoe")
    
    Note:
        Для @username функция вернет (False, None, "username")
        Caller должен самостоятельно найти user по username в БД
    """
    user_input = user_input.strip()
    
    # Проверка на пустой ввод
    if not user_input:
        return (False, None, None)
    
    # Случай 1: Числовой ID
    if user_input.isdigit():
        user_id = int(user_input)
        
        # Telegram ID должен быть положительным и разумным
        if user_id <= 0 or user_id > 9999999999:
            bot_logger.warning(f"Invalid Telegram ID range: {user_id}")
            return (False, None, None)
        
        return (True, user_id, None)
    
    # Случай 2: Username с @ или без
    if user_input.startswith('@'):
        username = user_input[1:]
    else:
        username = user_input
    
    # Валидация формата username
    # Telegram username: 5-32 символа, только буквы, цифры и подчеркивания
    if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
        bot_logger.warning(f"Invalid username format: {username}")
        return (False, None, None)
    
    return (False, None, username)


def validate_service_description(text: str) -> Tuple[bool, Optional[str]]:
    """
    Валидация описания услуги
    
    Правила:
    - Минимум 10 символов
    - Максимум 500 символов
    - Не должно быть только пробелов
    
    Args:
        text: Описание услуги
    
    Returns:
        Tuple[bool, Optional[str]]:
            - bool: True если валидация прошла успешно
            - str: Сообщение об ошибке (если валидация не прошла)
    
    Examples:
        >>> validate_service_description("Размещение рекламы на 7 дней")
        (True, None)
        
        >>> validate_service_description("Реклама")
        (False, "Описание слишком короткое. Минимум 10 символов")
        
        >>> validate_service_description("   ")
        (False, "Описание не может быть пустым")
    """
    # Удаляем пробелы с краев
    text = text.strip()
    
    # Проверка на пустоту
    if not text:
        return (False, "❌ Описание не может быть пустым")
    
    # Проверка на минимальную длину
    if len(text) < 10:
        return (
            False, 
            f"❌ Описание слишком короткое. Минимум 10 символов (сейчас: {len(text)})"
        )
    
    # Проверка на максимальную длину
    if len(text) > 500:
        return (
            False, 
            f"❌ Описание слишком длинное. Максимум 500 символов (сейчас: {len(text)})"
        )
    
    return (True, None)


def validate_invoice_id(invoice_id: str) -> bool:
    """
    Валидация формата Invoice ID
    
    Формат: INV-{timestamp}
    Например: INV-1707398400
    
    Args:
        invoice_id: ID инвойса
    
    Returns:
        bool: True если формат корректен
    
    Examples:
        >>> validate_invoice_id("INV-1707398400")
        True
        
        >>> validate_invoice_id("invoice-123")
        False
    """
    pattern = r'^INV-\d{10,}$'
    return bool(re.match(pattern, invoice_id))


def sanitize_text(text: str, max_length: int = 200) -> str:
    """
    Очистка текста от опасных символов и обрезка по длине
    
    Удаляет:
    - HTML теги
    - Специальные символы Telegram MarkdownV2 (оставляет безопасные)
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина (по умолчанию 200)
    
    Returns:
        str: Очищенный текст
    """
    # Удаляем HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    
    # Обрезаем по длине
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text.strip()


# Вспомогательные функции

def is_valid_telegram_id(telegram_id: int) -> bool:
    """
    Проверка валидности Telegram ID
    
    Args:
        telegram_id: Telegram ID пользователя
    
    Returns:
        bool: True если ID в допустимом диапазоне
    """
    return 0 < telegram_id <= 9999999999


def is_valid_status(status: str) -> bool:
    """
    Проверка валидности статуса инвойса
    
    Args:
        status: Статус инвойса
    
    Returns:
        bool: True если статус допустим
    """
    valid_statuses = {'pending', 'paid', 'expired', 'cancelled'}
    return status in valid_statuses
