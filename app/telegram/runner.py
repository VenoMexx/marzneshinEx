"""
Telegram Bot Runner

This module runs the Telegram bot as a background task in the main application.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config.env import TELEGRAM_API_TOKEN
from app.telegram.bot import setup_handlers
from app.telegram.callbacks import setup_callback_handlers

logger = logging.getLogger(__name__)

# Global bot and dispatcher instances
bot: Bot | None = None
dispatcher: Dispatcher | None = None


async def start_telegram_bot():
    """
    Start the Telegram bot in the background.

    This function initializes the bot and dispatcher, registers all handlers,
    and starts polling for updates.
    """
    global bot, dispatcher

    if not TELEGRAM_API_TOKEN:
        logger.warning("Telegram bot token not configured, bot will not start")
        return

    try:
        logger.info("Starting Telegram bot...")

        # Create bot instance
        bot = Bot(token=TELEGRAM_API_TOKEN)

        # Create dispatcher with memory storage
        dispatcher = Dispatcher(storage=MemoryStorage())

        # Setup handlers
        setup_handlers(dispatcher)
        setup_callback_handlers(dispatcher)

        logger.info("Telegram bot handlers registered")

        # Start polling
        await dispatcher.start_polling(bot, skip_updates=True)

    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}", exc_info=True)
    finally:
        if bot:
            await bot.session.close()


async def stop_telegram_bot():
    """Stop the Telegram bot gracefully"""
    global bot, dispatcher

    if dispatcher:
        await dispatcher.stop_polling()
        logger.info("Telegram bot stopped")

    if bot:
        await bot.session.close()


def run_bot_in_background():
    """
    Run the Telegram bot as a background task.

    This function can be called from the main application to start the bot.
    """
    asyncio.create_task(start_telegram_bot())
    logger.info("Telegram bot task created")
