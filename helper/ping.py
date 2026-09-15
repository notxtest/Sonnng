# helper/ping.py

import time
import psutil
import platform

from pyrogram import filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.database import users_col, credits_col, premium_col
from config import ADMIN_IDS


# ==================== CONFIG ====================

BOT_START_TIME = time.time()


# ==================== ADMIN CHECK ====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ==================== HELPERS ====================

def get_bot_uptime():
    """Get bot uptime in human readable format"""

    uptime_seconds = int(
        time.time() - BOT_START_TIME
    )

    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"

    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"

    elif minutes > 0:
        return f"{minutes}m {seconds}s"

    else:
        return f"{seconds}s"


def get_system_stats():
    """Get system stats"""

    try:

        cpu_percent = psutil.cpu_percent(
            interval=1
        )

        memory = psutil.virtual_memory()

        disk = psutil.disk_usage('/')

        return {
            "cpu": cpu_percent,
            "ram_total": memory.total / (1024**3),
            "ram_used": memory.used / (1024**3),
            "ram_percent": memory.percent,
            "disk_total": disk.total / (1024**3),
            "disk_used": disk.used / (1024**3),
            "disk_percent": disk.percent,
            "os": platform.system(),
            "python": platform.python_version()
        }

    except:

        return None


def get_db_stats():
    """Get database stats"""

    try:

        total_users = users_col.count_documents({})

        total_credits = credits_col.count_documents({})

        total_premium = premium_col.count_documents({})

        now = time.time()

        active_premium = premium_col.count_documents(
            {
                "expiry": {
                    "$gt": now
                }
            }
        )

        return {
            "total_users": total_users,
            "total_credits": total_credits,
            "total_premium": total_premium,
            "active_premium": active_premium
        }

    except:

        return None


def build_ping_text(
    latency,
    include_latency=True
):
    """Build ping message text"""

    db_stats = get_db_stats()

    system_stats = get_system_stats()

    uptime = get_bot_uptime()

    python_ver = platform.python_version()

    ping_text = (
        f"🏓 <b>Pᴏɴɢ!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>🤖 Bᴏᴛ Sᴛᴀᴛᴜs</b>\n"
        f"├ Sᴛᴀᴛᴜs: <b>🟢 Oɴʟɪɴᴇ</b>\n"
    )

    if include_latency:

        ping_text += (
            f"├ Lᴀᴛᴇɴᴄʏ: "
            f"<b>{latency}ms</b>\n"
        )

    ping_text += (
        f"├ Uᴘᴛɪᴍᴇ: <b>{uptime}</b>\n"
        f"└ Pʏᴛʜᴏɴ: <b>{python_ver}</b>\n\n"
    )

    if system_stats:

        ping_text += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>🖥️ Sʏsᴛᴇᴍ Sᴛᴀᴛs</b>\n"
            f"├ CPU: "
            f"<b>{system_stats['cpu']:.1f}%</b>\n"
            f"├ RAM: "
            f"<b>{system_stats['ram_used']:.1f}GB</b> / "
            f"{system_stats['ram_total']:.1f}GB "
            f"(<b>{system_stats['ram_percent']:.0f}%</b>)\n"
            f"└ Dɪsᴋ: "
            f"<b>{system_stats['disk_used']:.1f}GB</b> / "
            f"{system_stats['disk_total']:.1f}GB "
            f"(<b>{system_stats['disk_percent']:.0f}%</b>)\n\n"
        )

    if db_stats:

        ping_text += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>📊 Dᴀᴛᴀʙᴀsᴇ Sᴛᴀᴛs</b>\n"
            f"├ Tᴏᴛᴀʟ Usᴇʀs: "
            f"<b>{db_stats['total_users']}</b>\n"
            f"├ Usᴇʀs ᴡɪᴛʜ Cʀᴇᴅɪᴛs: "
            f"<b>{db_stats['total_credits']}</b>\n"
            f"├ Tᴏᴛᴀʟ Pʀᴇᴍɪᴜᴍ: "
            f"<b>{db_stats['total_premium']}</b>\n"
            f"└ Aᴄᴛɪᴠᴇ Pʀᴇᴍɪᴜᴍ: "
            f"<b>{db_stats['active_premium']}</b>\n\n"
        )

    if include_latency:

        ping_text += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⏱️ <b>Rᴇsᴘᴏɴsᴇ Tɪᴍᴇ:</b> "
            f"{latency}ms"
        )

    return ping_text


def build_ping_keyboard():
    """Build ping keyboard"""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 Rᴇғʀᴇsʜ",
                    callback_data="ping_refresh"
                ),
                InlineKeyboardButton(
                    "🔙 Bᴀᴄᴋ",
                    callback_data="back_to_start"
                )
            ]
        ]
    )


# ==================== PING COMMAND ====================

async def ping_command(
    client,
    message
):
    """Handle /ping command — Admin only"""

    user = message.from_user

    chat_id = message.chat.id

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    try:

        # Latency measure

        start_time = time.time()

        msg = await client.send_message(
            chat_id=chat_id,
            text="🏓 <b>Pinging...</b>",
            parse_mode=enums.ParseMode.HTML
        )

        end_time = time.time()

        latency = int(
            (end_time - start_time) * 1000
        )

        # Build text + keyboard

        ping_text = build_ping_text(
            latency,
            include_latency=True
        )

        keyboard = build_ping_keyboard()

        await client.edit_message_text(
            chat_id=chat_id,
            message_id=msg.id,
            text=ping_text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:

        try:

            await client.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ <b>Error:</b> "
                    f"{str(e)[:100]}"
                ),
                parse_mode=enums.ParseMode.HTML
            )

        except:

            pass


# ==================== PING REFRESH ====================

async def ping_refresh_callback(
    client,
    callback_query
):
    """Handle ping refresh button — Admin only"""

    query = callback_query

    user = query.from_user

    if not is_admin(user.id):

        await query.answer(
            "❌ Admin only!",
            show_alert=True
        )

        return

    await query.answer(
        "🔄 Refreshing..."
    )

    try:

        # Refresh pe latency = 0
        # (ya "N/A"), isliye include_latency=False

        ping_text = build_ping_text(
            latency=0,
            include_latency=False
        )

        keyboard = build_ping_keyboard()

        await query.message.edit_text(
            text=ping_text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard
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

def register_ping_handlers(app):
    """Register all handlers for ping module"""

    app.add_handler(
        MessageHandler(
            ping_command,
            filters.command("ping")
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            ping_refresh_callback,
            filters.regex(r"^ping_refresh$")
        )
    )