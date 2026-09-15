# helper/fsub.py

import time
import html
from datetime import datetime, timezone, timedelta

from pyrogram import filters, enums
from pyrogram.handlers import (
    MessageHandler,
    CallbackQueryHandler,
)
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from helper.database import (
    fsub_collection,
    join_requests_collection,
    channel_users_collection,
    pending_checks_collection,
)

from config import ADMIN_IDS


# ==================== TEMP USER DATA ====================
# PTB context.user_data ka Pyrogram replacement.
# User ID -> current FSUB admin action

fsub_action_data = {}


# ==================== ADMIN CHECK ====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def escape_html(text):
    if not text:
        return "Unknown"

    return html.escape(str(text))


# ==================== FSUB CHANNEL HELPERS ====================

def get_fsub_channels():
    return list(
        fsub_collection.find({})
    )


def get_fsub_channel(channel_id):
    return fsub_collection.find_one(
        {
            "channel_id": channel_id
        }
    )


async def create_fsub_link(
    client,
    channel_id,
    request=False,
    timer=0
):
    """Create invite link for channel with optional expiry timer"""

    try:

        kwargs = {
            "chat_id": channel_id,
            "member_limit": 1,
        }

        if request:
            kwargs["creates_join_request"] = True

        if timer > 0:
            kwargs["expire_date"] = (
                datetime.now(timezone.utc)
                + timedelta(minutes=timer)
            )

        link = await client.create_chat_invite_link(
            **kwargs
        )

        return link.invite_link

    except Exception:

        return None


async def is_subscribed(
    client,
    user_id,
    channel_id
):
    """Check if user is subscribed to a channel"""

    try:

        member = await client.get_chat_member(
            chat_id=channel_id,
            user_id=user_id
        )

        return member.status in [
            enums.ChatMemberStatus.MEMBER,
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
        ]

    except Exception:

        return False


async def check_all_fsub(
    client,
    user_id
):
    """Check if user is subscribed to all FSUB channels"""

    channels = get_fsub_channels()

    failed_channels = []

    for channel in channels:

        channel_id = channel["channel_id"]

        if not await is_subscribed(
            client,
            user_id,
            channel_id
        ):
            failed_channels.append(
                channel
            )

    return failed_channels


# ==================== BUILD FSUB MESSAGE ====================

async def build_fsub_message(
    client,
    user_id
):
    """Build force subscribe message and keyboard"""

    failed_channels = await check_all_fsub(
        client,
        user_id
    )

    if not failed_channels:
        return None, None

    text = (
        "⚠️ <b>Force Subscription Required!</b>\n\n"
        "You need to join the following channel(s) "
        "to use this bot:\n\n"
    )

    keyboard = []

    for channel in failed_channels:

        channel_id = channel["channel_id"]

        name = escape_html(
            channel.get(
                "name",
                str(channel_id)
            )
        )

        invite_link = channel.get(
            "invite_link",
            ""
        )

        text += (
            f"📌 <b>{name}</b>\n"
            f"🔗 <a href='{html.escape(invite_link)}'>"
            f"Join Channel</a>\n\n"
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📢 Join {name}",
                    url=invite_link
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "✅ Verified",
                callback_data="check_fsub"
            )
        ]
    )

    return (
        text,
        InlineKeyboardMarkup(keyboard)
    )


# ==================== FSUB COMMANDS ====================

async def fsub_command(
    client,
    message
):
    """Admin command to manage FSUB"""

    if not message.from_user:
        return

    if not is_admin(
        message.from_user.id
    ):

        await message.reply_text(
            "❌ <b>You are not authorized.</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return

    await show_fsub_panel(
        message,
        client
    )


async def show_fsub_panel(
    message,
    client
):
    """Show FSUB admin panel"""

    channels = get_fsub_channels()

    if channels:

        channel_list = []

        for channel in channels:

            channel_id = channel["channel_id"]

            name = escape_html(
                channel.get(
                    "name",
                    str(channel_id)
                )
            )

            request = channel.get(
                "request",
                False
            )

            timer = channel.get(
                "timer",
                0
            )

            request_status = (
                "Request: ✅"
                if request
                else
                "Request: ❌"
            )

            timer_status = (
                f"Timer: {timer}m"
                if timer > 0
                else
                "Timer: ∞"
            )

            channel_list.append(
                f"• <code>{name}</code> "
                f"(<code>{channel_id}</code>)\n"
                f"  {request_status} | {timer_status}"
            )

        channels_display = "\n".join(
            channel_list
        )

    else:

        channels_display = (
            "<i>No force subscription "
            "channels configured.</i>"
        )

    text = (
        "<blockquote><b>Force Subscription Settings</b></blockquote>\n\n"
        "<b>Configured Channels:</b>\n"
        f"{channels_display}\n\n"
        "Use the buttons below to add or remove "
        "a force subscription channel."
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ",
                    callback_data="add_fsub"
                ),
                InlineKeyboardButton(
                    "ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ",
                    callback_data="rm_fsub"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back_to_start"
                )
            ]
        ]
    )

    await message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.HTML
    )


# ==================== ADD FSUB ====================

async def add_fsub_callback(
    client,
    callback_query
):
    """Add FSUB channel callback"""

    try:
        await callback_query.answer()
    except Exception:
        pass

    if not is_admin(
        callback_query.from_user.id
    ):
        return

    user_id = callback_query.from_user.id

    fsub_action_data[user_id] = "add"

    await callback_query.message.reply_text(
        "Send channel details in this format:\n\n"
        "<code>-100123456789 yes 5</code>\n\n"
        "Meaning:\n"
        "• Channel ID = -100123456789\n"
        "• Request = yes/no\n"
        "• Timer = minutes\n\n"
        "Timer 0 = no expiry.\n\n"
        "You have 60 seconds.",
        parse_mode=enums.ParseMode.HTML
    )


async def remove_fsub_callback(
    client,
    callback_query
):
    """Remove FSUB channel callback"""

    try:
        await callback_query.answer()
    except Exception:
        pass

    if not is_admin(
        callback_query.from_user.id
    ):
        return

    user_id = callback_query.from_user.id

    fsub_action_data[user_id] = "remove"

    await callback_query.message.reply_text(
        "Send the channel ID to remove.\n\n"
        "Example:\n"
        "<code>-100123456789</code>\n\n"
        "You have 60 seconds.",
        parse_mode=enums.ParseMode.HTML
    )


# ==================== FSUB MESSAGE HANDLER (COMBINED) ====================

async def fsub_message_handler(
    client,
    message
):
    """
    Combined handler for both add and remove FSUB.

    Checks fsub_action_data[user_id] and routes accordingly.

    IMPORTANT:
    If the admin has no pending FSUB action, this handler
    silently returns so normal text/URL messages are not
    affected.
    """

    if not message.from_user:
        return

    # ========================================================
    # ADMIN CHECK
    # ========================================================

    if not is_admin(
        message.from_user.id
    ):
        return

    user_id = message.from_user.id

    # ========================================================
    # CHECK PENDING ACTION
    # ========================================================

    action = fsub_action_data.get(
        user_id
    )

    # No pending add/remove action.
    # Do absolutely nothing.
    if not action:
        return

    text = message.text or ""

    # ========================================================
    # ADD
    # ========================================================

    if action == "add":

        try:

            parts = text.split()

            if len(parts) != 3:

                await message.reply_text(
                    "❌ Invalid format.\n\n"
                    "Use:\n"
                    "<code>-100123456789 yes 5</code>",
                    parse_mode=enums.ParseMode.HTML
                )

                return

            channel_id = int(
                parts[0]
            )

            request_value = (
                parts[1].lower()
            )

            timer = int(
                parts[2]
            )

            if request_value in (
                "true",
                "on",
                "yes"
            ):

                request = True

            elif request_value in (
                "false",
                "off",
                "no"
            ):

                request = False

            else:

                await message.reply_text(
                    "❌ Request value must be "
                    "yes/no/true/false."
                )

                return

            if timer < 0:

                await message.reply_text(
                    "❌ Timer cannot be negative."
                )

                return

            if get_fsub_channel(
                channel_id
            ):

                await message.reply_text(
                    "❌ This channel ID already exists "
                    "in force subscription list."
                )

                fsub_action_data.pop(
                    user_id,
                    None
                )

                return

            # ====================================================
            # CHECK BOT IS ADMIN
            # ====================================================

            try:

                bot_member = (
                    await client.get_chat_member(
                        chat_id=channel_id,
                        user_id=client.me.id
                    )
                )

                if bot_member.status not in (
                    enums.ChatMemberStatus.ADMINISTRATOR,
                    enums.ChatMemberStatus.OWNER,
                ):

                    await message.reply_text(
                        "❌ Bot is not admin in this channel."
                    )

                    fsub_action_data.pop(
                        user_id,
                        None
                    )

                    return

            except Exception as e:

                await message.reply_text(
                    "❌ Cannot access channel:\n"
                    f"<code>{escape_html(str(e))}</code>",
                    parse_mode=enums.ParseMode.HTML
                )

                fsub_action_data.pop(
                    user_id,
                    None
                )

                return

            # ====================================================
            # GET CHANNEL
            # ====================================================

            chat = await client.get_chat(
                channel_id
            )

            name = (
                chat.title
                or str(channel_id)
            )

            # ====================================================
            # CREATE INVITE LINK
            # ====================================================

            invite_link = await create_fsub_link(
                client,
                channel_id,
                request,
                timer
            )

            if not invite_link:

                await message.reply_text(
                    "❌ Could not create invite link."
                )

                fsub_action_data.pop(
                    user_id,
                    None
                )

                return

            # ====================================================
            # SAVE CHANNEL
            # ====================================================

            fsub_collection.insert_one(
                {
                    "channel_id": channel_id,
                    "name": name,
                    "invite_link": invite_link,
                    "request": request,
                    "timer": timer,
                    "created_at": datetime.now(
                        timezone.utc
                    ),
                }
            )

            fsub_action_data.pop(
                user_id,
                None
            )

            await message.reply_text(
                f"✅ <b>Channel Added!</b>\n\n"
                f"Name: <code>{escape_html(name)}</code>\n"
                f"ID: <code>{channel_id}</code>\n"
                f"Request: <code>{request}</code>\n"
                f"Timer: <code>{timer}</code> minutes",
                parse_mode=enums.ParseMode.HTML
            )

        except ValueError:

            await message.reply_text(
                "❌ Channel ID and timer "
                "must be integers."
            )

        except Exception as e:

            await message.reply_text(
                "❌ Error:\n"
                f"<code>{escape_html(str(e))}</code>",
                parse_mode=enums.ParseMode.HTML
            )

        return

    # ========================================================
    # REMOVE
    # ========================================================

    if action == "remove":

        try:

            channel_id = int(
                text.strip()
            )

            channel = get_fsub_channel(
                channel_id
            )

            if not channel:

                await message.reply_text(
                    "❌ This channel ID is not in "
                    "force subscription list."
                )

                fsub_action_data.pop(
                    user_id,
                    None
                )

                return

            fsub_collection.delete_one(
                {
                    "channel_id": channel_id
                }
            )

            join_requests_collection.delete_many(
                {
                    "channel_id": channel_id
                }
            )

            channel_users_collection.delete_many(
                {
                    "channel_id": channel_id
                }
            )

            pending_checks_collection.delete_many(
                {
                    "channel_id": channel_id
                }
            )

            fsub_action_data.pop(
                user_id,
                None
            )

            await message.reply_text(
                f"✅ Channel removed.\n\n"
                f"ID: <code>{channel_id}</code>",
                parse_mode=enums.ParseMode.HTML
            )

        except ValueError:

            await message.reply_text(
                "❌ Invalid channel ID."
            )

        except Exception as e:

            await message.reply_text(
                "❌ Error:\n"
                f"<code>{escape_html(str(e))}</code>",
                parse_mode=enums.ParseMode.HTML
            )

        return


# ==================== CHECK FSUB ====================

async def check_fsub_callback(
    client,
    callback_query
):
    """Check FSUB verification callback"""

    user_id = callback_query.from_user.id

    text, keyboard = await build_fsub_message(
        client,
        user_id
    )

    if text:

        await callback_query.answer(
            "❌ Please join the channel first!",
            show_alert=True
        )

        return

    await callback_query.answer(
        "✅ Verified!",
        show_alert=True
    )

    try:

        await callback_query.message.edit_text(
            "✅ <b>Subscription Verified!</b>\n\n"
            "You can now use the bot.",
            parse_mode=enums.ParseMode.HTML,
        )

    except Exception:

        pass

    # Delete pending checks if any
    pending_checks_collection.delete_one(
        {
            "user_id": user_id
        }
    )


# ==================== REGISTER HANDLERS ====================

def register_fsub_handlers(app):
    """Register all handlers for fsub module"""

    # --------------------------------------------------------
    # /fsub command
    # --------------------------------------------------------

    app.add_handler(
        MessageHandler(
            fsub_command,
            filters.command("fsub")
        )
    )

    # --------------------------------------------------------
    # Add FSUB callback
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            add_fsub_callback,
            filters.regex(r"^add_fsub$")
        )
    )

    # --------------------------------------------------------
    # Remove FSUB callback
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            remove_fsub_callback,
            filters.regex(r"^rm_fsub$")
        )
    )

    # --------------------------------------------------------
    # Check FSUB callback
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            check_fsub_callback,
            filters.regex(r"^check_fsub$")
        )
    )

    # --------------------------------------------------------
    # Pending add/remove text handler
    # --------------------------------------------------------

    app.add_handler(
        MessageHandler(
            fsub_message_handler,
            filters.text),
        group=1
    )