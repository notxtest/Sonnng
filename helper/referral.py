# helper/referral.py

import time
import random
import string
import html
from urllib.parse import quote

from datetime import datetime, timedelta
from pymongo import ReturnDocument

from pyrogram import filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.database import users_col, referrals_col, credits_col

from helper.credit import (
    add_credits_atomic,
    get_credits,
    deduct_credit_atomic
)

from config import (
    REFERRAL_REWARD,
    REFERRAL_DOWNLOADS_REQUIRED
)


# ==================== HELPERS ====================

def escape_html(text):
    if not text:
        return "Unknown"

    return html.escape(str(text))


def generate_referral_code(user_id):
    random_str = ''.join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=6
        )
    )

    return f"REF_{user_id}_{random_str}"


async def get_referral_code(user_id):
    user = users_col.find_one({
        "_id": user_id
    })

    if user and user.get("referral_code"):
        return user["referral_code"]

    code = generate_referral_code(
        user_id
    )

    users_col.update_one(
        {
            "_id": user_id
        },
        {
            "$set": {
                "referral_code": code
            }
        },
        upsert=True
    )

    return code


async def get_referral_count(user_id):
    return referrals_col.count_documents({
        "referrer_id": user_id
    })


async def get_referral_earnings(user_id):
    pipeline = [
        {
            "$match": {
                "referrer_id": user_id
            }
        },
        {
            "$group": {
                "_id": None,
                "total": {
                    "$sum": "$credits_given"
                }
            }
        }
    ]

    result = list(
        referrals_col.aggregate(
            pipeline
        )
    )

    return (
        result[0]["total"]
        if result
        else 0
    )


async def get_pending_referrals(user_id):
    """Get referrals that are pending (not yet rewarded)"""

    return list(
        referrals_col.find(
            {
                "referrer_id": user_id,
                "rewarded": False
            }
        )
    )


# ==================== PROCESS REFERRAL (Only on first start) ====================

async def process_referral_atomic(
    user_id: int,
    code: str
) -> dict:
    """
    Process referral — ONLY stores referral, NO reward yet.
    Reward given after referred user completes required downloads.
    """

    if not code:
        return {
            "success": False,
            "message": "Invalid referral code"
        }

    referrer = users_col.find_one({
        "referral_code": code
    })

    if not referrer:
        return {
            "success": False,
            "message": "Invalid referral code"
        }

    referrer_id = referrer["_id"]

    if user_id == referrer_id:
        return {
            "success": False,
            "message": "You cannot refer yourself!"
        }

    # ATOMIC: Check if already referred

    result = users_col.find_one_and_update(
        {
            "_id": user_id,
            "referred_by": {
                "$exists": False
            }
        },
        {
            "$set": {
                "referred_by": referrer_id
            }
        },
        return_document=ReturnDocument.AFTER
    )

    if not result:
        return {
            "success": False,
            "message": "Already referred"
        }

    # Store referral without reward

    referrals_col.insert_one(
        {
            "referrer_id": referrer_id,
            "referred_id": user_id,
            "credits_given": 0,
            "rewarded": False,
            "download_count": 0,
            "created_at": time.time()
        }
    )

    return {
        "success": True,
        "message": (
            f"Referral recorded! "
            f"Referrer will get "
            f"{REFERRAL_REWARD} credits after "
            f"{REFERRAL_DOWNLOADS_REQUIRED} downloads."
        ),
        "referrer_id": referrer_id
    }


# ==================== CHECK AND REWARD REFERRALS ====================

async def check_and_reward_referrals(
    client,
    user_id: int
):
    """
    Called after each successful download.

    If referred user completes required downloads,
    reward referrer.

    Sends notification to referrer via client.
    """

    # Check if this user was referred

    user_data = users_col.find_one({
        "_id": user_id
    })

    if not user_data:
        return None

    referred_by = user_data.get(
        "referred_by"
    )

    if not referred_by:
        return None

    # Find the referral record

    referral = referrals_col.find_one(
        {
            "referrer_id": referred_by,
            "referred_id": user_id,
            "rewarded": False
        }
    )

    if not referral:
        return None

    # Increment download count ATOMICALLY
    #
    # Using $inc prevents lost updates if two
    # successful downloads are processed at once.

    count_result = referrals_col.find_one_and_update(
        {
            "_id": referral["_id"],
            "rewarded": False
        },
        {
            "$inc": {
                "download_count": 1
            }
        },
        return_document=ReturnDocument.AFTER
    )

    if not count_result:
        return None

    new_count = count_result.get(
        "download_count",
        0
    )

    # Check if required downloads completed

    if new_count >= REFERRAL_DOWNLOADS_REQUIRED:

        # ATOMIC: Reward referrer

        result = referrals_col.find_one_and_update(
            {
                "_id": referral["_id"],
                "rewarded": False
            },
            {
                "$set": {
                    "rewarded": True,
                    "credits_given": REFERRAL_REWARD
                }
            },
            return_document=ReturnDocument.AFTER
        )

        if result:

            new_balance = await add_credits_atomic(
                referred_by,
                REFERRAL_REWARD
            )

            # NOTIFY REFERRER

            if client is not None:

                try:

                    await client.send_message(
                        chat_id=referred_by,
                        text=(
                            f"🎉 <b>Referral Reward!</b>\n\n"
                            f"👥 Your referred user completed "
                            f"<b>{REFERRAL_DOWNLOADS_REQUIRED} downloads</b>!\n"
                            f"💰 <b>+{REFERRAL_REWARD} credits</b> "
                            f"added to your balance.\n"
                            f"💳 <b>New Balance:</b> "
                            f"{new_balance} credits\n\n"
                            f"📌 Keep sharing your referral link "
                            f"to earn more!"
                        ),
                        parse_mode=enums.ParseMode.HTML
                    )

                except Exception:
                    pass

            return {
                "referrer_id": referred_by,
                "credits_added": REFERRAL_REWARD,
                "new_balance": new_balance
            }

    return None


# ==================== REFER COMMAND ====================

async def refer_command(
    client,
    message
):
    user = message.from_user

    if not user:
        return

    user_id = user.id

    chat_id = message.chat.id

    referral_code = await get_referral_code(
        user_id
    )

    referral_count = await get_referral_count(
        user_id
    )

    balance = await get_credits(
        user_id
    )

    earnings = await get_referral_earnings(
        user_id
    )

    bot_username = client.me.username

    refer_text = (
        f"👥 <b>ʀᴇꜰᴇʀ & ᴇᴀʀɴ</b>\n\n"
        f"🔗 <b>ʏᴏᴜʀ ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ:</b>\n"
        f"<code>https://t.me/{bot_username}"
        f"?start=ref_{referral_code}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>ᴛᴏᴛᴀʟ ʀᴇꜰᴇʀʀᴀʟꜱ:</b> "
        f"{referral_count}\n"
        f"💰 <b>ᴇᴀʀɴᴇᴅ:</b> "
        f"{earnings} ᴄʀᴇᴅɪᴛꜱ\n"
        f"💳 <b>ʙᴀʟᴀɴᴄᴇ:</b> "
        f"{balance} ᴄʀᴇᴅɪᴛꜱ\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 <b>ʜᴏᴡ ɪᴛ ᴡᴏʀᴋꜱ:</b>\n"
        f"① ꜱʜᴀʀᴇ ʏᴏᴜʀ ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ\n"
        f"② ꜰʀɪᴇɴᴅ ᴊᴏɪɴꜱ ᴜꜱɪɴɢ ʏᴏᴜʀ ʟɪɴᴋ\n"
        f"③ ꜰʀɪᴇɴᴅ ᴄᴏᴍᴘʟᴇᴛᴇꜱ "
        f"<b>{REFERRAL_DOWNLOADS_REQUIRED} ᴅᴏᴡɴʟᴏᴀᴅꜱ</b>\n"
        f"④ ʏᴏᴜ ʀᴇᴄᴇɪᴠᴇ "
        f"<b>{REFERRAL_REWARD} ᴄʀᴇᴅɪᴛꜱ</b>! 🎉\n\n"
        f"🚀 <b>ꜱʜᴀʀᴇ ᴍᴏʀᴇ • ᴇᴀʀɴ ᴍᴏʀᴇ</b>"
    )

    # FIX: Properly URL-encode the share text
    share_text = (
        f"Join this bot!\n"
        f"https://t.me/{bot_username}?start=ref_{referral_code}"
    )

    share_url = (
        "https://t.me/share/url?"
        f"url={quote(share_text)}"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🚀 ꜱʜᴀʀᴇ",
                    url=share_url
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 ʙᴀᴄᴋ",
                    callback_data="back_to_start"
                )
            ]
        ]
    )

    await client.send_message(
        chat_id=chat_id,
        text=refer_text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )


# ==================== REFER CALLBACK ====================

async def refer_callback(
    client,
    callback_query
):
    query = callback_query

    await query.answer()

    user = query.from_user

    user_id = user.id

    referral_code = await get_referral_code(
        user_id
    )

    referral_count = await get_referral_count(
        user_id
    )

    balance = await get_credits(
        user_id
    )

    earnings = await get_referral_earnings(
        user_id
    )

    bot_username = client.me.username

    refer_text = (
        f"👥 <b>ʀᴇꜰᴇʀ & ᴇᴀʀɴ</b>\n\n"
        f"🔗 <b>ʏᴏᴜʀ ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ:</b>\n"
        f"<code>https://t.me/{bot_username}"
        f"?start=ref_{referral_code}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>ᴛᴏᴛᴀʟ ʀᴇꜰᴇʀʀᴀʟꜱ:</b> "
        f"{referral_count}\n"
        f"💰 <b>ᴇᴀʀɴᴇᴅ:</b> "
        f"{earnings} ᴄʀᴇᴅɪᴛꜱ\n"
        f"💳 <b>ʙᴀʟᴀɴᴄᴇ:</b> "
        f"{balance} ᴄʀᴇᴅɪᴛꜱ\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 <b>ʜᴏᴡ ɪᴛ ᴡᴏʀᴋꜱ:</b>\n"
        f"① ꜱʜᴀʀᴇ ʏᴏᴜʀ ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ\n"
        f"② ꜰʀɪᴇɴᴅ ᴊᴏɪɴꜱ ᴜꜱɪɴɢ ʏᴏᴜʀ ʟɪɴᴋ\n"
        f"③ ꜰʀɪᴇɴᴅ ᴄᴏᴍᴘʟᴇᴛᴇꜱ "
        f"<b>{REFERRAL_DOWNLOADS_REQUIRED} ᴅᴏᴡɴʟᴏᴀᴅꜱ</b>\n"
        f"④ ʏᴏᴜ ʀᴇᴄᴇɪᴠᴇ "
        f"<b>{REFERRAL_REWARD} ᴄʀᴇᴅɪᴛꜱ</b>! 🎉\n\n"
        f"🚀 <b>ꜱʜᴀʀᴇ ᴍᴏʀᴇ • ᴇᴀʀɴ ᴍᴏʀᴇ</b>"
    )

    # FIX: Properly URL-encode the share text
    share_text = (
        f"Join this bot!\n"
        f"https://t.me/{bot_username}?start=ref_{referral_code}"
    )

    share_url = (
        "https://t.me/share/url?"
        f"url={quote(share_text)}"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🚀 ꜱʜᴀʀᴇ",
                    url=share_url
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 ʙᴀᴄᴋ",
                    callback_data="back_to_start"
                )
            ]
        ]
    )

    try:

        await query.message.edit_text(
            text=refer_text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception:

        pass


# ==================== REGISTER HANDLERS ====================

def register_refer_handlers(app):

    app.add_handler(
        MessageHandler(
            refer_command,
            filters.command("refer")
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            refer_callback,
            filters.regex(r"^refer$")
        )
    )
