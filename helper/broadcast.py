# helper/broadcast.py

import asyncio
import time

from datetime import datetime, timedelta

from pyrogram import filters, enums
from pyrogram.handlers import MessageHandler
from pyrogram.errors import FloodWait, RPCError

from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from helper.database import users_col, broadcast_collection

from config import (
    ADMIN_IDS,
    LOG_CHANNEL_ID
)


# ==================== CONFIG ====================

BROADCAST_DELAY = 0.05  # Delay between messages (seconds)


# ==================== ADMIN CHECK ====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ==================== HELPERS ====================

async def log_to_channel(client, text):
    """Log message to admin log channel"""

    try:
        await client.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=text,
            parse_mode=enums.ParseMode.HTML
        )

    except Exception:
        pass


def chunk_list(lst, chunk_size=100):
    """Split list into chunks"""

    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


# ==================== GET ALL USERS ====================

async def get_all_users():
    """Get all active users from database"""

    try:
        users = list(
            users_col.find(
                {},
                {"_id": 1}
            )
        )

        return [
            u["_id"]
            for u in users
            if u.get("_id")
        ]

    except Exception as e:

        print(
            f"Error fetching users: {e}"
        )

        return []


# ==================== PARSE TIME DURATION ====================

def parse_time_duration(time_str):
    """Parse time string like 12h, 2d, 30m"""

    if not time_str:
        return None

    time_str = time_str.lower().strip()

    if time_str.endswith("h"):

        try:
            hours = int(
                time_str[:-1]
            )

            return timedelta(
                hours=hours
            )

        except Exception:
            return None

    elif time_str.endswith("d"):

        try:
            days = int(
                time_str[:-1]
            )

            return timedelta(
                days=days
            )

        except Exception:
            return None

    elif time_str.endswith("m"):

        try:
            minutes = int(
                time_str[:-1]
            )

            return timedelta(
                minutes=minutes
            )

        except Exception:
            return None

    else:
        return None


# ==================== BROADCAST COMMANDS ====================

async def broadcast_command(client, message):
    """Handle /broadcast command — permanent broadcast"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ Admin only!"
        )

        return

    if not message.reply_to_message:

        await message.reply_text(
            "❌ Reply to a message to broadcast!"
        )

        return

    broadcast_msg = message.reply_to_message

    await perform_broadcast(
        client,
        message,
        broadcast_msg,
        broadcast_type="normal"
    )


async def dbroadcast_command(client, message):
    """Handle /dbroadcast 12h or 2d — delete after time"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ Admin only!"
        )

        return

    if not message.reply_to_message:

        await message.reply_text(
            "❌ Reply to a message to broadcast!"
        )

        return

    # PTB:
    # context.args
    #
    # Pyrogram:
    # message.command[1:]

    args = message.command[1:] if message.command else []

    if not args:

        await message.reply_text(
            "❌ Please specify time!\n"
            "Example: /dbroadcast 12h  or  "
            "/dbroadcast 2d"
        )

        return

    time_str = args[0]

    duration = parse_time_duration(
        time_str
    )

    if not duration:

        await message.reply_text(
            "❌ Invalid time format!\n"
            "Use: 12h, 24h, 2d, 7d"
        )

        return

    broadcast_msg = message.reply_to_message

    await perform_broadcast(
        client,
        message,
        broadcast_msg,
        broadcast_type="delete",
        duration=duration
    )


async def pbroadcast_command(client, message):
    """Handle /pbroadcast 12h or 2d — pin for time"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ Admin only!"
        )

        return

    if not message.reply_to_message:

        await message.reply_text(
            "❌ Reply to a message to broadcast!"
        )

        return

    args = message.command[1:] if message.command else []

    if not args:

        await message.reply_text(
            "❌ Please specify time!\n"
            "Example: /pbroadcast 12h  or  "
            "/pbroadcast 2d"
        )

        return

    time_str = args[0]

    duration = parse_time_duration(
        time_str
    )

    if not duration:

        await message.reply_text(
            "❌ Invalid time format!\n"
            "Use: 12h, 24h, 2d, 7d"
        )

        return

    broadcast_msg = message.reply_to_message

    await perform_broadcast(
        client,
        message,
        broadcast_msg,
        broadcast_type="pin",
        duration=duration
    )


async def pdbroadcast_command(client, message):
    """Handle /pdbroadcast 12h or 2d — pin + delete after time"""

    user = message.from_user

    if not user:
        return

    if not is_admin(user.id):

        await message.reply_text(
            "❌ Admin only!"
        )

        return

    if not message.reply_to_message:

        await message.reply_text(
            "❌ Reply to a message to broadcast!"
        )

        return

    args = message.command[1:] if message.command else []

    if not args:

        await message.reply_text(
            "❌ Please specify time!\n"
            "Example: /pdbroadcast 12h  or  "
            "/pdbroadcast 2d"
        )

        return

    time_str = args[0]

    duration = parse_time_duration(
        time_str
    )

    if not duration:

        await message.reply_text(
            "❌ Invalid time format!\n"
            "Use: 12h, 24h, 2d, 7d"
        )

        return

    broadcast_msg = message.reply_to_message

    await perform_broadcast(
        client,
        message,
        broadcast_msg,
        broadcast_type="pin_delete",
        duration=duration
    )


# ==================== SEND TO ONE USER (helper) ====================

async def send_broadcast_to_user(
    client,
    broadcast_msg,
    user_id,
    broadcast_type,
    duration
):
    """
    Send broadcast to one user with all logic.

    Returns:
    (status, sent_msg)

    status:
    "success" | "blocked" | "deleted" | "failed"
    """

    try:

        # Pyrogram copy
        sent_msg = await broadcast_msg.copy(
            chat_id=user_id
        )


        # ==================== PIN ====================

        if broadcast_type in [
            "pin",
            "pin_delete"
        ]:

            try:

                await client.pin_chat_message(
                    chat_id=user_id,
                    message_id=sent_msg.id,
                    disable_notification=True
                )

            except Exception:
                pass


        # ==================== STORE FOR AUTO DELETE ====================

        if (
            broadcast_type in [
                "delete",
                "pin_delete"
            ]
            and duration
        ):

            broadcast_collection.insert_one({
                "user_id": user_id,
                "message_id": sent_msg.id,
                "delete_after": (
                    datetime.now() + duration
                ),
                "created_at": datetime.now()
            })


        return "success", sent_msg


    # ==================== FLOOD WAIT ====================

    except FloodWait as e:

        await asyncio.sleep(
            e.value
        )

        # Retry once
        try:

            sent_msg = await broadcast_msg.copy(
                chat_id=user_id
            )


            if broadcast_type in [
                "pin",
                "pin_delete"
            ]:

                try:

                    await client.pin_chat_message(
                        chat_id=user_id,
                        message_id=sent_msg.id,
                        disable_notification=True
                    )

                except Exception:
                    pass


            if (
                broadcast_type in [
                    "delete",
                    "pin_delete"
                ]
                and duration
            ):

                broadcast_collection.insert_one({
                    "user_id": user_id,
                    "message_id": sent_msg.id,
                    "delete_after": (
                        datetime.now() + duration
                    ),
                    "created_at": datetime.now()
                })


            return "success", sent_msg


        except Exception:

            return "failed", None


    # ==================== RPC ERRORS ====================

    except RPCError as e:

        err = str(e).lower()


        # User blocked/deactivated/not found
        if (
            "deactivated" in err
            or "invalid" in err
            or "chat not found" in err
            or "user not found" in err
            or "peer id invalid" in err
            or "user is blocked" in err
        ):

            users_col.delete_one({
                "_id": user_id
            })

            if "deactivated" in err:
                return "deleted", None

            if "chat not found" in err:
                return "deleted", None

            if "user not found" in err:
                return "deleted", None

            if "peer id invalid" in err:
                return "deleted", None

            if "user is blocked" in err:
                return "blocked", None

        return "failed", None


    # ==================== OTHER ERRORS ====================

    except Exception:

        return "failed", None


# ==================== PERFORM BROADCAST ====================

async def perform_broadcast(
    client,
    message,
    broadcast_msg,
    broadcast_type="normal",
    duration=None
):
    """Main broadcast function — sends to ALL users"""


    # Get all users
    user_ids = await get_all_users()


    if not user_ids:

        await message.reply_text(
            "❌ No users in database!"
        )

        return


    total_users = len(
        user_ids
    )


    # Processing message
    pls_wait = await message.reply_text(
        "📢 <b>Broadcasting Message..</b>\n\n"
        f"👥 Total Users: "
        f"<code>{total_users}</code>\n"
        "⏳ Starting...",
        parse_mode=enums.ParseMode.HTML
    )


    # ==================== STATS ====================

    total = 0
    successful = 0
    blocked = 0
    deleted = 0
    unsuccessful = 0


    # ==================== BROADCAST TYPE ====================

    type_text = {

        "normal":
            "📢 Normal Broadcast",

        "delete":
            f"🗑 Delete after {duration}",

        "pin":
            f"📌 Pin for {duration}",

        "pin_delete":
            f"📌 Pin + Delete after {duration}"
    }


    # ==================== SEND TO EACH USER ====================

    for user_id in user_ids:

        total += 1


        status, _ = await send_broadcast_to_user(
            client,
            broadcast_msg,
            user_id,
            broadcast_type,
            duration
        )


        if status == "success":

            successful += 1

        elif status == "blocked":

            blocked += 1

        elif status == "deleted":

            deleted += 1

        else:

            unsuccessful += 1


        # ==================== UPDATE PROGRESS ====================

        if total % 10 == 0:

            try:

                await pls_wait.edit_text(
                    f"📢 <b>Broadcasting...</b>\n\n"
                    f"👥 Total: "
                    f"<code>{total}</code> / "
                    f"<code>{total_users}</code>\n"
                    f"✅ Success: "
                    f"<code>{successful}</code>\n"
                    f"🚫 Blocked: "
                    f"<code>{blocked}</code>\n"
                    f"🗑 Deleted: "
                    f"<code>{deleted}</code>\n"
                    f"❌ Failed: "
                    f"<code>{unsuccessful}</code>\n"
                    f"⏳ Progress: "
                    f"<code>"
                    f"{int(total / total_users * 100)}"
                    f"%</code>",
                    parse_mode=enums.ParseMode.HTML
                )

            except Exception:

                pass


        # Small delay to avoid flood
        await asyncio.sleep(
            BROADCAST_DELAY
        )


    # ==================== FINAL STATUS ====================

    status_text = (
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"📢 Type: "
        f"{type_text.get(broadcast_type, 'Normal')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users: "
        f"<code>{total}</code>\n"
        f"✅ Successful: "
        f"<code>{successful}</code>\n"
        f"🚫 Blocked: "
        f"<code>{blocked}</code>\n"
        f"🗑 Deleted: "
        f"<code>{deleted}</code>\n"
        f"❌ Failed: "
        f"<code>{unsuccessful}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Delivery Rate: "
        f"<code>"
        f"{int(successful / total * 100 if total > 0 else 0)}"
        f"%</code>"
    )


    try:

        await pls_wait.edit_text(
            status_text,
            parse_mode=enums.ParseMode.HTML
        )

    except Exception:

        await message.reply_text(
            status_text,
            parse_mode=enums.ParseMode.HTML
        )


    # ==================== LOG TO CHANNEL ====================

    await log_to_channel(
        client,
        f"📢 <b>Broadcast Completed</b>\n\n"
        f"📢 Type: "
        f"{type_text.get(broadcast_type, 'Normal')}\n"
        f"👥 Total: {total}\n"
        f"✅ Success: {successful}\n"
        f"🚫 Blocked: {blocked}\n"
        f"🗑 Deleted: {deleted}\n"
        f"❌ Failed: {unsuccessful}"
    )


# ==================== AUTO DELETE BROADCAST MESSAGES ====================

async def auto_delete_broadcast_messages(client):
    """Auto-delete broadcast messages after expiry"""

    while True:

        try:

            now = datetime.now()


            # Find expired messages
            expired = broadcast_collection.find({
                "delete_after": {
                    "$lte": now
                }
            })


            for item in expired:

                user_id = item.get(
                    "user_id"
                )

                message_id = item.get(
                    "message_id"
                )


                if user_id and message_id:

                    try:

                        await client.delete_messages(
                            chat_id=user_id,
                            message_ids=message_id
                        )

                    except Exception:

                        pass


                # Remove from DB
                broadcast_collection.delete_one({
                    "_id": item["_id"]
                })


        except Exception:
            pass


        # Schedule next check
        await asyncio.sleep(60)


# ==================== START CLEANUP TASK ====================

async def start_broadcast_cleanup(client):
    """
    Start broadcast auto-delete background task.
    """

    await auto_delete_broadcast_messages(
        client
    )


# ==================== REGISTER HANDLERS ====================

def register_broadcast_handlers(app):
    """Register all handlers for broadcast module"""


    # /broadcast
    app.add_handler(
        MessageHandler(
            broadcast_command,
            filters.command("broadcast")
        )
    )


    # /dbroadcast
    app.add_handler(
        MessageHandler(
            dbroadcast_command,
            filters.command("dbroadcast")
        )
    )


    # /pbroadcast
    app.add_handler(
        MessageHandler(
            pbroadcast_command,
            filters.command("pbroadcast")
        )
    )


    # /pdbroadcast
    app.add_handler(
        MessageHandler(
            pdbroadcast_command,
            filters.command("pdbroadcast")
        )
    )