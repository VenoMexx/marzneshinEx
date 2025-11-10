"""
Telegram Bot Module

Provides Telegram bot functionality for user self-service and admin management.
"""

from app.telegram.bot import setup_handlers, start_bot
from app.telegram.callbacks import setup_callback_handlers

__all__ = ["setup_handlers", "setup_callback_handlers", "start_bot"]
