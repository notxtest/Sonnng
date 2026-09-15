# helper/ads.py

import time
import random
import string
import requests
import html
import asyncio

from urllib.parse import quote
from datetime import datetime, timedelta
from pymongo import ReturnDocument

from pyrogram import filters, enums


from helper.database import ads_col, users_col, tutorial_col
from helper.credit import add_credits_atomic, get_credits

from config import (
    VPLINK_API,
    MAX_ADS_PER_DAY,
    ADS_REWARD,
    AD_TIMER,
    BOT_USERNAME,
    ADMIN_IDS,
)


# ==================== ADMIN CHECK ====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ==================== HELPERS ====================

def escape_html(text):
    if not text:
        return "Unknown"
    return html.escape(str(text))


def generate_token():
    return ''.join(
        random.choices(
            string.ascii_letters + string.digits,
            k=10
        )
    )


def get_current_date():
    return datetime.now().strftime("%Y-%m-%d")


# ==================== SHORT LINK ====================

async def create_short_link_async(long_url: str) -> str:
    """Async short link creation"""

    try:
        # Python 3.14 compatible
        loop = asyncio.get_running_loop()

        encoded_url = quote(long_url, safe='')

        api_url = (
            f"https://vplink.in/api"
            f"?api={VPLINK_API}"
            f"&url={encoded_url}"
            f"&format=text"
        )

        response = await loop.run_in_executor(
            None,
            lambda: requests.get(
                api_url,
                timeout=10
            )
        )

        if response.status_code == 200 and response.text:
            return response.text.strip()

        return None

    except Exception:
        return None


# ==================== ATOMIC TOKEN OPERATIONS ====================

async def reserve_ad_slot(user_id: int) -> dict:
    """
    ATOMIC: Reserve an ad slot for user.

    Flow:
    1. Daily limit check
    2. Purane pending tokens ko 'expired' mark karo
    3. Naya token create

    Returns:
    {"success": bool, "token": str, "message": str}
    """

    today = get_current_date()
    now = time.time()

    # Step 1: Daily limit check
    daily_count = ads_col.count_documents({
        "user_id": user_id,
        "date": today,
        "status": "completed"
    })

    if daily_count >= MAX_ADS_PER_DAY:
        return {
            "success": False,
            "message": "Daily limit reached"
        }

    # Step 2: Purane pending tokens ko expire karo
    ads_col.update_many(
        {
            "user_id": user_id,
            "status": "pending"
        },
        {
            "$set": {
                "status": "expired"
            }
        }
    )

    # Step 3: Naya token create
    token = generate_token()

    long_url = f"https://t.me/{BOT_USERNAME}?start=ad_{token}"

    short_url = await create_short_link_async(long_url)

    if not short_url:
        short_url = long_url

    ads_col.insert_one({
        "token": token,
        "user_id": user_id,
        "short_url": short_url,
        "long_url": long_url,
        "status": "pending",
        "date": today,
        "created_at": now,
        "expires_at": now + AD_TIMER,
        "completed_at": None
    })

    return {
        "success": True,
        "token": token,
        "message": "New token created"
    }


async def verify_and_complete_token_atomic(
    user_id: int,
    token: str
) -> dict:
    """
    ATOMIC: Verify and complete token.

    Flow:
    1. Token check
    2. 60s check:
       - now < expires_at → BYPASS
       - now >= expires_at → SUCCESS + credits

    Returns:
    {
        "success": bool,
        "credits_added": int,
        "message": str,
        "bypassed": bool
    }
    """

    now = time.time()

    # Fetch token
    data = ads_col.find_one({
        "token": token
    })

    if not data:
        return {
            "success": False,
            "credits_added": 0,
            "message": "Token not found",
            "bypassed": False
        }

    if data.get("user_id") != user_id:
        return {
            "success": False,
            "credits_added": 0,
            "message": "Invalid user",
            "bypassed": False
        }

    status = data.get("status", "")

    if status == "completed":
        return {
            "success": False,
            "credits_added": 0,
            "message": "Already completed",
            "bypassed": False
        }

    if status == "expired":
        return {
            "success": False,
            "credits_added": 0,
            "message": "Token expired (naya token ban gaya)",
            "bypassed": False
        }

    if status == "bypassed":
        return {
            "success": False,
            "credits_added": 0,
            "message": "Bypass detected",
            "bypassed": True
        }

    if status != "pending":
        return {
            "success": False,
            "credits_added": 0,
            "message": "Invalid token status",
            "bypassed": False
        }

    # Status = pending
    expires_at = data.get("expires_at", 0)

    # 60s se pehle aaya?
    if now < expires_at:

        # BYPASS
        ads_col.update_one(
            {
                "token": token,
                "status": "pending"
            },
            {
                "$set": {
                    "status": "bypassed",
                    "bypassed_at": now
                }
            }
        )

        return {
            "success": False,
            "credits_added": 0,
            "message": "Bypass detected",
            "bypassed": True
        }

    # 60s ke baad aaya → SUCCESS
    result = ads_col.find_one_and_update(
        {
            "token": token,
            "status": "pending"
        },
        {
            "$set": {
                "status": "completed",
                "completed_at": now
            }
        },
        return_document=ReturnDocument.AFTER
    )

    if not result:
        # Koi aur process ne pehle hi complete kar diya
        return {
            "success": False,
            "credits_added": 0,
            "message": "Already processed",
            "bypassed": False
        }

    # Credits add
    new_balance = await add_credits_atomic(
        user_id,
        ADS_REWARD
    )

    return {
        "success": True,
        "credits_added": ADS_REWARD,
        "new_balance": new_balance,
        "message": "Credits added",
        "bypassed": False
    }


async def bypass_token(token: str):
    """Mark token as bypassed"""

    ads_col.update_one(
        {
            "token": token,
            "status": "pending"
        },
        {
            "$set": {
                "status": "bypassed",
                "bypassed_at": time.time()
            }
        }
    )


# ============================================================
# TUTORIAL STATE
# ============================================================

# PTB context.user_data ka Pyrogram equivalent.
# User ID ke according state maintain hogi.
tutorial_waiting_users = set()


# ==================== SET TUTORIAL ====================

async def set_tutorial_command(client, message):

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):
        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode=enums.ParseMode.HTML
        )
        return

    await message.reply_text(
        "🎬 <b>Set Tutorial Video</b>\n\n"
        "Send me a video file (MP4) to set as tutorial.",
        parse_mode=enums.ParseMode.HTML
    )

    tutorial_waiting_users.add(user.id)


async def handle_tutorial_video(client, message):

    user = message.from_user

    if not user:
        return

    # PTB:
    # context.user_data.get("waiting_for_tutorial")
    #
    # Pyrogram:
    # tutorial_waiting_users

    if user.id not in tutorial_waiting_users:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        tutorial_waiting_users.discard(user.id)

        return

    if not message.video:

        await message.reply_text(
            "❌ <b>Please send a video file!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    video = message.video

    file_id = video.file_id

    tutorial_col.delete_many({})

    tutorial_col.insert_one({
        "file_id": file_id,
        "set_by": user.id,
        "set_at": time.time()
    })

    tutorial_waiting_users.discard(user.id)

    await message.reply_text(
        "✅ <b>Tutorial Set!</b>",
        parse_mode=enums.ParseMode.HTML
    )


# ==================== EARN COMMAND ====================

async def earn_command(client, message):

    user_id = message.from_user.id
    chat_id = message.chat.id

    today = get_current_date()

    daily_count = ads_col.count_documents({
        "user_id": user_id,
        "date": today,
        "status": "completed"
    })

    remaining = MAX_ADS_PER_DAY - daily_count

    if remaining <= 0:

        await client.send_message(
            chat_id=chat_id,
            text=(
                "📺 <b>Watch & Earn</b>\n\n"
                "❌ <b>Daily limit reached!</b>"
            ),
            parse_mode=enums.ParseMode.HTML
        )

        return

    watch_text = (
        f"📺 <b>Watch & Earn</b>\n\n"
        f"💰 <b>Reward:</b> {ADS_REWARD} credits\n"
        f"📊 <b>Today:</b> "
        f"{daily_count}/{MAX_ADS_PER_DAY}\n"
        f"📌 <b>Remaining:</b> {remaining}\n\n"
        f"⏱️ <b>Wait {AD_TIMER} seconds</b> "
        f"after clicking the link!"
    )

    keyboard = [
        [
            {
                "text": "🎬 Watch Now",
                "callback_data": "watch_now"
            }
        ],
        [
            {
                "text": "📖 Tutorial",
                "callback_data": "watch_tutorial"
            }
        ],
        [
            {
                "text": "🔙 Back",
                "callback_data": "back_to_start"
            }
        ]
    ]

    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎬 Watch Now",
                callback_data="watch_now"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 Tutorial",
                callback_data="watch_tutorial"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back_to_start"
            )
        ]
    ])

    await client.send_message(
        chat_id=chat_id,
        text=watch_text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard
    )


# ==================== WATCH EARN CALLBACK ====================

async def watch_earn_callback(client, query):

    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat.id

    today = get_current_date()

    daily_count = ads_col.count_documents({
        "user_id": user_id,
        "date": today,
        "status": "completed"
    })

    remaining = MAX_ADS_PER_DAY - daily_count

    if remaining <= 0:

        await query.message.edit_text(
            text=(
                "📺 <b>Watch & Earn</b>\n\n"
                "❌ <b>Daily limit reached!</b>"
            ),
            parse_mode=enums.ParseMode.HTML
        )

        return

    watch_text = (
        f"📺 <b>Watch & Earn</b>\n\n"
        f"💰 <b>Reward:</b> {ADS_REWARD} credits\n"
        f"📊 <b>Today:</b> "
        f"{daily_count}/{MAX_ADS_PER_DAY}\n"
        f"📌 <b>Remaining:</b> {remaining}\n\n"
        f"⏱️ <b>Wait {AD_TIMER} seconds</b> "
        f"after clicking the link!"
    )

    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎬 Watch Now",
                callback_data="watch_now"
            )
        ],
        [
            InlineKeyboardButton(
                "📖 Tutorial",
                callback_data="watch_tutorial"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back_to_start"
            )
        ]
    ])

    # Original PTB code mein edit_message_caption()
    # tha, lekin earn message text message hai.
    # Isliye Pyrogram mein edit_text() correct equivalent hai.

    await query.message.edit_text(
        text=watch_text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard
    )


# ==================== WATCH NOW ====================

async def watch_now_callback(client, query):

    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat.id

    # ATOMIC: Reserve slot
    result = await reserve_ad_slot(user_id)

    if not result["success"]:

        await query.message.edit_text(
            text=f"❌ <b>{result['message']}</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    token = result["token"]

    token_data = ads_col.find_one({
        "token": token
    })

    short_url = token_data.get(
        "short_url",
        ""
    )

    # Purana message delete karo
    try:
        await query.message.delete()
    except Exception:
        pass

    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    # Ad message bhejo
    ad_message = await client.send_message(
        chat_id=chat_id,
        text=(
            f"🔗 <b>Watch the ad to earn "
            f"{ADS_REWARD} credits!</b>\n\n"
            f"📌 Click the link:\n"
            f"<code>{short_url}</code>\n\n"
            f"⏳ <b>You have to wait "
            f"{AD_TIMER} seconds!</b>\n"
            f"⚠️ Don't close before "
            f"{AD_TIMER} seconds, warna bypass "
            f"detect ho jayega!"
        ),
        parse_mode=enums.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔗 Open Link",
                    url=short_url
                )
            ],
            [
                InlineKeyboardButton(
                    f"⏳ Timer: {AD_TIMER}s",
                    callback_data="ad_timer"
                )
            ]
        ])
    )

    # PTB JobQueue ka Pyrogram equivalent
    asyncio.create_task(
        auto_delete_ad_message(
            client,
            chat_id,
            ad_message.id
        )
    )


# ==================== AUTO DELETE AD MESSAGE ====================

async def auto_delete_ad_message(
    client,
    chat_id,
    message_id
):
    """AD_TIMER seconds baad ad message delete karo"""

    await asyncio.sleep(AD_TIMER)

    try:
        await client.delete_messages(
            chat_id=chat_id,
            message_ids=message_id
        )
    except Exception:
        pass


# ==================== AD TIMER ====================

async def ad_timer_callback(client, query):

    await query.answer(
        f"⏳ Wait {AD_TIMER} seconds before "
        f"clicking the link!",
        show_alert=False
    )


# ==================== TUTORIAL ====================

async def watch_tutorial_callback(client, query):

    await query.answer()

    chat_id = query.message.chat.id

    tutorial = tutorial_col.find_one({})

    if not tutorial or not tutorial.get("file_id"):

        await query.message.edit_text(
            text="❌ <b>Tutorial not available!</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    file_id = tutorial.get("file_id")

    try:
        await query.message.delete()
    except Exception:
        pass

    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    await client.send_video(
        chat_id=chat_id,
        video=file_id,
        caption="📖 <b>How to watch ads & earn</b>",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎬 Watch Now",
                    callback_data="watch_now"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back_to_start"
                )
            ]
        ])
    )


# ============================================================
# REGISTER HANDLERS
# ============================================================

def register_ads_handlers(app):

    # /earn
    app.add_handler(
        __import__("pyrogram").handlers.MessageHandler(
            earn_command,
            filters.command("earn")
        )
    )

    # /set_tutorial
    app.add_handler(
        __import__("pyrogram").handlers.MessageHandler(
            set_tutorial_command,
            filters.command("set_tutorial")
        )
    )

    # watch_earn
    app.add_handler(
        __import__("pyrogram").handlers.CallbackQueryHandler(
            watch_earn_callback,
            filters.regex(r"^watch_earn$")
        )
    )

    # watch_now
    app.add_handler(
        __import__("pyrogram").handlers.CallbackQueryHandler(
            watch_now_callback,
            filters.regex(r"^watch_now$")
        )
    )

    # watch_tutorial
    app.add_handler(
        __import__("pyrogram").handlers.CallbackQueryHandler(
            watch_tutorial_callback,
            filters.regex(r"^watch_tutorial$")
        )
    )

    # ad_timer
    app.add_handler(
        __import__("pyrogram").handlers.CallbackQueryHandler(
            ad_timer_callback,
            filters.regex(r"^ad_timer$")
        )
    )

    # Tutorial video
    app.add_handler(
        __import__("pyrogram").handlers.MessageHandler(
            handle_tutorial_video,
            filters.video
        )
    )

