"""
Handlers package
Содержит обработчики команд и callback'ов
"""

from .user_handlers import user_router
from .admin_handlers import admin_router
from .callback_handlers import callback_router

__all__ = [
    "user_router",
    "admin_router",
    "callback_router"
]
