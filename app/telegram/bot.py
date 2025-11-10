"""
Telegram Bot for User Self-Service

This module provides a Telegram bot interface for users to:
- Link their Telegram account to their proxy account
- View account status (traffic, expiry, limits)
- Get subscription links and QR codes
- Receive notifications

Admin features:
- Add/remove users
- View statistics
- Manage users via bot
"""

import logging
import io
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.orm import Session

from app.db import GetDB, get_db
from app.db.models import User
from app.config.env import TELEGRAM_API_TOKEN, TELEGRAM_ADMIN_ID
from app.utils.share import generate_subscription
from app.db import crud

logger = logging.getLogger(__name__)


# Rate limiting implementation
_rate_limit_storage = defaultdict(lambda: {"count": 0, "reset_time": datetime.now()})
RATE_LIMIT_MESSAGES = 5  # messages per window
RATE_LIMIT_WINDOW = 60  # seconds


def rate_limit(func):
    """
    Rate limiting decorator for bot commands.
    Limits to RATE_LIMIT_MESSAGES per RATE_LIMIT_WINDOW seconds per user.
    """
    async def wrapper(message: Message, *args, **kwargs):
        user_id = message.from_user.id
        now = datetime.now()

        # Get user's rate limit data
        user_limit = _rate_limit_storage[user_id]

        # Reset counter if window has passed
        if now > user_limit["reset_time"]:
            user_limit["count"] = 0
            user_limit["reset_time"] = now + timedelta(seconds=RATE_LIMIT_WINDOW)

        # Check if user has exceeded limit
        if user_limit["count"] >= RATE_LIMIT_MESSAGES:
            wait_seconds = int((user_limit["reset_time"] - now).total_seconds())
            await message.answer(
                f"⏳ <b>Rate limit exceeded!</b>\n\n"
                f"Please wait {wait_seconds} seconds before trying again.\n"
                f"This prevents spam and keeps the bot responsive for everyone.",
                parse_mode="HTML"
            )
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return

        # Increment counter and execute command
        user_limit["count"] += 1
        return await func(message, *args, **kwargs)

    return wrapper


class LinkAccountState(StatesGroup):
    """States for linking Telegram account to user"""
    waiting_for_username = State()


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human-readable format"""
    if bytes_value is None:
        return "Unlimited"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime to readable string"""
    if dt is None:
        return "Never"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
    """Get user by Telegram ID"""
    return db.query(User).filter(User.telegram_id == telegram_id).first()


def create_main_keyboard() -> InlineKeyboardMarkup:
    """Create main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Status", callback_data="status"),
            InlineKeyboardButton(text="🔗 Config", callback_data="config"),
        ],
        [
            InlineKeyboardButton(text="📱 QR Code", callback_data="qr"),
            InlineKeyboardButton(text="ℹ️ Help", callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_config_format_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for config format selection"""
    keyboard = [
        [
            InlineKeyboardButton(text="V2Ray", callback_data="config_v2ray"),
            InlineKeyboardButton(text="Clash", callback_data="config_clash"),
        ],
        [
            InlineKeyboardButton(text="Clash Meta", callback_data="config_clash_meta"),
            InlineKeyboardButton(text="Sing-Box", callback_data="config_singbox"),
        ],
        [InlineKeyboardButton(text="« Back", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command"""
    telegram_id = message.from_user.id

    with GetDB() as db:
        user = get_user_by_telegram_id(db, telegram_id)

    if user:
        await message.answer(
            f"👋 Welcome back, <b>{user.username}</b>!\n\n"
            f"Your account is linked. Use the menu below to manage your account.",
            reply_markup=create_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "👋 Welcome to Marzneshin Bot!\n\n"
            "To use this bot, you need to link your Telegram account to your proxy account.\n\n"
            "Use /link command with your username:\n"
            "<code>/link your_username</code>",
            parse_mode="HTML"
        )


@rate_limit
async def cmd_link(message: Message, state: FSMContext):
    """Handle /link command to link Telegram account"""
    telegram_id = message.from_user.id

    # Extract username and subscription key from command
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "❌ <b>Usage:</b>\n"
            "<code>/link username subscription_key</code>\n\n"
            "📝 You can find your subscription key in your subscription URL:\n"
            "<code>https://panel.com/sub/<b>YOUR_KEY</b>/...</code>\n\n"
            "Example:\n"
            "<code>/link john abc123def456</code>",
            parse_mode="HTML"
        )
        return

    username = args[1].strip()
    subscription_key = args[2].strip()

    with GetDB() as db:
        # Check if already linked
        existing_user = get_user_by_telegram_id(db, telegram_id)
        if existing_user:
            await message.answer(
                f"⚠️ Your Telegram account is already linked to: <b>{existing_user.username}</b>\n\n"
                f"To relink, please contact an administrator.",
                parse_mode="HTML"
            )
            return

        # Authenticate: verify username AND subscription key
        user = crud.get_user(db, username)
        if not user or user.key != subscription_key:
            await message.answer(
                "❌ <b>Invalid credentials</b>\n\n"
                "Please check your username and subscription key.\n"
                "Make sure you're using the correct key from your subscription URL.",
                parse_mode="HTML"
            )
            logger.warning(f"Failed Telegram link attempt for username '{username}' from telegram_id {telegram_id}")
            return

        # Check if user already has a telegram_id
        if user.telegram_id:
            await message.answer(
                f"❌ This account is already linked to another Telegram account.\n\n"
                f"Please contact an administrator to unlink first.",
                parse_mode="HTML"
            )
            return

        # Link the account
        try:
            user.telegram_id = telegram_id
            db.commit()

            await message.answer(
                f"✅ <b>Successfully linked!</b>\n\n"
                f"Account: <b>{username}</b>\n\n"
                f"Use the menu below to manage your account.",
                reply_markup=create_main_keyboard(),
                parse_mode="HTML"
            )
            logger.info(f"Telegram account {telegram_id} successfully linked to user {username}")

        except Exception as e:
            db.rollback()
            await message.answer(
                "❌ An error occurred while linking your account.\n"
                "Please try again later or contact an administrator."
            )
            logger.error(f"Error linking Telegram account: {e}")


async def cmd_unlink(message: Message):
    """Handle /unlink command"""
    telegram_id = message.from_user.id

    with GetDB() as db:
        user = get_user_by_telegram_id(db, telegram_id)
        if not user:
            await message.answer("❌ Your Telegram account is not linked to any user.")
            return

        username = user.username
        user.telegram_id = None
        db.commit()

        await message.answer(
            f"✅ Successfully unlinked from <b>{username}</b>!",
            parse_mode="HTML"
        )
        logger.info(f"Telegram account {telegram_id} unlinked from user {username}")


@rate_limit
async def cmd_status(message: Message):
    """Handle /status command"""
    telegram_id = message.from_user.id

    with GetDB() as db:
        user = get_user_by_telegram_id(db, telegram_id)
        if not user:
            await message.answer(
                "❌ Your Telegram account is not linked.\n\n"
                "Use /link to link your account."
            )
            return

        # Calculate remaining data (safe division)
        if user.data_limit and user.data_limit > 0:
            used_percentage = (user.used_traffic / user.data_limit) * 100
            remaining = max(0, user.data_limit - user.used_traffic)
        else:
            used_percentage = 0
            remaining = None

        # Build status message
        status_text = f"📊 <b>Account Status</b>\n\n"
        status_text += f"👤 Username: <b>{user.username}</b>\n"
        status_text += f"🔑 Status: {'✅ Active' if user.is_active else '❌ Inactive'}\n"
        status_text += f"📅 Created: {format_datetime(user.created_at)}\n\n"

        status_text += f"📈 <b>Traffic Usage</b>\n"
        status_text += f"📤 Used: {format_bytes(user.used_traffic)}\n"

        if user.data_limit and user.data_limit > 0:
            status_text += f"📊 Limit: {format_bytes(user.data_limit)}\n"
            status_text += f"📉 Remaining: {format_bytes(remaining)}\n"
            status_text += f"📈 Usage: {used_percentage:.1f}%\n"
        else:
            status_text += f"📊 Limit: ♾️ Unlimited\n"

        status_text += f"\n"

        status_text += f"⏰ <b>Expiry</b>\n"
        status_text += f"📅 Expire Date: {format_datetime(user.expire_date)}\n"
        status_text += f"⏳ Status: {'❌ Expired' if user.expired else '✅ Active'}\n"

        await message.answer(status_text, parse_mode="HTML", reply_markup=create_main_keyboard())


@rate_limit
async def cmd_config(message: Message):
    """Handle /config command"""
    telegram_id = message.from_user.id

    with GetDB() as db:
        user = get_user_by_telegram_id(db, telegram_id)
        if not user:
            await message.answer(
                "❌ Your Telegram account is not linked.\n\n"
                "Use /link to link your account."
            )
            return

    await message.answer(
        "📱 <b>Select Config Format</b>\n\n"
        "Choose the format for your subscription link:",
        reply_markup=create_config_format_keyboard(),
        parse_mode="HTML"
    )


async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = (
        "🤖 <b>Marzneshin Bot Help</b>\n\n"
        "<b>User Commands:</b>\n"
        "/start - Start the bot\n"
        "/link [username] [subscription_key] - Link your Telegram account\n"
        "/unlink - Unlink your account\n"
        "/status - View your account status\n"
        "/config - Get your subscription link\n"
        "/qr - Get QR code\n"
        "/help - Show this help message\n\n"
        "<b>Admin Commands:</b>\n"
        "/stats - View system statistics\n"
        "/broadcast - Send message to all users\n\n"
        "💡 <b>Tip:</b> Use the inline buttons for easier navigation!"
    )

    await message.answer(help_text, parse_mode="HTML")


# Admin commands
async def cmd_stats(message: Message):
    """Handle /stats command (admin only)"""
    telegram_id = message.from_user.id

    # Check if user is admin
    if not TELEGRAM_ADMIN_ID or telegram_id not in TELEGRAM_ADMIN_ID:
        await message.answer("❌ This command is only available to administrators.")
        return

    with GetDB() as db:
        total_users = db.query(User).filter(User.removed == False).count()
        active_users = db.query(User).filter(
            User.removed == False,
            User.enabled == True,
            User.activated == True
        ).count()

        stats_text = (
            f"📊 <b>System Statistics</b>\n\n"
            f"👥 Total Users: {total_users}\n"
            f"✅ Active Users: {active_users}\n"
            f"❌ Inactive Users: {total_users - active_users}\n"
        )

        await message.answer(stats_text, parse_mode="HTML")


async def cmd_broadcast(message: Message):
    """Handle /broadcast command (admin only)"""
    telegram_id = message.from_user.id

    # Check if user is admin
    if not TELEGRAM_ADMIN_ID or telegram_id not in TELEGRAM_ADMIN_ID:
        await message.answer("❌ This command is only available to administrators.")
        return

    # Get message text after command
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Please provide a message to broadcast:\n"
            "<code>/broadcast Your message here</code>",
            parse_mode="HTML"
        )
        return

    broadcast_text = args[1]

    with GetDB() as db:
        users_with_telegram = db.query(User).filter(
            User.telegram_id.isnot(None),
            User.removed == False
        ).all()

        sent_count = 0
        failed_count = 0

        for user in users_with_telegram:
            try:
                await message.bot.send_message(
                    user.telegram_id,
                    f"📢 <b>Broadcast Message</b>\n\n{broadcast_text}",
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user.username}: {e}")
                failed_count += 1

        await message.answer(
            f"✅ Broadcast sent!\n\n"
            f"📤 Sent: {sent_count}\n"
            f"❌ Failed: {failed_count}",
            parse_mode="HTML"
        )


def setup_handlers(dp: Dispatcher):
    """Setup all bot handlers"""
    # User commands
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_link, Command("link"))
    dp.message.register(cmd_unlink, Command("unlink"))
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(cmd_config, Command("config"))
    dp.message.register(cmd_help, Command("help"))

    # Admin commands
    dp.message.register(cmd_stats, Command("stats"))
    dp.message.register(cmd_broadcast, Command("broadcast"))

    logger.info("Telegram bot handlers registered")


async def start_bot():
    """Start the Telegram bot"""
    if not TELEGRAM_API_TOKEN:
        logger.warning("Telegram bot token not configured, bot will not start")
        return None

    try:
        bot = Bot(token=TELEGRAM_API_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())

        setup_handlers(dp)

        # Start polling
        await dp.start_polling(bot)

        logger.info("Telegram bot started successfully")
        return dp

    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")
        return None
