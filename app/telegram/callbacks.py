"""
Telegram Bot Callback Handlers

This module handles all inline button callbacks for the Telegram bot.
"""

import logging
import io
import base64
from typing import Optional

from aiogram import Bot
from aiogram.types import CallbackQuery, BufferedInputFile
from sqlalchemy.orm import Session
import qrcode

from app.db import GetDB
from app.db.models import User
from app.utils.share import generate_subscription
from app.telegram.bot import (
    get_user_by_telegram_id,
    format_bytes,
    format_datetime,
    create_main_keyboard,
    create_config_format_keyboard,
)

logger = logging.getLogger(__name__)


def generate_qr_code(data: str) -> bytes:
    """Generate QR code image from data"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    return img_bytes.read()


async def callback_status(callback: CallbackQuery):
    """Handle status button callback"""
    telegram_id = callback.from_user.id

    with GetDB() as db:
        user = get_user_by_telegram_id(db, telegram_id)
        if not user:
            await callback.answer("❌ Your account is not linked", show_alert=True)
            return

        # Calculate remaining data
        if user.data_limit:
            used_percentage = (user.used_traffic / user.data_limit) * 100
            remaining = user.data_limit - user.used_traffic
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
        status_text += f"📊 Limit: {format_bytes(user.data_limit)}\n"
        if user.data_limit:
            status_text += f"📉 Remaining: {format_bytes(remaining)}\n"
            status_text += f"📈 Usage: {used_percentage:.1f}%\n"
        status_text += f"\n"

        status_text += f"⏰ <b>Expiry</b>\n"
        status_text += f"📅 Expire Date: {format_datetime(user.expire_date)}\n"
        status_text += f"⏳ Status: {'❌ Expired' if user.expired else '✅ Active'}\n"

        await callback.message.edit_text(
            status_text,
            parse_mode="HTML",
            reply_markup=create_main_keyboard()
        )
        await callback.answer()


async def callback_config(callback: CallbackQuery):
    """Handle config button callback"""
    telegram_id = callback.from_user.id

    with GetDB() as db:
        user = get_user_by_telegram_id(db, telegram_id)
        if not user:
            await callback.answer("❌ Your account is not linked", show_alert=True)
            return

    await callback.message.edit_text(
        "📱 <b>Select Config Format</b>\n\n"
        "Choose the format for your subscription link:",
        reply_markup=create_config_format_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


async def callback_config_format(callback: CallbackQuery, format_type: str):
    """Handle config format selection callback"""
    telegram_id = callback.from_user.id

    format_map = {
        "config_v2ray": ("links", "V2Ray"),
        "config_clash": ("clash", "Clash"),
        "config_clash_meta": ("clash-meta", "Clash Meta"),
        "config_singbox": ("sing-box", "Sing-Box"),
    }

    config_format, format_name = format_map.get(format_type, ("links", "V2Ray"))

    with GetDB() as db:
        user = get_user_by_telegram_id(db, telegram_id)
        if not user:
            await callback.answer("❌ Your account is not linked", show_alert=True)
            return

        try:
            # Generate subscription link (base URL should be configured)
            from app.config import DOCS_URL
            base_url = DOCS_URL.rstrip('/')

            # Generate subscription URL
            sub_url = f"{base_url}/sub/{user.key}/{config_format}"

            config_text = (
                f"🔗 <b>{format_name} Subscription Link</b>\n\n"
                f"<code>{sub_url}</code>\n\n"
                f"📋 Copy this link and paste it into your {format_name} client.\n\n"
                f"💡 <b>Tip:</b> This link auto-updates when your config changes."
            )

            await callback.message.edit_text(
                config_text,
                parse_mode="HTML",
                reply_markup=create_main_keyboard()
            )
            await callback.answer("✅ Subscription link generated!")

        except Exception as e:
            logger.error(f"Failed to generate config: {e}")
            await callback.answer("❌ Failed to generate config", show_alert=True)


async def callback_qr(callback: CallbackQuery):
    """Handle QR code button callback"""
    telegram_id = callback.from_user.id

    with GetDB() as db:
        user = get_user_by_telegram_id(db, telegram_id)
        if not user:
            await callback.answer("❌ Your account is not linked", show_alert=True)
            return

        try:
            # Generate subscription link
            from app.config import DOCS_URL
            base_url = DOCS_URL.rstrip('/')
            sub_url = f"{base_url}/sub/{user.key}"

            # Generate QR code
            qr_bytes = generate_qr_code(sub_url)

            # Send QR code as photo
            photo = BufferedInputFile(qr_bytes, filename=f"qr_{user.username}.png")
            await callback.message.answer_photo(
                photo=photo,
                caption=f"📱 <b>QR Code for {user.username}</b>\n\n"
                        f"Scan this QR code with your proxy client.",
                parse_mode="HTML"
            )

            await callback.answer("✅ QR code generated!")

        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")
            await callback.answer("❌ Failed to generate QR code", show_alert=True)


async def callback_help(callback: CallbackQuery):
    """Handle help button callback"""
    help_text = (
        "🤖 <b>Marzneshin Bot Help</b>\n\n"
        "<b>User Commands:</b>\n"
        "/start - Start the bot\n"
        "/link [username] - Link your Telegram account\n"
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

    await callback.message.edit_text(
        help_text,
        parse_mode="HTML",
        reply_markup=create_main_keyboard()
    )
    await callback.answer()


async def callback_main_menu(callback: CallbackQuery):
    """Handle main menu button callback"""
    telegram_id = callback.from_user.id

    with GetDB() as db:
        user = get_user_by_telegram_id(db, telegram_id)
        if not user:
            await callback.answer("❌ Your account is not linked", show_alert=True)
            return

        await callback.message.edit_text(
            f"👋 Welcome, <b>{user.username}</b>!\n\n"
            f"Use the menu below to manage your account.",
            reply_markup=create_main_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()


def setup_callback_handlers(dp):
    """Setup all callback handlers"""
    from aiogram import F

    dp.callback_query.register(callback_status, F.data == "status")
    dp.callback_query.register(callback_config, F.data == "config")
    dp.callback_query.register(callback_qr, F.data == "qr")
    dp.callback_query.register(callback_help, F.data == "help")
    dp.callback_query.register(callback_main_menu, F.data == "main_menu")

    # Config format callbacks
    dp.callback_query.register(
        lambda c: callback_config_format(c, "config_v2ray"),
        F.data == "config_v2ray"
    )
    dp.callback_query.register(
        lambda c: callback_config_format(c, "config_clash"),
        F.data == "config_clash"
    )
    dp.callback_query.register(
        lambda c: callback_config_format(c, "config_clash_meta"),
        F.data == "config_clash_meta"
    )
    dp.callback_query.register(
        lambda c: callback_config_format(c, "config_singbox"),
        F.data == "config_singbox"
    )

    logger.info("Telegram bot callback handlers registered")
