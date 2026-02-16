"""
Вспомогательные функции
"""
from datetime import datetime
from decimal import Decimal
import time
import re


def generate_invoice_id() -> str:
    """
    Генерация уникального ID инвойса
    
    Формат: INV-YYMMDD-XXXX
    Например: INV-260216-A7B3
    
    Returns:
        str: Уникальный ID инвойса
    
    Examples:
        >>> invoice_id = generate_invoice_id()
        >>> invoice_id.startswith('INV-')
        True
        >>> len(invoice_id) == 16
        True
    """
    import random
    import string
    date_part = datetime.now().strftime("%y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"INV-{date_part}-{random_part}"


def format_currency(amount: Decimal | float, currency: str = "USD") -> str:
    """
    Форматирование суммы в красивый вид
    
    Args:
        amount: Сумма
        currency: Валюта (по умолчанию USD)
    
    Returns:
        str: Отформатированная строка
    
    Examples:
        >>> format_currency(150)
        '$150.00'
        
        >>> format_currency(150.5)
        '$150.50'
        
        >>> format_currency(1500.99)
        '$1,500.99'
        
        >>> format_currency(150, "EUR")
        '€150.00'
    """
    # Конвертация в Decimal для точности
    if isinstance(amount, float):
        amount = Decimal(str(amount))
    
    # Символы валют
    currency_symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "RUB": "₽",
    }
    
    symbol = currency_symbols.get(currency, currency)
    
    # Форматирование с разделителями тысяч
    amount_str = f"{amount:,.2f}"
    
    return f"{symbol}{amount_str}"


def format_datetime(dt: datetime, format_type: str = "full") -> str:
    """
    Форматирование datetime в читаемый вид
    
    Args:
        dt: Datetime объект
        format_type: Тип форматирования ("full", "date", "time", "short")
    
    Returns:
        str: Отформатированная дата/время
    
    Examples:
        >>> dt = datetime(2024, 2, 8, 13, 30, 45)
        >>> format_datetime(dt, "full")
        '08.02.2024 13:30:45'
        
        >>> format_datetime(dt, "date")
        '08.02.2024'
        
        >>> format_datetime(dt, "time")
        '13:30'
        
        >>> format_datetime(dt, "short")
        '08.02.24 13:30'
    """
    formats = {
        "full": "%d.%m.%Y %H:%M:%S",
        "date": "%d.%m.%Y",
        "time": "%H:%M",
        "short": "%d.%m.%y %H:%M",
    }
    
    format_str = formats.get(format_type, formats["full"])
    return dt.strftime(format_str)


def escape_markdown(text: str) -> str:
    """
    Экранирование специальных символов для Telegram MarkdownV2
    
    Args:
        text: Исходный текст
    
    Returns:
        str: Текст с экранированными символами
    
    Note:
        В MarkdownV2 нужно экранировать: _ * [ ] ( ) ~ ` > # + - = | { } . !
    
    Examples:
        >>> escape_markdown("Hello_world")
        'Hello\\_world'
        
        >>> escape_markdown("Price: $150.00")
        'Price: $150\\.00'
    """
    # Символы для экранирования в MarkdownV2
    special_chars = r'_*[]()~`>#+-=|{}.!'
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Обрезка текста до указанной длины с добавлением суффикса
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        suffix: Суффикс для добавления (по умолчанию "...")
    
    Returns:
        str: Обрезанный текст
    
    Examples:
        >>> truncate_text("Very long text that needs to be cut", 20)
        'Very long text th...'
        
        >>> truncate_text("Short text", 20)
        'Short text'
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def get_time_until_expiry(created_at: datetime, expiry_hours: int = 1) -> str:
    """
    Получить человекочитаемое время до истечения срока
    
    Args:
        created_at: Время создания
        expiry_hours: Часов до истечения (по умолчанию 1)
    
    Returns:
        str: Время до истечения в формате "XX минут" или "Истек"
    
    Examples:
        >>> from datetime import datetime, timedelta
        >>> created = datetime.now() - timedelta(minutes=30)
        >>> result = get_time_until_expiry(created, 1)
        >>> "30" in result or "минут" in result
        True
    """
    now = datetime.utcnow()
    expiry_time = created_at.replace(tzinfo=None) + timedelta(hours=expiry_hours)
    
    if now >= expiry_time:
        return "Истек"
    
    time_left = expiry_time - now
    
    # Конвертация в минуты
    minutes_left = int(time_left.total_seconds() / 60)
    
    if minutes_left < 60:
        return f"{minutes_left} минут"
    else:
        hours_left = minutes_left // 60
        return f"{hours_left} час(а)"


def parse_command_args(text: str) -> list[str]:
    """
    Парсинг аргументов команды
    
    Разделяет текст на части, учитывая кавычки
    
    Args:
        text: Текст команды (например: '/invoice @user 150 "Размещение рекламы на 7 дней"')
    
    Returns:
        list[str]: Список аргументов
    
    Examples:
        >>> parse_command_args('/invoice @user 150 "Реклама на 7 дней"')
        ['@user', '150', 'Реклама на 7 дней']
        
        >>> parse_command_args('/invoice 123456 100 Simple description')
        ['123456', '100', 'Simple', 'description']
    """
    # Удаляем команду (первое слово)
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return []
    
    args_text = parts[1]
    
    # Парсинг с учетом кавычек
    pattern = r'[^\s"]+|"([^"]*)"'
    matches = re.findall(pattern, args_text)
    
    # Очистка результатов
    args = []
    for match in matches:
        # match это tuple (group0, group1)
        # Если есть group1 (текст в кавычках), используем его
        # Иначе используем group0 (текст без кавычек)
        arg = match[1] if isinstance(match, tuple) and match[1] else match[0] if isinstance(match, tuple) else match
        if arg:
            args.append(arg)
    
    return args


def format_user_mention(user_id: int, username: str | None, first_name: str) -> str:
    """
    Форматирование упоминания пользователя
    
    Args:
        user_id: Telegram ID
        username: Username (может быть None)
        first_name: Имя пользователя
    
    Returns:
        str: Форматированное упоминание
    
    Examples:
        >>> format_user_mention(123, "johndoe", "John")
        '@johndoe (ID: 123)'
        
        >>> format_user_mention(456, None, "Jane")
        'Jane (ID: 456)'
    """
    if username:
        return f"@{username} (ID: {user_id})"
    else:
        return f"{first_name} (ID: {user_id})"


def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """
    Создание ASCII прогресс-бара
    
    Args:
        current: Текущее значение
        total: Максимальное значение
        length: Длина прогресс-бара (по умолчанию 10)
    
    Returns:
        str: Прогресс-бар
    
    Examples:
        >>> create_progress_bar(5, 10, 10)
        '█████░░░░░ 50%'
        
        >>> create_progress_bar(75, 100, 10)
        '███████░░░ 75%'
    """
    if total == 0:
        percentage = 0
    else:
        percentage = int((current / total) * 100)
    
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '░' * (length - filled_length)
    
    return f"{bar} {percentage}%"


# Импорты для типов
from datetime import timedelta
