# helper/stats.py

import time
import html
from datetime import datetime, timedelta, timezone

from pyrogram import filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.database import (
    users_col,
    credits_col,
    premium_col,
    referrals_col,
    ads_col,
    fsub_collection,
    stats_col
)

from config import ADMIN_IDS, TIMEZONE_OFFSET


# ==================== ADMIN CHECK ====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ==================== HELPERS ====================

def escape_html(text):
    if not text:
        return "Unknown"

    return html.escape(str(text))


def format_number(num):
    """Format number with commas"""
    return f"{num:,}"


def get_ist_date_str():
    """Get today's date in IST (YYYY-MM-DD)"""

    ist_tz = timezone(
        timedelta(seconds=TIMEZONE_OFFSET)
    )

    return datetime.now(
        tz=ist_tz
    ).strftime("%Y-%m-%d")


# ==================== STATS FETCHERS ====================

def get_platform_stats():
    """Get platform-wise download stats"""

    stats = stats_col.find_one(
        {"_id": "platform_stats"}
    )

    if stats:
        return stats.get("data", {})

    return {
        "youtube": 0,
        "instagram": 0,
        "facebook": 0,
        "tiktok": 0,
        "pinterest": 0,
        "twitter": 0,
        "terabox": 0
    }


def get_api_stats():
    """Get API usage stats"""

    stats = stats_col.find_one(
        {"_id": "api_stats"}
    )

    if stats:
        return stats.get("data", {})

    return {
        "fastsaver": 0,
        "yoinku": 0,
        "Terabox": 0,
        "instagram_api": 0,
        "getvidfb": 0
    }


def get_all_stats():
    """Fetch all stats from database"""

    stats = {}

    # ========== USER STATS ==========

    stats["total_users"] = (
        users_col.count_documents({})
    )

    stats["total_credits_users"] = (
        credits_col.count_documents({})
    )

    # Total credits (aggregation)

    result = list(
        credits_col.aggregate(
            [
                {
                    "$group": {
                        "_id": None,
                        "total": {
                            "$sum": "$balance"
                        }
                    }
                }
            ]
        )
    )

    stats["total_credits"] = (
        result[0]["total"]
        if result
        else 0
    )

    stats["avg_credits"] = (
        int(
            stats["total_credits"]
            / stats["total_credits_users"]
        )
        if stats["total_credits_users"] > 0
        else 0
    )

    # ========== PREMIUM STATS ==========

    stats["total_premium"] = (
        premium_col.count_documents({})
    )

    now = time.time()

    stats["active_premium"] = (
        premium_col.count_documents(
            {
                "expiry": {
                    "$gt": now
                }
            }
        )
    )

    stats["expired_premium"] = (
        stats["total_premium"]
        - stats["active_premium"]
    )

    # ========== REFERRAL STATS ==========

    stats["total_referrals"] = (
        referrals_col.count_documents({})
    )

    # ========== ADS STATS ==========

    stats["total_ads_completed"] = (
        ads_col.count_documents(
            {"status": "completed"}
        )
    )

    stats["total_ads_bypassed"] = (
        ads_col.count_documents(
            {"status": "bypassed"}
        )
    )

    today = get_ist_date_str()

    stats["today_ads"] = (
        ads_col.count_documents(
            {
                "date": today,
                "status": "completed"
            }
        )
    )

    # ========== FSUB STATS ==========

    stats["total_fsub_channels"] = (
        fsub_collection.count_documents({})
    )

    # ========== PLATFORM + API STATS ==========

    stats["platform_stats"] = (
        get_platform_stats()
    )

    stats["api_stats"] = (
        get_api_stats()
    )

    return stats


# ==================== STATS TEXT BUILDER ====================

def build_stats_text(stats):
    """Build stats message text from stats dict"""

    stats_text = (
        f"📊 <b>Bᴏᴛ Sᴛᴀᴛɪsᴛɪᴄs</b>\n\n"

        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>👥 Usᴇʀ Sᴛᴀᴛs</b>\n"
        f"├ Tᴏᴛᴀʟ Usᴇʀs: "
        f"<b>{format_number(stats['total_users'])}</b>\n"
        f"├ Usᴇʀs ᴡɪᴛʜ Cʀᴇᴅɪᴛs: "
        f"<b>{format_number(stats['total_credits_users'])}</b>\n"
        f"├ Tᴏᴛᴀʟ Cʀᴇᴅɪᴛs: "
        f"<b>{format_number(stats['total_credits'])}</b>\n"
        f"└ Aᴠɢ Cʀᴇᴅɪᴛs: "
        f"<b>{format_number(stats['avg_credits'])}</b>\n\n"

        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>👑 Pʀᴇᴍɪᴜᴍ Sᴛᴀᴛs</b>\n"
        f"├ Tᴏᴛᴀʟ Pʀᴇᴍɪᴜᴍ: "
        f"<b>{format_number(stats['total_premium'])}</b>\n"
        f"├ Aᴄᴛɪᴠᴇ: "
        f"<b>{format_number(stats['active_premium'])}</b>\n"
        f"└ Exᴘɪʀᴇᴅ: "
        f"<b>{format_number(stats['expired_premium'])}</b>\n\n"

        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>👥 Rᴇғᴇʀʀᴀʟ Sᴛᴀᴛs</b>\n"
        f"└ Tᴏᴛᴀʟ Rᴇғᴇʀʀᴀʟs: "
        f"<b>{format_number(stats['total_referrals'])}</b>\n\n"

        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>📺 Aᴅs Sᴛᴀᴛs</b>\n"
        f"├ Tᴏᴛᴀʟ Cᴏᴍᴘʟᴇᴛᴇᴅ: "
        f"<b>{format_number(stats['total_ads_completed'])}</b>\n"
        f"├ Tᴏᴛᴀʟ Bʏᴘᴀssᴇᴅ: "
        f"<b>{format_number(stats['total_ads_bypassed'])}</b>\n"
        f"└ Tᴏᴅᴀʏ's Aᴅs: "
        f"<b>{format_number(stats['today_ads'])}</b>\n\n"

        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>📢 FSUB Sᴛᴀᴛs</b>\n"
        f"└ Tᴏᴛᴀʟ Cʜᴀɴɴᴇʟs: "
        f"<b>{format_number(stats['total_fsub_channels'])}</b>\n\n"
    )

    # Platform stats

    platform_stats = stats.get(
        "platform_stats",
        {}
    )

    if any(platform_stats.values()):

        stats_text += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>🎬 Pʟᴀᴛғᴏʀᴍ Dᴏᴡɴʟᴏᴀᴅs</b>\n"
        )

        for platform, count in platform_stats.items():

            if count > 0:

                emoji = {
                    "youtube": "▶️",
                    "instagram": "📸",
                    "facebook": "📘",
                    "tiktok": "🎵",
                    "pinterest": "📌",
                    "twitter": "𝕏",
                    "terabox": "📦"
                }.get(
                    platform,
                    "📥"
                )

                stats_text += (
                    f"├ {emoji} "
                    f"{platform.title()}: "
                    f"<b>{format_number(count)}</b>\n"
                )

        stats_text += "\n"

    # API stats

    api_stats = stats.get(
        "api_stats",
        {}
    )

    if any(api_stats.values()):

        stats_text += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>📡 API Usᴀɢᴇ</b>\n"
        )

        for api, count in api_stats.items():

            if count > 0:

                emoji = {
                    "fastsaver": "🟢",
                    "yoinku": "🔵",
                    "Terabox": "🟣",
                    "instagram_api": "🟠",
                    "getvidfb": "🟡"
                }.get(
                    api,
                    "🔹"
                )

                stats_text += (
                    f"├ {emoji} "
                    f"{api.title()}: "
                    f"<b>{format_number(count)}</b>\n"
                )

        stats_text += "\n"

    stats_text += (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 <b>Lᴀsᴛ Uᴘᴅᴀᴛᴇᴅ:</b> "
        f"{datetime.now().strftime('%d %b %Y, %I:%M %p')}"
    )

    return stats_text


def build_stats_keyboard():
    """Build stats keyboard"""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 Rᴇғʀᴇsʜ",
                    callback_data="stats_refresh"
                ),
                InlineKeyboardButton(
                    "🔙 Bᴀᴄᴋ",
                    callback_data="back_to_start"
                )
            ]
        ]
    )


# ==================== STATS COMMAND ====================

async def stats_command(
    client,
    message
):
    """Handle /stats command — Admin only"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Aᴅᴍɪɴ ᴏɴʟʏ!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    chat_id = message.chat.id

    try:

        stats = get_all_stats()

        stats_text = build_stats_text(
            stats
        )

        keyboard = build_stats_keyboard()

        await client.send_message(
            chat_id=chat_id,
            text=stats_text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    except Exception as e:

        await client.send_message(
            chat_id=chat_id,
            text=(
                f"❌ <b>Error:</b> "
                f"{escape_html(str(e))}"
            ),
            parse_mode=enums.ParseMode.HTML
        )


# ==================== STATS REFRESH ====================

async def stats_refresh_callback(
    client,
    callback_query
):
    """Handle stats refresh button"""

    query = callback_query

    user = query.from_user

    if not user:
        return

    if not is_admin(user.id):

        await query.answer(
            "❌ Admin only!",
            show_alert=True
        )

        return

    await query.answer(
        "🔄 Rᴇғʀᴇsʜɪɴɢ..."
    )

    try:

        stats = get_all_stats()

        stats_text = build_stats_text(
            stats
        )

        keyboard = build_stats_keyboard()

        await query.message.edit_text(
            text=stats_text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    except Exception as e:

        try:

            await query.answer(
                f"❌ Error: {str(e)[:50]}",
                show_alert=True
            )

        except:

            pass


# ==================== REGISTER HANDLERS ====================

def register_stats_handlers(app):
    """Register all handlers for stats module"""

    app.add_handler(
        MessageHandler(
            stats_command,
            filters.command("stats")
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            stats_refresh_callback,
            filters.regex(
                r"^stats_refresh$"
            )
        )
    )