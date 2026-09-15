import re
import time

from pyrogram import enums

from helper.fsub import (
    check_all_fsub,
    build_fsub_message
)

from helper.premium import is_premium

from helper.credit import (
    has_credits,
    get_credits,
    get_daily_credit_status,
    claim_daily_credits_atomic,
    credit_command as credit_cmd_from_credit,
    claim_command as claim_cmd_from_credit,
)

from helper.downloader import download_and_send

from config import (
    LOG_CHANNEL_ID,
    DAILY_CLAIM_CREDITS
)


# ==================== LOG CHANNEL ====================

async def log_to_channel(
    client,
    user_id,
    username,
    action,
    details=""
):
    """Send log to channel"""

    try:

        user_mention = (
            f"<a href='tg://user?id={user_id}'>"
            f"{username or 'User'}"
            f"</a>"
        )

        log_text = (
            f"📋 <b>Manager Log</b>\n\n"
            f"👤 <b>User:</b> {user_mention}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📌 <b>Action:</b> {action}\n"
            f"{details}"
        )

        await client.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=log_text,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception:
        pass


# ==================== URL EXTRACTOR ====================

def extract_url(text: str) -> str:
    """Extract first valid URL from text"""

    if not text:
        return None

    url_pattern = r'(https?://[^\s]+)'

    match = re.search(
        url_pattern,
        text
    )

    if match:
        return match.group(1)

    return None


# ==================== MAIN URL HANDLER ====================

async def handle_url(
    client,
    message
):
    """
    Main handler for any URL sent by user.

    Flow:
    1. Extract URL
    2. Show processing message
    3. FSUB check
    4. Premium check
    5. Credit check (non-premium only)
    6. Call downloader
       (credit deduction happens inside downloader on success)
    7. Handle success/fail
    """

    if not message.from_user:
        return

    user = message.from_user

    user_id = user.id

    chat_id = message.chat.id

    username = (
        user.username
        or user.first_name
        or "Unknown"
    )

    text = message.text or ""


    # ========== EXTRACT URL ==========

    url = extract_url(text)

    if not url:
        return


    # ========== SHOW PROCESSING MESSAGE ==========

    try:

        processing_msg = await client.send_message(
            chat_id=chat_id,
            text="🔄 <b>Processing your request...</b>",
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:

        # Do not silently hide the actual error.
        # This is especially useful for Python 3.14 +
        # Pyrogram parse-mode compatibility issues.
        print(
            f"❌ Manager processing message error: "
            f"{type(e).__name__}: {e}"
        )

        return

    proc_msg_id = processing_msg.id


    # ========== 1. FORCE SUBSCRIBE CHECK ==========

    failed_channels = await check_all_fsub(
        client,
        user_id
    )

    if failed_channels:

        fsub_text, fsub_keyboard = (
            await build_fsub_message(
                client,
                user_id
            )
        )

        if fsub_text:

            try:

                await client.edit_message_text(
                    chat_id=chat_id,
                    message_id=proc_msg_id,
                    text=fsub_text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=fsub_keyboard,
                    disable_web_page_preview=True
                )

            except Exception:

                pass

            await log_to_channel(
                client,
                user_id,
                username,
                "❌ FSUB Blocked",
                (
                    f"\n📌 <b>Reason:</b> "
                    f"User not subscribed to "
                    f"{len(failed_channels)} channel(s)"
                )
            )

            return


    # ========== 2. PREMIUM CHECK ==========

    premium = await is_premium(
        user_id
    )

    if premium:

        await log_to_channel(
            client,
            user_id,
            username,
            "👑 Premium User",
            (
                f"\n🔗 <b>URL:</b> "
                f"<code>{url[:100]}"
                f"{'...' if len(url) > 100 else ''}"
                f"</code>"
            )
        )


    # ========== 3. CREDIT CHECK (non-premium only) ==========

    if not premium:

        has_enough = await has_credits(
            user_id,
            1
        )

        if not has_enough:

            daily_status = (
                await get_daily_credit_status(
                    user_id
                )
            )

            reminder_text = ""

            if daily_status.get(
                "can_claim"
            ):

                reminder_text = (
                    f"\n\n💡 <b>You have "
                    f"{DAILY_CLAIM_CREDITS} free "
                    f"credits waiting!</b>\n"
                    f"Type /claim to get them."
                )

            try:

                await client.edit_message_text(
                    chat_id=chat_id,
                    message_id=proc_msg_id,
                    text=(
                        f"❌ <b>Insufficient Credits!</b>\n\n"
                        f"💰 Balance: 0 credits"
                        f"{reminder_text}\n\n"
                        f"📺 Watch ads: /earn\n"
                        f"👥 Refer & earn: /refer\n"
                        f"💳 Buy credits: Contact admin"
                    ),
                    parse_mode=enums.ParseMode.HTML
                )

            except Exception:

                pass

            await log_to_channel(
                client,
                user_id,
                username,
                "❌ Insufficient Credits",
                "\n💰 <b>Balance:</b> 0 credits"
            )

            return


        # ========== LOG CREDIT CHECK PASSED ==========

        balance = await get_credits(
            user_id
        )

        await log_to_channel(
            client,
            user_id,
            username,
            "✅ Credit Check Passed",
            (
                f"\n💰 <b>Balance:</b> "
                f"{balance} credits\n"
                f"🔗 <b>URL:</b> "
                f"<code>{url[:100]}"
                f"{'...' if len(url) > 100 else ''}"
                f"</code>"
            )
        )


    # ========== 4. ALL CHECKS PASSED → DOWNLOADER ==========

    # NOTE:
    # Credit deduction happens in downloader.py
    # ONLY after successful upload.

    try:

        await client.edit_message_text(
            chat_id=chat_id,
            message_id=proc_msg_id,
            text=(
                "✅ <b>All checks passed!</b>\n\n"
                "📥 Fetching your video..."
            ),
            parse_mode=enums.ParseMode.HTML
        )

    except Exception:

        pass


    # ========== CALL DOWNLOADER ==========

    success = await download_and_send(
        client,
        message,
        url,
        premium
    )


    if success:

        # Delete processing message
        # Downloader normally deletes its own
        try:

            await client.delete_messages(
                chat_id=chat_id,
                message_ids=proc_msg_id
            )

        except Exception:

            pass

    else:

        # ========== DOWNLOAD FAILED ==========

        try:

            await client.edit_message_text(
                chat_id=chat_id,
                message_id=proc_msg_id,
                text=(
                    "❌ <b>Download failed!</b>\n\n"
                    "Please try again later."
                ),
                parse_mode=enums.ParseMode.HTML
            )

        except Exception:

            pass


        await log_to_channel(
            client,
            user_id,
            username,
            "❌ Download Failed",
            (
                f"\n🔗 <b>URL:</b> "
                f"<code>{url[:100]}"
                f"{'...' if len(url) > 100 else ''}"
                f"</code>"
            )
        )


# ==================== COMMAND WRAPPERS ====================

async def claim_command(
    client,
    message
):
    """Wrapper — calls actual /claim from credit.py"""

    await claim_cmd_from_credit(
        client,
        message
    )


async def credit_command(
    client,
    message
):
    """Wrapper — calls actual /credit from credit.py"""

    await credit_cmd_from_credit(
        client,
        message
    )