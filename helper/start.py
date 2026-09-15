# helper/start.py

import time
import html
import re

from pyrogram import filters, enums
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.credit import (
    get_credits,
    get_daily_credit_status,
    add_credits
)
from helper.premium import is_premium, get_premium_expiry
from helper.referral import (
    process_referral_atomic,
    get_referral_code,
    get_referral_count
)
from helper.database import users_col
from helper.ads import (
    verify_and_complete_token_atomic,
    AD_TIMER,
    ADS_REWARD
)
from config import (
    DAILY_CLAIM_CREDITS,
    REFERRAL_DOWNLOADS_REQUIRED
)


# ==================== START IMAGES & EFFECTS ====================

START_IMAGES = [
    "https://graph.org/file/9b84ec73a967e27c15de9-d1e9e4da7828acaedc.jpg",
    "https://graph.org/file/bf97d23cc674f784ccc44-4f4954b079b5bef5aa.jpg",
    "https://graph.org/file/7b1b649637df1f6cc93ed-89bc7f67834da7267e.jpg",
    "https://graph.org/file/042fbf6c2c92939d81a0f-83b1e0be26a59e5ff0.jpg",
    "https://graph.org/file/63addfcda854228dd2eb4-f5389cd6bdaa995c6b.jpg",
    "https://graph.org/file/b9f294b8549d8803e2bae-1a97a4394146e77a7b.jpg"
]

START_EFFECTS = [
    "5104841245755180586",
    "5107584321108051014",
    "5104858069142078462",
    "5159385139981059251",
    "5046509860389126442",
    "5046589136895476101"
]


# ==================== HELPERS ====================

def escape_html(text):
    if not text:
        return "Unknown"

    return html.escape(str(text))


# ==================== SEND START MESSAGE ====================

async def send_start_message(
    client,
    chat_id,
    user_id,
    user_first_name,
    user_username=None
):
    """Send start message (used by both command and callback)"""

    try:

        # Save / Update user
        result = users_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "username": user_username,
                    "first_name": user_first_name,
                    "last_active": time.time()
                },
                "$setOnInsert": {
                    "created_at": time.time()
                }
            },
            upsert=True
        )

        # 🎁 New User Start Bonus
        if result.upserted_id is not None:
            await add_credits(
                user_id,
                20
            )

        balance = await get_credits(user_id)

        premium = await is_premium(user_id)

        daily_status = await get_daily_credit_status(user_id)

        credit_reminder = ""

        if (
            daily_status.get("can_claim")
            and balance == 0
        ):
            credit_reminder = (
                f"\n\n💡 <b>You have "
                f"{DAILY_CLAIM_CREDITS} free "
                f"credits waiting!</b>\n"
                f"Type /claim to get them."
            )

        premium_status = (
            "✅ Active"
            if premium
            else "❌ Not Active"
        )

        # Random image
        image_index = (
            int(time.time())
            % len(START_IMAGES)
        )

        image_url = START_IMAGES[
            image_index
        ]

        # Random effect
        #
        # Kept because START_EFFECTS and effect selection
        # are part of the original structure.
        #
        # Pyrogram send_photo() does not expose
        # message_effect_id directly.

        effect_index = (
            int(time.time() * 1000)
            % len(START_EFFECTS)
        )

        effect_id = int(
            START_EFFECTS[effect_index]
        )

        safe_name = escape_html(
            user_first_name
        )

        caption = (
            f"👋 <b>ʜᴇʏ {safe_name}!</b>\n\n"
            "🚀 <b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ sᴏᴄɪᴀʟ ᴍᴇᴅɪᴀ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ</b>\n\n"
            "<blockquote expandable>"
            "📥 <b>ᴡʜᴀᴛ ɪ ᴄᴀɴ ᴅᴏ</b>\n\n"
            "ɪ ᴄᴀɴ ʜᴇʟᴘ ʏᴏᴜ ᴅᴏᴡɴʟᴏᴀᴅ ᴠɪᴅᴇᴏs ᴀɴᴅ ᴍᴇᴅɪᴀ "
            "ғʀᴏᴍ ᴍᴜʟᴛɪᴘʟᴇ ᴘʟᴀᴛғᴏʀᴍs.\n\n"
            "◎ <b>ɪɴsᴛᴀɢʀᴀᴍ</b>\n"
            "ⓕ <b>ғᴀᴄᴇʙᴏᴏᴋ</b>\n"
            "▶ <b>ʏᴏᴜᴛᴜʙᴇ</b>\n"
            "◈ <b>ᴛᴇʀᴀʙᴏx</b>\n"
            "🎵 <b>ᴛɪᴋᴛᴏᴋ</b>\n"
            "𝕏 <b>ᴛᴡɪᴛᴛᴇʀ / 𝕏</b>\n"
            "℘ <b>ᴘɪɴᴛᴇʀᴇsᴛ</b>\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>Balance:</b> "
            f"{balance} credits\n"
            f"👑 <b>Premium:</b> "
            f"{premium_status}\n"
            f"{credit_reminder}\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "</blockquote>"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "ʜᴏᴡ ᴛᴏ ᴜꜱᴇ",
                        callback_data="help"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "👤 ᴘʀᴏꜰɪʟᴇ",
                        callback_data="profile"
                    ),
                    InlineKeyboardButton(
                        "👑 ᴘʀᴇᴍɪᴜᴍ",
                        callback_data="premium"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "👥 ʀᴇꜰᴇʀ & ᴇᴀʀɴ",
                        callback_data="refer"
                    ),
                    InlineKeyboardButton(
                        "📺 ᴡᴀᴛᴄʜ & ᴇᴀʀɴ",
                        callback_data="watch_earn"
                    )
                ]
            ]
        )

        await client.send_photo(
            chat_id=chat_id,
            photo=image_url,
            caption=caption,
            message_effect_id=effect_id,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:

        print(
            f"❌ send_start_message error: {e}"
        )

        try:
            await client.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ Error: "
                    f"{escape_html(str(e))}"
                )
            )
        except Exception as send_error:
            print(
                f"❌ Error message send failed: "
                f"{send_error}"
            )


# ==================== START COMMAND ====================

async def start_command(
    client,
    message
):
    """Handle /start command"""

    print("🔥 START COMMAND RECEIVED")

    try:

        user = message.from_user

        if not user:
            return

        user_id = user.id

        chat_id = message.chat.id

        text = message.text or ""

        # ========== CHECK REFERRAL ==========

        ref_match = re.match(
            r'^/start(?:@\w+)?\s+ref_(.+)$',
            text
        )

        if ref_match:

            ref_code = (
                ref_match.group(1).strip()
            )

            if ref_code:

                result = await process_referral_atomic(
                    user_id,
                    ref_code
                )

                if result.get("success"):

                    try:

                        await client.send_message(
                            chat_id=result["referrer_id"],
                            text=(
                                f"👥 <b>New Referral!</b>\n\n"
                                f"Someone used your referral link!\n"
                                f"📌 They need <b>"
                                f"{REFERRAL_DOWNLOADS_REQUIRED} "
                                f"downloads</b> to unlock "
                                f"your reward!"
                            ),
                            parse_mode=enums.ParseMode.HTML
                        )

                    except Exception:
                        pass

                    await client.send_message(
                        chat_id=chat_id,
                        text=(
                            "🎉 <b>Welcome!</b>\n\n"
                            "You were referred by someone!\n"
                            f"📌 Complete <b>"
                            f"{REFERRAL_DOWNLOADS_REQUIRED} "
                            f"downloads</b> to unlock "
                            f"their referral reward!"
                        ),
                        parse_mode=enums.ParseMode.HTML
                    )

        # ========== CHECK AD TOKEN ==========

        ad_match = re.match(
            r'^/start(?:@\w+)?\s+ad_(.+)$',
            text
        )

        if ad_match:

            token = (
                ad_match.group(1).strip()
            )

            if token:

                result = await verify_and_complete_token_atomic(
                    user_id,
                    token
                )

                if result["success"]:

                    await client.send_message(
                        chat_id=chat_id,
                        text=(
                            f"✅ <b>Ad Completed!</b>\n\n"
                            f"💰 <b>+"
                            f"{result['credits_added']} "
                            f"credits</b>\n"
                            f"💳 <b>New Balance:</b> "
                            f"{result.get('new_balance', 0)} "
                            f"credits\n\n"
                            f"📌 Thanks for watching!"
                        ),
                        parse_mode=enums.ParseMode.HTML
                    )

                    return

                if result.get("bypassed"):

                    keyboard = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🔁 Try Again",
                                    callback_data="watch_now"
                                )
                            ]
                        ]
                    )

                    await client.send_message(
                        chat_id=chat_id,
                        text=(
                            f"❌ <b>Bypass Detected!</b>\n\n"
                            f"⚠️ You clicked the link before "
                            f"<b>{AD_TIMER} seconds</b>.\n"
                            f"⏱️ Please wait "
                            f"{AD_TIMER} seconds before "
                            f"clicking the link.\n\n"
                            f"🔁 Try again:"
                        ),
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=keyboard
                    )

                    return

                await client.send_message(
                    chat_id=chat_id,
                    text=(
                        f"❌ <b>{result['message']}</b>\n\n"
                        f"💡 Type /earn to try again."
                    ),
                    parse_mode=enums.ParseMode.HTML
                )

                return

        # ========== NORMAL START ==========

        await send_start_message(
            client,
            chat_id,
            user_id,
            user.first_name,
            user.username
        )

    except Exception as e:

        print(
            f"❌ start_command error: {e}"
        )

        try:

            await client.send_message(
                chat_id=message.chat.id,
                text=(
                    f"❌ Error: "
                    f"{escape_html(str(e))}"
                )
            )

        except Exception as send_error:

            print(
                f"❌ Could not send start error: "
                f"{send_error}"
            )

# ==================== HELP CALLBACK ====================

async def help_callback(
    client,
    callback_query
):
    """Handle Help button callback"""

    query = callback_query

    await query.answer()

    help_text = (
        "📖 <b>ʜᴏᴡ ᴛᴏ ᴜsᴇ</b>\n\n"
        "<blockquote>① ᴄᴏᴘʏ ᴛʜᴇ ᴠɪᴅᴇᴏ ᴏʀ ᴘᴏsᴛ ʟɪɴᴋ.\n"
        "② sᴇɴᴅ ᴛʜᴇ ʟɪɴᴋ ᴛᴏ ᴍᴇ.\n"
        "③ ᴡᴀɪᴛ ᴡʜɪʟᴇ ɪ ᴘʀᴏᴄᴇss ɪᴛ.\n"
        "④ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇ ʀɪɢʜᴛ ʜᴇʀᴇ. ✨\n\n"
        "💡 <b>ʏᴏᴜᴛᴜʙᴇ</b>\n"
        "ᴜsᴇ: sᴇɴᴅ URL\n"
        "ᴄʜᴏᴏsᴇ ᴠɪᴅᴇᴏ ǫᴜᴀʟɪᴛʏ ᴏʀ ᴀᴜᴅɪᴏ ғᴏʀᴍᴀᴛ.\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "💬 <b>sᴜᴘᴘᴏʀᴛ</b>\n"
        "ɴᴇᴇᴅ ʜᴇʟᴘ? ᴄᴏɴᴛᴀᴄᴛ: @cinevines_bot\n\n"
        "⚡ <b>ғᴀsᴛ • sɪᴍᴘʟᴇ • ᴇᴀsʏ</b></blockquote>"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back_to_start"
                )
            ]
        ]
    )

    try:

        await query.message.edit_caption(
            caption=help_text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:

        print(
            f"❌ help_callback error: {e}"
        )

# ==================== PROFILE CALLBACK ====================

async def profile_callback(
    client,
    callback_query
):
    """Handle Profile button callback"""

    query = callback_query

    await query.answer()

    user_id = query.from_user.id

    user = query.from_user

    balance = await get_credits(
        user_id
    )

    premium = await is_premium(
        user_id
    )

    daily_status = await get_daily_credit_status(
        user_id
    )

    referral_count = await get_referral_count(
        user_id
    )

    referral_code = await get_referral_code(
        user_id
    )

    user_data = users_col.find_one({
        "_id": user_id
    })

    premium_text = "❌ Not Active"

    if premium:

        expiry = await get_premium_expiry(
            user_id
        )

        if expiry:

            remaining = int(
                (expiry - time.time())
                / 86400
            )

            premium_text = (
                f"✅ Active "
                f"({remaining} days left)"
            )

    next_claim = daily_status.get(
        "next_claim",
        "Tomorrow"
    )

    last_claim = daily_status.get(
        "last_claim",
        "Never"
    )

    bot_username = client.me.username

    safe_name = escape_html(
        user.first_name
    )

    safe_username = (
        escape_html(user.username)
        if user.username
        else "N/A"
    )

    profile_text = (
        f"👤 <b>ᴜꜱᴇʀ ᴘʀᴏꜰɪʟᴇ</b>\n\n"
        f"<blockquote>"
        f"🆔 <b>ɪᴅ:</b> "
        f"<code>{user_id}</code>\n"
        f"📛 <b>ɴᴀᴍᴇ:</b> "
        f"{safe_name}\n"
        f"👤 <b>ᴜꜱᴇʀɴᴀᴍᴇ:</b> "
        f"@{safe_username}\n"
        f"📅 <b>ᴊᴏɪɴᴇᴅ:</b> "
        f"{time.strftime('%d %b %Y', time.localtime(user_data.get('created_at', time.time()))) if user_data else 'N/A'}"
        f"</blockquote>\n"
        f"<blockquote>"
        f"💰 <b>ᴄʀᴇᴅɪᴛꜱ:</b> "
        f"{balance}\n"
        f"👑 <b>ᴘʀᴇᴍɪᴜᴍ:</b> "
        f"{premium_text}\n"
        f"👥 <b>ʀᴇꜰᴇʀʀᴀʟꜱ:</b> "
        f"{referral_count}\n"
        f"🔗 <b>ʀᴇꜰᴇʀʀᴀʟ ʟɪɴᴋ:</b>\n"
        f"<code>https://t.me/{bot_username}"
        f"?start=ref_{referral_code}</code>"
        f"</blockquote>\n"
        f"<blockquote>"
        f"📅 <b>ʟᴀꜱᴛ ᴄʟᴀɪᴍ:</b> "
        f"{last_claim}\n"
        f"⏳ <b>ɴᴇxᴛ ᴄʟᴀɪᴍ:</b> "
        f"{next_claim}"
        f"</blockquote>"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back_to_start"
                )
            ]
        ]
    )

    try:

        await query.message.edit_caption(
            caption=profile_text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:

        print(
            f"❌ profile_callback error: {e}"
        )


# ==================== BACK TO START ====================

async def back_to_start_callback(
    client,
    callback_query
):
    """Handle Back button callback"""

    query = callback_query

    await query.answer()

    user_id = query.from_user.id

    chat_id = query.message.chat.id

    user = query.from_user

    try:

        await client.delete_messages(
            chat_id=chat_id,
            message_ids=query.message.id
        )

    except Exception:

        pass

    await send_start_message(
        client,
        chat_id,
        user_id,
        user.first_name,
        user.username
    )


# ==================== REGISTER HANDLERS ====================

def register_start_handlers(app):
    """Register all handlers for start module"""

    app.add_handler(
        MessageHandler(
            start_command,
            filters.command("start")
        )
    )
    
    
    app.add_handler(
        CallbackQueryHandler(
            help_callback,
            filters.regex(r"^help$")
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            profile_callback,
            filters.regex(r"^profile$")
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            back_to_start_callback,
            filters.regex(r"^back_to_start$")
        )
    )

    print("✅ Start handlers registered")