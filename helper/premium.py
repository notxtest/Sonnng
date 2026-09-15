# helper/premium.py

import time
import html

from datetime import datetime, timedelta

from pyrogram import filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.database import premium_col

from config import (
    ADMIN_IDS,
    CONTACT_ADMIN_URL,
    PREMIUM_PRICE,
    PREMIUM_BENEFITS
)


# ==================== ADMIN CHECK ====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ==================== HELPERS ====================

def escape_html(text):
    if not text:
        return "Unknown"

    return html.escape(str(text))


# ==================== PREMIUM HELPERS ====================

async def is_premium(user_id: int) -> bool:
    """Check if user has active premium"""

    data = premium_col.find_one({
        "_id": user_id
    })

    if not data:
        return False

    expiry = data.get(
        "expiry",
        0
    )

    if expiry < time.time():

        premium_col.delete_one({
            "_id": user_id
        })

        return False

    return True


async def get_premium_expiry(user_id: int) -> int:
    """Get premium expiry timestamp"""

    data = premium_col.find_one({
        "_id": user_id
    })

    if not data:
        return 0

    return data.get(
        "expiry",
        0
    )


async def get_premium_remaining(user_id: int) -> dict:
    """Get remaining premium time in days, hours, minutes"""

    expiry = await get_premium_expiry(
        user_id
    )

    if expiry == 0:
        return {
            "days": 0,
            "hours": 0,
            "minutes": 0,
            "text": "Expired"
        }

    now = time.time()

    if expiry <= now:

        premium_col.delete_one({
            "_id": user_id
        })

        return {
            "days": 0,
            "hours": 0,
            "minutes": 0,
            "text": "Expired"
        }

    remaining = int(
        expiry - now
    )

    days = remaining // 86400

    hours = (
        remaining % 86400
    ) // 3600

    minutes = (
        remaining % 3600
    ) // 60

    if days > 0:

        text = f"{days}d {hours}h"

    elif hours > 0:

        text = f"{hours}h {minutes}m"

    else:

        text = f"{minutes}m"

    return {
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "text": text
    }


async def get_premium_expiry_date(
    user_id: int
) -> str:
    """Get premium expiry date in readable format"""

    expiry = await get_premium_expiry(
        user_id
    )

    if expiry == 0:
        return "N/A"

    return datetime.fromtimestamp(
        expiry
    ).strftime(
        "%d %b %Y, %I:%M %p"
    )


async def add_premium(
    user_id: int,
    duration_str: str
) -> bool:
    """Add premium with validation"""

    if not duration_str:
        return False

    # Validate format

    if duration_str[-1] not in [
        'h',
        'd',
        'm'
    ]:
        return False

    try:

        value = int(
            duration_str[:-1]
        )

    except ValueError:

        return False

    if value <= 0:
        return False

    if duration_str[-1] == "h":

        delta = timedelta(
            hours=value
        )

    elif duration_str[-1] == "d":

        delta = timedelta(
            days=value
        )

    elif duration_str[-1] == "m":

        delta = timedelta(
            minutes=value
        )

    else:

        return False

    current_expiry = await get_premium_expiry(
        user_id
    )

    if current_expiry > time.time():

        new_expiry = (
            current_expiry
            + delta.total_seconds()
        )

    else:

        new_expiry = (
            time.time()
            + delta.total_seconds()
        )

    premium_col.update_one(
        {
            "_id": user_id
        },
        {
            "$set": {
                "expiry": new_expiry
            }
        },
        upsert=True
    )

    return True


async def remove_premium(
    user_id: int
) -> bool:
    """Remove premium from user"""

    result = premium_col.delete_one({
        "_id": user_id
    })

    return result.deleted_count > 0


# ==================== PREMIUM MESSAGE BUILDER ====================

async def build_premium_text(
    user_id: int
) -> str:
    """Build premium message text (common for /premium and callback)"""

    premium = await is_premium(
        user_id
    )

    if premium:

        remaining = await get_premium_remaining(
            user_id
        )

        expiry_date = await get_premium_expiry_date(
            user_id
        )

        status_text = (
            f"🟢 <b>ᴀᴄᴛɪᴠᴇ</b>\n\n"
            f"📅 <b>ᴇxᴘɪʀʏ:</b> "
            f"{expiry_date}\n"
            f"⏳ <b>ʀᴇᴍᴀɪɴɪɴɢ:</b> "
            f"{remaining['text']}"
        )

    else:

        status_text = (
            "🔴 <b>ɴᴏᴛ ᴀᴄᴛɪᴠᴇ</b>"
        )

    premium_text = (
        f"👑 <b>ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ</b>\n\n"
        f"ꜱᴛᴀᴛᴜꜱ: {status_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote expandable>"
        f"<b>ᴘʀᴇᴍɪᴜᴍ ʙᴇɴᴇꜰɪᴛꜱ</b>\n\n"
        f"{PREMIUM_BENEFITS}"
        f"</blockquote>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>ᴘʀɪᴄᴇ:</b> "
        f"{PREMIUM_PRICE}\n\n"
        f"📞 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ᴛᴏ ɢᴇᴛ ᴘʀᴇᴍɪᴜᴍ"
    )

    return premium_text


def build_premium_keyboard() -> InlineKeyboardMarkup:
    """Build premium keyboard (common for /premium and callback)"""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📞 Contact Admin",
                    url=CONTACT_ADMIN_URL
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back_to_start"
                )
            ]
        ]
    )


# ==================== PREMIUM COMMAND ====================

async def premium_command(
    client,
    message
):
    """Handle /premium command"""

    user_id = message.from_user.id

    chat_id = message.chat.id

    premium_text = await build_premium_text(
        user_id
    )

    keyboard = build_premium_keyboard()

    await client.send_message(
        chat_id=chat_id,
        text=premium_text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard
    )


# ==================== PREMIUM CALLBACK ====================

async def premium_callback(
    client,
    callback_query
):
    """Handle Premium button callback — message edit"""

    query = callback_query

    await query.answer()

    user_id = query.from_user.id

    premium_text = await build_premium_text(
        user_id
    )

    keyboard = build_premium_keyboard()

    try:

        await query.message.edit_text(
            text=premium_text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception:

        pass


# ==================== ADMIN PREMIUM COMMANDS ====================

async def addpremium_command(
    client,
    message
):
    """Admin: /addpremium user_id 10d or /addpremium user_id 24h"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    args = message.command[1:]

    if len(args) < 2:

        await message.reply_text(
            "❌ <b>Usage:</b>\n"
            "<code>/addpremium user_id 10d</code> — 10 days\n"
            "<code>/addpremium user_id 24h</code> — 24 hours\n"
            "<code>/addpremium user_id 30m</code> — 30 minutes\n\n"
            "Supported: h (hours), d (days), m (minutes)",
            parse_mode=enums.ParseMode.HTML
        )

        return

    try:

        target_id = int(
            args[0]
        )

        duration_str = args[1]

    except ValueError:

        await message.reply_text(
            "❌ <b>Invalid user ID!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    # Validate duration format

    if duration_str[-1] not in [
        'h',
        'd',
        'm'
    ]:

        await message.reply_text(
            "❌ <b>Invalid format!</b>\n"
            "Use: <code>10d</code> (days), "
            "<code>24h</code> (hours), "
            "<code>30m</code> (minutes)",
            parse_mode=enums.ParseMode.HTML
        )

        return

    try:

        value = int(
            duration_str[:-1]
        )

    except ValueError:

        await message.reply_text(
            "❌ <b>Invalid number!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    if value <= 0:

        await message.reply_text(
            "❌ <b>Duration must be positive!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    success = await add_premium(
        target_id,
        duration_str
    )

    if not success:

        await message.reply_text(
            "❌ <b>Failed to add premium!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    remaining = await get_premium_remaining(
        target_id
    )

    expiry_date = await get_premium_expiry_date(
        target_id
    )

    # Notify user

    try:

        await client.send_message(
            chat_id=target_id,
            text=(
                f"👑 <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴀᴛᴇᴅ</b>\n\n"
                f"✨ <i>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴘʀᴇᴍɪᴜᴍ!</i>\n\n"
                f"<blockquote>"
                f"🎁 <b>ᴘʟᴀɴ:</b> ᴘʀᴇᴍɪᴜᴍ\n"
                f"⏱ <b>ᴀᴅᴅᴇᴅ:</b> {duration_str}\n"
                f"📅 <b>ᴇxᴘɪʀʏ:</b> {expiry_date}\n"
                f"⏳ <b>ʀᴇᴍᴀɪɴɪɴɢ:</b> {remaining['text']}"
                f"</blockquote>\n\n"
                f"💎 <b>ᴇɴᴊᴏʏ ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ʙᴇɴᴇꜰɪᴛꜱ!</b>\n\n"
                f"🚀 <i>ᴜɴʟɪᴍɪᴛᴇᴅ ᴅᴏᴡɴʟᴏᴀᴅꜱ • ɴᴏ ᴄʀᴇᴅɪᴛ ᴅᴇᴅᴜᴄᴛɪᴏɴ</i>"
            ),
            parse_mode=enums.ParseMode.HTML
        )

    except:

        pass

    await message.reply_text(
        (
            f"✅ <b>Premium Added!</b>\n\n"
            f"👤 User: <code>{target_id}</code>\n"
            f"⏱ Duration: <b>{duration_str}</b>\n"
            f"📅 Expiry: <b>{expiry_date}</b>\n"
            f"⏳ Remaining: "
            f"<b>{remaining['text']}</b>"
        ),
        parse_mode=enums.ParseMode.HTML
    )


async def delpremium_command(
    client,
    message
):
    """Admin: /delpremium user_id"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    args = message.command[1:]

    if len(args) < 1:

        await message.reply_text(
            "❌ <b>Usage:</b>\n"
            "<code>/delpremium user_id</code>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    try:

        target_id = int(
            args[0]
        )

    except ValueError:

        await message.reply_text(
            "❌ <b>Invalid user ID!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    success = await remove_premium(
        target_id
    )

    if not success:

        await message.reply_text(
            "❌ <b>User is not premium!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    try:

        await client.send_message(
            chat_id=target_id,
            text=(
                f"❌ <b>ᴘʀᴇᴍɪᴜᴍ ʀᴇᴍᴏᴠᴇᴅ</b>\n\n"
                f"⚠️ <i>ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ ʜᴀꜱ ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ.</i>\n\n"
                f"<blockquote>"
                f"👑 <b>ꜱᴛᴀᴛᴜꜱ:</b> ɴᴏᴛ ᴀᴄᴛɪᴠᴇ\n"
                f"💎 <b>ᴘʀᴇᴍɪᴜᴍ:</b> ʀᴇᴍᴏᴠᴇᴅ"
                f"</blockquote>\n\n"
                f"📞 <b>ᴡᴀɴᴛ ᴘʀᴇᴍɪᴜᴍ ᴀɢᴀɪɴ?</b>\n"
                f"ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ᴛᴏ ʀᴇᴀᴄᴛɪᴠᴀᴛᴇ."
            ),
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📞 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ",
                            url=CONTACT_ADMIN_URL
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="back_to_start"
                        )
                    ]
                ]
            )
        )

    except:

        pass

    await message.reply_text(
        (
            f"✅ <b>Premium Removed!</b>\n\n"
            f"👤 User: <code>{target_id}</code>"
        ),
        parse_mode=enums.ParseMode.HTML
    )


async def allpremium_command(
    client,
    message
):
    """Admin: /allpremium — Show all premium users"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    all_premium = list(
        premium_col.find({})
    )

    if not all_premium:

        await message.reply_text(
            "❌ <b>No premium users found!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    active_users = []

    now = time.time()

    for p in all_premium:

        expiry = p.get(
            "expiry",
            0
        )

        if expiry > now:

            remaining = int(
                (expiry - now) / 86400
            )

            active_users.append(
                {
                    "user_id": p.get("_id"),
                    "remaining": remaining
                }
            )

    if not active_users:

        await message.reply_text(
            "❌ <b>No active premium users!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    active_users.sort(
        key=lambda x: x["remaining"],
        reverse=True
    )

    text = (
        f"👑 <b>Premium Users</b>\n\n"
    )

    text += (
        f"👥 Total Active: "
        f"<b>{len(active_users)}</b>\n\n"
    )

    text += (
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    for i, p in enumerate(
        active_users[:20],
        1
    ):

        user_id = p["user_id"]

        remaining = p["remaining"]

        text += (
            f"{i}. <code>{user_id}</code> "
            f"— <b>{remaining} days</b>\n"
        )

    if len(active_users) > 20:

        text += (
            f"\n... and "
            f"{len(active_users) - 20} "
            f"more users"
        )

    await message.reply_text(
        text,
        parse_mode=enums.ParseMode.HTML
    )


# ==================== REGISTER HANDLERS ====================

def register_premium_handlers(app):
    """Register all handlers for premium module"""

    app.add_handler(
        MessageHandler(
            premium_command,
            filters.command("premium")
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            premium_callback,
            filters.regex(r"^premium$")
        )
    )

    app.add_handler(
        MessageHandler(
            addpremium_command,
            filters.command("addpremium")
        )
    )

    app.add_handler(
        MessageHandler(
            delpremium_command,
            filters.command("delpremium")
        )
    )

    app.add_handler(
        MessageHandler(
            allpremium_command,
            filters.command("allpremium")
        )
    )