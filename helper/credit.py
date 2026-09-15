# helper/credit.py

import time
import html

from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from pyrogram import filters
from pyrogram.handlers import MessageHandler


from helper.database import credits_col, users_col

from config import (
    ADMIN_IDS,
    DAILY_CLAIM_CREDITS,
    TIMEZONE_OFFSET
)


# ==================== ADMIN CHECK ====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def escape_html(text):
    if not text:
        return "Unknown"

    return html.escape(str(text))


# ==================== TIME HELPERS ====================

def get_ist_now() -> float:
    """Current IST timestamp (as unix time — same as UTC time, only used for display)"""
    return time.time()


def format_ist_time(timestamp: float) -> str:
    """Convert unix timestamp to IST readable string"""

    if not timestamp:
        return "Never"

    # Convert to IST
    ist_tz = timezone(
        timedelta(
            seconds=TIMEZONE_OFFSET
        )
    )

    dt = datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc
    ).astimezone(ist_tz)

    return dt.strftime(
        "%d %b %Y, %I:%M %p"
    )


def get_next_midnight_ist() -> float:
    """
    Returns timestamp of next 12:00 AM IST.
    Claim reset happens at midnight IST.
    """

    ist_tz = timezone(
        timedelta(
            seconds=TIMEZONE_OFFSET
        )
    )

    now_ist = datetime.now(
        tz=ist_tz
    )

    # Next midnight IST
    tomorrow_ist = (
        now_ist + timedelta(days=1)
    )

    next_midnight_ist = tomorrow_ist.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    # Convert back to UTC timestamp
    return next_midnight_ist.timestamp()


def get_today_midnight_ist() -> float:
    """
    Returns timestamp of today's 12:00 AM IST.
    Used to check if user has claimed today.
    """

    ist_tz = timezone(
        timedelta(
            seconds=TIMEZONE_OFFSET
        )
    )

    now_ist = datetime.now(
        tz=ist_tz
    )

    today_midnight_ist = now_ist.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    return today_midnight_ist.timestamp()


def format_time_remaining(seconds: float) -> str:
    """Format seconds into Xh Ym Zs"""

    if seconds <= 0:
        return "0s"

    hours = int(
        seconds // 3600
    )

    minutes = int(
        (seconds % 3600) // 60
    )

    secs = int(
        seconds % 60
    )

    parts = []

    if hours > 0:
        parts.append(
            f"{hours}h"
        )

    if minutes > 0:
        parts.append(
            f"{minutes}m"
        )

    parts.append(
        f"{secs}s"
    )

    return " ".join(parts)


# ==================== ATOMIC CREDIT OPERATIONS ====================

async def get_credits(user_id: int) -> int:
    """Get user's credit balance"""

    try:

        data = credits_col.find_one(
            {"_id": user_id}
        )

        return (
            data.get("balance", 0)
            if data
            else 0
        )

    except Exception:

        return 0


async def add_credits(
    user_id: int,
    amount: float
) -> float:
    """Add credits (atomic)"""

    if amount <= 0:

        return await get_credits(
            user_id
        )

    try:

        result = credits_col.find_one_and_update(
            {"_id": user_id},
            {
                "$inc": {
                    "balance": amount
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        return (
            result.get("balance", 0)
            if result
            else 0
        )

    except Exception:

        return await get_credits(
            user_id
        )


async def add_credits_atomic(
    user_id: int,
    amount: float
) -> float:
    """Add credits atomically (same as add_credits now)"""

    return await add_credits(
        user_id,
        amount
    )


async def deduct_credit(
    user_id: int,
    amount: float = 1
) -> bool:
    """
    Deduct credits atomically.

    Returns True if deduction succeeded,
    False if insufficient balance.

    Used by /delcredit AND downloader.
    """

    if amount <= 0:
        return False

    try:

        result = credits_col.find_one_and_update(
            {
                "_id": user_id,
                "balance": {
                    "$gte": amount
                }
            },
            {
                "$inc": {
                    "balance": -amount
                }
            },
            return_document=ReturnDocument.AFTER
        )

        return result is not None

    except Exception:

        return False


async def deduct_credit_atomic(
    user_id: int,
    amount: float = 1
) -> bool:
    """Alias for deduct_credit (atomic)"""

    return await deduct_credit(
        user_id,
        amount
    )


async def has_credits(
    user_id: int,
    amount: int = 1
) -> bool:
    """Check if user has enough credits"""

    return (
        await get_credits(user_id)
        >= amount
    )


async def set_credits(
    user_id: int,
    amount: int
) -> int:
    """Set exact credit balance"""

    try:

        credits_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "balance": amount
                }
            },
            upsert=True
        )

        return amount

    except Exception:

        return 0


# ==================== DAILY CLAIM SYSTEM (ATOMIC) ====================

async def get_daily_credit_status(
    user_id: int
) -> dict:
    """Get user's daily credit claim status — resets at 12:00 AM IST"""

    try:

        data = credits_col.find_one(
            {"_id": user_id}
        )

        if not data:

            return {
                "can_claim": True,
                "last_claim": "Never",
                "next_claim": "Now",
                "time_remaining": ""
            }

        last_claim = data.get(
            "last_claim"
        )

        if not last_claim:

            return {
                "can_claim": True,
                "last_claim": "Never",
                "next_claim": "Now",
                "time_remaining": ""
            }

        # Check if last claim was before today's midnight IST
        today_midnight = (
            get_today_midnight_ist()
        )

        if last_claim < today_midnight:

            # Can claim today
            return {
                "can_claim": True,
                "last_claim": format_ist_time(
                    last_claim
                ),
                "next_claim": "Now",
                "time_remaining": "0s"
            }

        else:

            # Already claimed today,
            # next claim at next midnight
            next_midnight = (
                get_next_midnight_ist()
            )

            remaining = (
                next_midnight - time.time()
            )

            return {
                "can_claim": False,
                "last_claim": format_ist_time(
                    last_claim
                ),
                "next_claim": "Tomorrow at 12:00 AM",
                "time_remaining": format_time_remaining(
                    remaining
                )
            }

    except Exception:

        return {
            "can_claim": True,
            "last_claim": "Never",
            "next_claim": "Now",
            "time_remaining": ""
        }


async def claim_daily_credits_atomic(
    user_id: int
) -> dict:
    """
    Claim daily free credits — ATOMIC
    Resets at 12:00 AM IST.
    """

    try:

        now = time.time()

        today_midnight = (
            get_today_midnight_ist()
        )


        # Step 1:
        # Ensure document exists
        credits_col.update_one(
            {"_id": user_id},
            {
                "$setOnInsert": {
                    "balance": 0
                }
            },
            upsert=True
        )


        # Step 2:
        # Atomic claim — only if
        # last_claim < today's midnight
        result = credits_col.find_one_and_update(
            {
                "_id": user_id,
                "$or": [
                    {
                        "last_claim": {
                            "$exists": False
                        }
                    },
                    {
                        "last_claim": {
                            "$lt": today_midnight
                        }
                    }
                ]
            },
            {
                "$inc": {
                    "balance": DAILY_CLAIM_CREDITS
                },
                "$set": {
                    "last_claim": now
                }
            },
            return_document=ReturnDocument.AFTER
        )


        if result:

            return {
                "success": True,
                "balance": result.get(
                    "balance",
                    DAILY_CLAIM_CREDITS
                ),
                "last_claim": "Just now"
            }


        else:

            # Already claimed today
            data = credits_col.find_one(
                {"_id": user_id}
            )

            last_claim = (
                data.get("last_claim")
                if data
                else None
            )

            next_midnight = (
                get_next_midnight_ist()
            )

            remaining = max(
                0,
                next_midnight - now
            )

            return {
                "success": False,
                "balance": (
                    data.get("balance", 0)
                    if data
                    else 0
                ),
                "last_claim": (
                    format_ist_time(last_claim)
                    if last_claim
                    else "Never"
                ),
                "time_remaining": format_time_remaining(
                    remaining
                )
            }


    except Exception as e:

        return {
            "success": False,
            "balance": 0,
            "last_claim": "Error",
            "time_remaining": "",
            "error": str(e)
        }


# ==================== ADMIN COMMANDS ====================

async def addcredit_command(
    client,
    message
):
    """Admin: /addcredit user_id amount"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode="html"
        )

        return


    args = (
        message.command[1:]
        if message.command
        else []
    )


    if len(args) < 2:

        await message.reply_text(
            "❌ <b>Usage:</b>\n"
            "<code>/addcredit user_id amount</code>",
            parse_mode="html"
        )

        return


    try:

        target_id = int(
            args[0]
        )

        amount = int(
            args[1]
        )

    except ValueError:

        await message.reply_text(
            "❌ <b>Invalid user ID or amount!</b>",
            parse_mode="html"
        )

        return


    if amount <= 0:

        await message.reply_text(
            "❌ <b>Amount must be positive!</b>",
            parse_mode="html"
        )

        return


    new_balance = await add_credits_atomic(
        target_id,
        amount
    )


    try:

        await client.send_message(
            chat_id=target_id,
            text=(
                f"✅ <b>+{amount} Credits Added!</b>\n\n"
                f"💰 New Balance: "
                f"<b>{new_balance}</b> credits"
            ),
            parse_mode="html"
        )

    except Exception:

        pass


    await message.reply_text(
        f"✅ <b>Credits Added!</b>\n\n"
        f"👤 User: <code>{target_id}</code>\n"
        f"➕ +{amount}\n"
        f"💰 Balance: <b>{new_balance}</b>",
        parse_mode="html"
    )


async def delcredit_command(
    client,
    message
):
    """Admin: /delcredit user_id amount — ATOMIC deduction"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode="html"
        )

        return


    args = (
        message.command[1:]
        if message.command
        else []
    )


    if len(args) < 2:

        await message.reply_text(
            "❌ <b>Usage:</b>\n"
            "<code>/delcredit user_id amount</code>",
            parse_mode="html"
        )

        return


    try:

        target_id = int(
            args[0]
        )

        amount = int(
            args[1]
        )

    except ValueError:

        await message.reply_text(
            "❌ <b>Invalid user ID or amount!</b>",
            parse_mode="html"
        )

        return


    if amount <= 0:

        await message.reply_text(
            "❌ <b>Amount must be positive!</b>",
            parse_mode="html"
        )

        return


    current_balance = await get_credits(
        target_id
    )


    if current_balance < amount:

        await message.reply_text(
            f"❌ <b>Insufficient credits!</b>\n\n"
            f"💰 Balance: {current_balance}\n"
            f"🔻 Requested: {amount}",
            parse_mode="html"
        )

        return


    # ATOMIC deduction
    success = await deduct_credit(
        target_id,
        amount
    )


    if not success:

        await message.reply_text(
            "❌ <b>Failed to deduct credits!</b>",
            parse_mode="html"
        )

        return


    new_balance = await get_credits(
        target_id
    )


    try:

        await client.send_message(
            chat_id=target_id,
            text=(
                f"❌ <b>-{amount} Credits Removed!</b>\n\n"
                f"💰 New Balance: "
                f"<b>{new_balance}</b> credits"
            ),
            parse_mode="html"
        )

    except Exception:

        pass


    await message.reply_text(
        f"✅ <b>Credits Removed!</b>\n\n"
        f"👤 User: <code>{target_id}</code>\n"
        f"➖ -{amount}\n"
        f"💰 Balance: <b>{new_balance}</b>",
        parse_mode="html"
    )


async def resetcredit_command(
    client,
    message
):
    """Admin: /resetcredit user_id"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode="html"
        )

        return


    args = (
        message.command[1:]
        if message.command
        else []
    )


    if len(args) < 1:

        await message.reply_text(
            "❌ <b>Usage:</b>\n"
            "<code>/resetcredit user_id</code>",
            parse_mode="html"
        )

        return


    try:

        target_id = int(
            args[0]
        )

    except ValueError:

        await message.reply_text(
            "❌ <b>Invalid user ID!</b>",
            parse_mode="html"
        )

        return


    await set_credits(
        target_id,
        0
    )


    try:

        await client.send_message(
            chat_id=target_id,
            text=(
                "🔄 <b>Credits Reset!</b>\n\n"
                "💰 New Balance: <b>0</b> credits"
            ),
            parse_mode="html"
        )

    except Exception:

        pass


    await message.reply_text(
        f"✅ <b>Credits Reset!</b>\n\n"
        f"👤 User: <code>{target_id}</code>\n"
        f"💰 Balance: <b>0</b>",
        parse_mode="html"
    )


async def allcredits_command(
    client,
    message
):
    """Admin: /allcredits — Show top 10 users by credits"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ <b>Admin only!</b>",
            parse_mode="html"
        )

        return


    try:

        total_users = credits_col.count_documents({})


        if total_users == 0:

            await message.reply_text(
                "❌ <b>No users found!</b>",
                parse_mode="html"
            )

            return


        # Top 10 by balance
        top_users = list(
            credits_col.find({})
            .sort("balance", -1)
            .limit(10)
        )


        # Get total credits (aggregation)
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total": {
                        "$sum": "$balance"
                    }
                }
            }
        ]


        agg_result = list(
            credits_col.aggregate(
                pipeline
            )
        )


        total_credits = (
            agg_result[0]["total"]
            if agg_result
            else 0
        )


        avg_credits = (
            total_credits // total_users
            if total_users > 0
            else 0
        )


        # Batch fetch user data
        user_ids = [
            c.get("_id")
            for c in top_users
        ]


        users_data = {
            u["_id"]: u
            for u in users_col.find(
                {
                    "_id": {
                        "$in": user_ids
                    }
                }
            )
        }


        text = (
            "💰 <b>Credit Statistics</b>\n\n"
        )

        text += (
            f"👥 Total Users: "
            f"<b>{total_users}</b>\n"
        )

        text += (
            f"💎 Total Credits: "
            f"<b>{total_credits}</b>\n"
        )

        text += (
            f"📊 Avg Credits: "
            f"<b>{avg_credits}</b>\n\n"
        )

        text += (
            "━━━━━━━━━━━━━━━━━━\n\n"
        )

        text += (
            "<b>🏆 Top 10 Users:</b>\n"
        )


        for i, c in enumerate(
            top_users,
            1
        ):

            user_id = c.get(
                "_id"
            )

            balance = c.get(
                "balance",
                0
            )


            user_data = users_data.get(
                user_id
            )


            if user_data:

                username = (
                    user_data.get("username")
                    or user_data.get(
                        "first_name",
                        "Unknown"
                    )
                )

            else:

                username = "Unknown"


            text += (
                f"{i}. "
                f"<code>{escape_html(username)}</code>"
                f" — <b>{balance}</b> credits\n"
            )


        await message.reply_text(
            text,
            parse_mode="html"
        )


    except Exception as e:

        await message.reply_text(
            f"❌ <b>Error:</b> "
            f"{escape_html(str(e))}",
            parse_mode="html"
        )


# ==================== USER COMMANDS ====================

async def credit_command(
    client,
    message
):
    """User: /credit — Check balance"""

    user_id = message.from_user.id
    chat_id = message.chat.id


    try:

        balance = await get_credits(
            user_id
        )

        daily_status = (
            await get_daily_credit_status(
                user_id
            )
        )


        text = (
            "💰 <b>Credit Balance</b>\n\n"
        )

        text += (
            f"Balance: "
            f"<b>{balance}</b> credits\n\n"
        )


        if daily_status.get(
            "can_claim"
        ):

            text += (
                f"📌 Type "
                f"<code>/claim</code> to get "
                f"<b>{DAILY_CLAIM_CREDITS} "
                f"free credits</b> today!"
            )

        else:

            text += (
                f"📅 Last Claim: "
                f"{daily_status.get('last_claim')}\n"
            )

            text += (
                f"⏳ Next Claim: "
                f"{daily_status.get('next_claim')}\n"
            )

            text += (
                f"🕐 Time Remaining: "
                f"{daily_status.get('time_remaining')}"
            )


        await client.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="html"
        )


    except Exception as e:

        await client.send_message(
            chat_id=chat_id,
            text=(
                f"❌ <b>Error:</b> "
                f"{escape_html(str(e))}"
            ),
            parse_mode="html"
        )


async def claim_command(
    client,
    message
):
    """User: /claim — Claim daily free credits"""

    user_id = message.from_user.id
    chat_id = message.chat.id


    try:

        result = (
            await claim_daily_credits_atomic(
                user_id
            )
        )


        if result["success"]:

            await client.send_message(
                chat_id=chat_id,
                text=(
                    f"✅ <b>+{DAILY_CLAIM_CREDITS} "
                    f"Credits Added!</b>\n\n"
                    f"💰 Total Balance: "
                    f"<b>{result['balance']}</b> credits\n"
                    f"📅 Next Claim: "
                    f"Tomorrow at 12:00 AM"
                ),
                parse_mode="html"
            )

        else:

            await client.send_message(
                chat_id=chat_id,
                text=(
                    "⏰ <b>Already Claimed Today!</b>\n\n"
                    f"💰 Balance: "
                    f"<b>{result.get('balance', 0)}</b> credits\n"
                    f"📅 Last Claimed: "
                    f"{result.get('last_claim', 'Never')}\n"
                    f"⏳ Time Remaining: "
                    f"{result.get('time_remaining', '')}"
                ),
                parse_mode="html"
            )


    except Exception as e:

        await client.send_message(
            chat_id=chat_id,
            text=(
                f"❌ <b>Error:</b> "
                f"{escape_html(str(e))}"
            ),
            parse_mode="html"
        )


# ==================== REGISTER HANDLERS ====================

def register_credit_handlers(app):
    """Register all handlers for credit module"""

    app.add_handler(
        MessageHandler(
            credit_command,
            filters.command("credit")
        )
    )

    app.add_handler(
        MessageHandler(
            claim_command,
            filters.command("claim")
        )
    )

    app.add_handler(
        MessageHandler(
            addcredit_command,
            filters.command("addcredit")
        )
    )

    app.add_handler(
        MessageHandler(
            delcredit_command,
            filters.command("delcredit")
        )
    )

    app.add_handler(
        MessageHandler(
            resetcredit_command,
            filters.command("resetcredit")
        )
    )

    app.add_handler(
        MessageHandler(
            allcredits_command,
            filters.command("allcredits")
        )
    )