# helper/downloader.py

import os
import time
import json
import requests
import asyncio
import aiohttp
import aiofiles
import html
import traceback
try:
    from bot import TEMP_DOWNLOAD_DIR, THUMBNAIL_DIR
except ImportError:
    TEMP_DOWNLOAD_DIR = "temp_downloads"
    THUMBNAIL_DIR = "thumbnails"
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
from urllib.parse import urlencode, quote
from pymongo import ReturnDocument

from pyrogram import filters, enums
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from helper.database import stats_col, credits_col
from helper.credit import deduct_credit_atomic
from helper.referral import check_and_reward_referrals
from config import LOG_CHANNEL_ID, CREDIT_COSTS


# ============================================================
# CONFIG
# ============================================================

FASTSAVER_API_KEYS = [
    # Apni existing FastSaver API key yahan rakho
    "fs_sk_1j6c7z4s9x8q2b2o9j8h4a4b0e1t",
    "fs_sk_0g6e6i4n9p5x6w0n3x6r4v0t3w2r",
    "fs_sk_7a1i9z2a6y5l2n5o4n1g6a2g9r5f",
]

YOINKU_API_KEYS = [
    # Apni existing Yoinku API key yahan rakho
    "yk_sYoChbQYRZXnXKDMxukeavqdGnsPdhYgJaVSFZkwIxgHSSbVikIWPJndAkxfJwXE",
    "yk_RbWjYeHhVQZTBYnDbGRKmboAzuBCVTpXZFUvOrFXiTutRIQODkOJGycRNEwCGsDT",
    "yk_TnzhYLAhHVuORtKWIpQaIgsvxoaxnniMGfaoKmYiPZJhydpFdGBvlVgXKjKSIzsb",
]

TERABOX_API_KEYS = [
    # Apni existing TeraBox API key yahan rakho
    "xapi_3cdb20c3db47abb5ac68deab51ba9b27",
    "pk_btyy0sy724jp23yjm28gk",
    "pk_1bjkrvzo3cfxabid36mh4j",
    "pk_v1dvx9943oilv11cqwvef",
]

INSTAGRAM_API_URLS = [
    # Apni existing Instagram API URL yahan rakho
    "https://7kpgrnvomroojzq6fw5e6qkogq0zyiuv.lambda-url.eu-north-1.on.aws/api/instagram/fetch",
]

GETVIDFB_API_KEYS = [
    # Apni existing GetVidFB API key yahan rakho
    "gvfb_eb940b21a7cfb2cf25d89e0e07b63a12ee85d72ebc8e4ecc",
    "gvfb_52220707e8e52b8d67be7d4edec6c1c64e2fee4d1a97c356",
]


# ============================================================
# TERABOX ALL SUPPORTED DOMAINS
# ============================================================

TERABOX_DOMAINS = [
    "terabox.com",
    "1024terabox.com",
    "teraboxapp.com",
    "teraboxlink.com",
    "terasharefile.com",
    "teraboxdownload.com",
    "4funbox.com",
    "mirrorbox.com",
    "mirrobox.com",
    "nephobox.com",
    "momerybox.com",
    "tibibox.com",
    "terabox.fun",
    "freeterabox.com",
]


def is_terabox_url(url: str) -> bool:
    """Check karo ki URL TeraBox ka hai ya nahi"""
    url_lower = str(url or "").lower()
    
    for domain in TERABOX_DOMAINS:
        # Domain ke aage '/' ya '://' ho — taaki 'x.com' type false match na ho
        if (
            f"://{domain}/" in url_lower
            or f"://www.{domain}/" in url_lower
        ):
            return True
    
    return False

# ============================================================
# TEMP USER DATA
# ============================================================

# Pyrogram me PTB context.user_data ka replacement.
# User ID ke basis par temporary quality-selection data.

yoinku_data = {}
terabox_data = {}


# ============================================================
# COMMON HELPERS
# ============================================================

def format_size(b):
    try:
        b = int(b or 0)
    except Exception:
        b = 0

    if b < 1024:
        return f"{b}B"

    elif b < 1048576:
        return f"{b / 1024:.1f}KB"

    elif b < 1073741824:
        return f"{b / 1048576:.1f}MB"

    return f"{b / 1073741824:.2f}GB"


def format_speed(bps):
    try:
        bps = float(bps or 0)
    except Exception:
        bps = 0

    if bps < 1024:
        return f"{bps:.0f}B/s"

    elif bps < 1048576:
        return f"{bps / 1024:.1f}KB/s"

    return f"{bps / 1048576:.1f}MB/s"


def format_eta(sec):
    try:
        sec = float(sec or 0)
    except Exception:
        sec = 0

    if sec < 0:
        sec = 0

    if sec < 60:
        return f"{sec:.0f}s"

    m = int(sec // 60)
    s = int(sec % 60)

    return f"{m}m {s}s"


def get_progress_bar(pct, length=15):
    try:
        pct = max(0, min(100, float(pct)))
    except Exception:
        pct = 0

    filled = int(length * pct / 100)

    return (
        "█" * filled
        + "░" * (length - filled)
    )


def get_live_progress_text(
    downloaded,
    total,
    start_time,
    status="Downloading"
):
    if total <= 0:
        total = 1

    pct = (
        downloaded / total * 100
        if total > 0
        else 0
    )

    elapsed = time.time() - start_time

    speed = (
        downloaded / elapsed
        if elapsed > 0
        else 0
    )

    if speed > 0 and total > downloaded:
        remaining = (
            total - downloaded
        ) / speed

        eta = format_eta(
            remaining
        )

    else:
        eta = "Calculating..."

    bar = get_progress_bar(pct)

    frames = [
        "⏳",
        "⌛",
        "⏳",
        "⌛"
    ]

    frame = frames[
        int(time.time() * 2)
        % len(frames)
    ]

    return (
        f"{frame} **{status}**\n\n"
        f"`{bar}` **{pct:.1f}%**\n"
        f"📦 **{format_size(downloaded)}** / "
        f"**{format_size(total)}**\n"
        f"⚡ **Speed:** "
        f"{format_speed(speed)}\n"
        f"⏳ **ETA:** {eta}"
    )


def get_platform(url):
    url_lower = str(url or "").lower()

    # ✅ TeraBox SABSE PEHLE check karo — saare domains ke saath
    if is_terabox_url(url):
        return "TeraBox"

    if "instagram.com/" in url_lower:
        return "Instagram"

    elif (
        "facebook.com/" in url_lower
        or "fb.watch/" in url_lower
    ):
        return "Facebook"

    elif (
        "twitter.com/" in url_lower
        or "//x.com/" in url_lower
        or url_lower.startswith("x.com/")
    ):
        return "X/Twitter"

    elif (
        "tiktok.com/" in url_lower
        or "vm.tiktok.com/" in url_lower
    ):
        return "TikTok"

    elif (
        "pinterest.com/" in url_lower
        or "pin.it/" in url_lower
    ):
        return "Pinterest"

    elif (
        "youtube.com/" in url_lower
        or "youtu.be/" in url_lower
    ):
        return "YouTube"

    return None


async def safe_edit_message(
    client,
    chat_id,
    message_id,
    text,
    parse_mode=None,
    reply_markup=None
):
    """
    Telegram message edit helper.

    BrokenPipe / reconnect ke time edit fail ho sakta hai.
    Download ko crash nahi hone deta.
    """

    try:
        kwargs = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }

        if parse_mode is not None:
            kwargs["parse_mode"] = parse_mode

        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup

        return await client.edit_message_text(
            **kwargs
        )

    except Exception as e:

        error_text = str(e).upper()

        if (
            "MESSAGE_NOT_MODIFIED"
            not in error_text
        ):
            print(
                f"⚠️ Message edit error: "
                f"{type(e).__name__}: {e}"
            )

        return None


# ============================================================
# COMMON ASYNC HTTP
# ============================================================

async def async_head(session, url):
    """Async HEAD request."""

    try:
        async with session.head(
            url,
            timeout=aiohttp.ClientTimeout(
                total=30
            ),
            allow_redirects=True
        ) as resp:

            return int(
                resp.headers.get(
                    "content-length",
                    0
                )
            )

    except Exception:
        return 0


async def async_download_with_progress(
    session,
    url,
    temp_file,
    progress_callback
):
    """
    Async file download with live progress.
    """

    async with session.get(
        url,
        timeout=aiohttp.ClientTimeout(
            total=300
        ),
        allow_redirects=True
    ) as resp:

        if resp.status >= 400:
            try:
                body = await resp.text()
                body = body[:200]
            except Exception:
                body = ""

            raise RuntimeError(
                f"HTTP {resp.status}"
                + (
                    f": {body}"
                    if body
                    else ""
                )
            )

        total = int(
            resp.headers.get(
                "content-length",
                0
            )
        )

        if total <= 0:
            total = 1

        downloaded = 0

        start_time = time.time()

        last_update = 0

        async with aiofiles.open(
            temp_file,
            "wb"
        ) as f:

            async for chunk in resp.content.iter_chunked(
                65536
            ):

                if not chunk:
                    continue

                await f.write(
                    chunk
                )

                downloaded += len(
                    chunk
                )

                now = time.time()

                if (
                    now - last_update
                    >= 0.5
                ):

                    last_update = now

                    await progress_callback(
                        downloaded,
                        total,
                        start_time
                    )

        # Final progress update.
        try:
            await progress_callback(
                downloaded,
                total,
                start_time
            )
        except Exception:
            pass

        return downloaded, total


# ============================================================
# STATS
# ============================================================

def update_platform_stats(platform: str):
    try:

        stats_col.update_one(
            {"_id": "platform_stats"},
            {
                "$inc": {
                    f"data.{platform.lower()}": 1
                }
            },
            upsert=True
        )

    except Exception:
        pass


def update_api_stats(api: str):
    try:

        key = (
            api.lower()
            .replace(" ", "_")
        )

        stats_col.update_one(
            {"_id": "api_stats"},
            {
                "$inc": {
                    f"data.{key}": 1
                }
            },
            upsert=True
        )

    except Exception:
        pass


# ============================================================
# LOGGING
# ============================================================

async def log_to_channel(
    client,
    user_id,
    username,
    platform,
    api_used,
    status,
    url="",
    size="",
    error=""
):
    """Send download log to LOG_CHANNEL_ID."""

    try:

        user_mention = (
            f"<a href='tg://user?id={user_id}'>"
            f"{html.escape(username or 'User')}"
            f"</a>"
        )

        log_text = (
            f"📥 <b>Download Log</b>\n\n"
            f"👤 <b>User:</b> {user_mention}\n"
            f"🆔 <b>ID:</b> "
            f"<code>{user_id}</code>\n"
            f"🌐 <b>Platform:</b> "
            f"{html.escape(str(platform))}\n"
            f"📡 <b>API Used:</b> "
            f"{html.escape(str(api_used))}\n"
            f"📦 <b>Size:</b> "
            f"{html.escape(str(size))}\n"
            f"📤 <b>Status:</b> "
            f"{html.escape(str(status))}\n"
            f"🔗 <b>URL:</b> "
            f"<code>{html.escape(url[:100])}"
            f"{'...' if len(url) > 100 else ''}</code>"
        )

        if error:

            safe_error = html.escape(
                str(error)[:500]
            )

            log_text += (
                f"\n\n⚠️ <b>Error:</b>\n"
                f"<code>{safe_error}</code>"
            )

        await client.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=log_text,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )

    except Exception:
        pass


# ============================================================
# COMMON API EXECUTOR
# ============================================================

async def call_api_async(func, *args):
    """Run sync API calls in executor."""

    loop = asyncio.get_running_loop()

    return await loop.run_in_executor(
        None,
        func,
        *args
    )


# ============================================================
# ========================= YOUTUBE ==========================
# ============================================================

def call_yoinku_sync(url):
    """
    YouTube info via Yoinku.

    NOTE:
    This function is kept separate from FastSaver YouTube.
    """

    for key in YOINKU_API_KEYS:

        if (
            not key
            or key.startswith("YOUR_")
            or key.startswith("PASTE_")
        ):
            continue

        try:

            resp = requests.get(
                "https://yoinku.com/api/v1/info",
                params={
                    "url": url
                },
                headers={
                    "x-api-key": key
                },
                timeout=30
            )

            data = resp.json()

            if data.get("ok"):
                
                return (
                    data.get("data", {}),
                    "Yoinku"
                )

        except Exception:
            continue

    return None, None


def call_fastsaver_youtube_sync(url):
    """
    FastSaver YouTube INFO.

    IMPORTANT:
    YouTube ka endpoint /v1/fetch nahi hai.
    Dedicated endpoint:
        /v1/youtube/info
    """

    for key in FASTSAVER_API_KEYS:

        if (
            not key
            or key.startswith("YOUR_")
            or key.startswith("PASTE_")
        ):
            continue

        try:

            resp = requests.get(
                "https://api.fastsaver.io/v1/youtube/info",
                params={
                    "url": url
                },
                headers={
                    "X-Api-Key": key
                },
                timeout=30
            )

            try:
                data = resp.json()
            except Exception:
                data = {}

            if data.get("ok"):
            
                # call_fastsaver_youtube_sync me
                print(f"🟥 YouTube API RESPONSE: {data}")
                return (
                    data,
                    "FastSaver YouTube"
                )

            print(
                "⚠️ FastSaver YouTube "
                f"info failed: "
                f"{resp.status_code} - "
                f"{data}"
            )

        except Exception as e:

            print(
                "⚠️ FastSaver YouTube "
                f"info error: "
                f"{type(e).__name__}: {e}"
            )

            continue

    return None, None


def extract_youtube_formats(data):
    """
    Safely extract YouTube formats.

    Expected:
        {
            "ok": true,
            "formats": [...]
        }
    """

    if not isinstance(data, dict):
        return []

    formats = data.get(
        "formats",
        []
    )

    if not isinstance(
        formats,
        list
    ):
        return []

    return [
        f
        for f in formats
        if isinstance(f, dict)
    ]


def extract_fastsaver_youtube_download(
    response_data
):
    """
    FastSaver YouTube download response.

    Official response:
        {
            "ok": true,
            "download_url": "...",
            "filename": "..."
        }

    Nested fallback is kept so unexpected API
    wrapping does not break the bot.
    """

    if not isinstance(
        response_data,
        dict
    ):
        return None, None

    download_url = (
        response_data.get(
            "download_url"
        )
        or response_data.get(
            "url"
        )
    )

    filename = (
        response_data.get(
            "filename"
        )
        or "youtube_video.mp4"
    )

    # Fallback: data
    nested_data = response_data.get(
        "data"
    )

    if (
        not download_url
        and isinstance(
            nested_data,
            dict
        )
    ):

        download_url = (
            nested_data.get(
                "download_url"
            )
            or nested_data.get(
                "url"
            )
        )

        filename = (
            nested_data.get(
                "filename"
            )
            or filename
        )

    # Fallback: result
    result = response_data.get(
        "result"
    )

    if (
        not download_url
        and isinstance(
            result,
            dict
        )
    ):

        download_url = (
            result.get(
                "download_url"
            )
            or result.get(
                "url"
            )
        )

        filename = (
            result.get(
                "filename"
            )
            or filename
        )

    if not isinstance(
        download_url,
        str
    ):
        return None, filename

    if not download_url.startswith(
        (
            "http://",
            "https://"
        )
    ):
        return None, filename

    return (
        download_url,
        filename
    )


def extract_yoinku_download(
    response_data
):
    """
    Yoinku download response extractor.
    """

    if not isinstance(
        response_data,
        dict
    ):
        return None, None

    data = response_data.get(
        "data"
    )

    if not isinstance(
        data,
        dict
    ):
        data = response_data

    download_url = (
        data.get("url")
        or data.get("download_url")
    )

    filename = (
        data.get("filename")
        or "video.mp4"
    )

    if not download_url:
        return None, filename

    return (
        download_url,
        filename
    )


def call_fastsaver_youtube_download_sync(
    url,
    format_id
):
    """
    ONLY YOUTUBE.

    FastSaver:
        POST /v1/youtube/download

    Body:
        {
            "url": "...",
            "format": "144p"
        }
    """

    for key in FASTSAVER_API_KEYS:

        if (
            not key
            or key.startswith("YOUR_")
            or key.startswith("PASTE_")
        ):
            continue

        try:

            resp = requests.post(
                "https://api.fastsaver.io/v1/youtube/download",
                json={
                    "url": url,
                    "format": format_id
                },
                headers={
                    "X-Api-Key": key,
                    "Content-Type": "application/json"
                },
                timeout=60
            )

            try:
                response_data = resp.json()
            except Exception:
                response_data = {}

            if response_data.get("ok"):

                return extract_fastsaver_youtube_download(
                    response_data
                )

            print(
                "⚠️ FastSaver YouTube "
                f"download failed: "
                f"{resp.status_code} - "
                f"{response_data}"
            )

        except Exception as e:

            print(
                "⚠️ FastSaver YouTube "
                f"download error: "
                f"{type(e).__name__}: {e}"
            )

            continue

    return None, None


# ============================================================
# ======================== INSTAGRAM =========================
# ============================================================

def call_instagram_api_sync(url):

    for api_url in INSTAGRAM_API_URLS:

        if (
            not api_url
            or api_url.startswith("YOUR_")
            or api_url.startswith("PASTE_")
        ):
            continue

        try:

            resp = requests.post(
                api_url,
                json={
                    "url": url
                },
                timeout=30
            )

            data = resp.json()

            if data.get("success"):

                return (
                    data,
                    "Instagram API"
                )

        except Exception:
            continue

    return None, None


# ============================================================
# ======================== FACEBOOK ==========================
# ============================================================

def call_getvidfb_sync(url):

    for key in GETVIDFB_API_KEYS:

        if (
            not key
            or key.startswith("YOUR_")
            or key.startswith("PASTE_")
        ):
            continue

        try:

            resp = requests.get(
                "https://getvidfb.com/api/v1/video-info",
                params={
                    "url": url
                },
                headers={
                    "X-API-Key": key
                },
                timeout=30
            )

            data = resp.json()

            if data.get("success"):

                return (
                    data,
                    "GetVidFB"
                )

        except Exception:
            continue

    return None, None


# ============================================================
# ======================== FASTSAVER =========================
# ========== INSTAGRAM / FACEBOOK / TIKTOK / X / PINTEREST ==
# ============================================================

def call_fastsaver_sync(url):

    for key in FASTSAVER_API_KEYS:

        if (
            not key
            or key.startswith("YOUR_")
            or key.startswith("PASTE_")
        ):
            continue

        try:

            resp = requests.get(
                "https://api.fastsaver.io/v1/fetch",
                params={
                    "url": url
                },
                headers={
                    "X-Api-Key": key
                },
                timeout=30
            )

            try:
                data = resp.json()
            except Exception:
                data = {}

            if data.get("ok"):

                return (
                    data,
                    "FastSaver"
                )

            print(
                f"⚠️ FastSaver failed: "
                f"{resp.status_code} - "
                f"{data}"
            )

        except Exception as e:

            print(
                f"⚠️ FastSaver error: "
                f"{type(e).__name__}: {e}"
            )

            continue

    return None, None


# ============================================================
# ========================== TERABOX =========================
# ============================================================

def call_terabox_sync(url):

    print(f"🟦 TeraBox API REQUEST: {url}")

    for key in TERABOX_API_KEYS:

        if (
            not key
            or key.startswith("YOUR_")
            or key.startswith("PASTE_")
        ):
            continue

        try:

            resp = requests.get(
                "https://api.playterabox.com/api/proxy",
                params={
                    "secret": key,
                    "url": url
                },
                timeout=30
            )

            print(
                f"🟦 TeraBox API STATUS: "
                f"{resp.status_code}"
            )

            data = resp.json()

            print(
                f"🟦 TeraBox API RESPONSE: "
                f"{data}"
            )

            if (
                data.get("status")
                == "success"
                and data.get("list")
            ):

                print("✅ TeraBox API SUCCESS")

                return (
                    data,
                    "TeraBox"
                )

        except Exception as e:

            print(
                f"❌ TeraBox API ERROR: "
                f"{e}"
            )

            continue

    print("❌ All TeraBox API keys failed")

    return None, None


# ============================================================
# ====================== FETCH INFO ROUTER ===================
# ============================================================

async def fetch_video_info_async(
    url,
    platform
):
    """
    Platform router.

    IMPORTANT:
    Har platform ka API flow yahan separate hai.
    """

    # ========================================================
    # YOUTUBE
    # ========================================================

    if platform == "YouTube":

        # 1. Yoinku
        data, api_used = await call_api_async(
            call_yoinku_sync,
            url
        )

        if data:
            return data, api_used

        # 2. FastSaver YouTube
        data, api_used = await call_api_async(
            call_fastsaver_youtube_sync,
            url
        )

        if data:
            return data, api_used

        return None, None

    # ========================================================
    # INSTAGRAM
    # ========================================================

    elif platform == "Instagram":

        # 1. Instagram API
        data, api_used = await call_api_async(
            call_instagram_api_sync,
            url
        )

        if data:
            return data, api_used

        # 2. FastSaver
        data, api_used = await call_api_async(
            call_fastsaver_sync,
            url
        )

        if data:
            return data, api_used

        # 3. Yoinku
        data, api_used = await call_api_async(
            call_yoinku_sync,
            url
        )

        if data:
            return data, api_used

        return None, None

    # ========================================================
    # FACEBOOK
    # ========================================================

    elif platform == "Facebook":

        # 1. GetVidFB
        data, api_used = await call_api_async(
            call_getvidfb_sync,
            url
        )

        if data:
            return data, api_used

        # 2. FastSaver
        data, api_used = await call_api_async(
            call_fastsaver_sync,
            url
        )

        if data:
            return data, api_used

        return None, None

    # ========================================================
    # TIKTOK
    # ========================================================

    elif platform == "TikTok":

        # 1. Yoinku
        data, api_used = await call_api_async(
            call_yoinku_sync,
            url
        )

        if data:
            return data, api_used

        # 2. FastSaver
        data, api_used = await call_api_async(
            call_fastsaver_sync,
            url
        )

        if data:
            return data, api_used

        return None, None

    # ========================================================
    # PINTEREST
    # ========================================================

    elif platform == "Pinterest":

        data, api_used = await call_api_async(
            call_fastsaver_sync,
            url
        )

        if data:
            return data, api_used

        return None, None

    # ========================================================
    # X / TWITTER
    # ========================================================

    elif platform == "X/Twitter":

        data, api_used = await call_api_async(
            call_fastsaver_sync,
            url
        )

        if data:
            return data, api_used

        return None, None

    # ========================================================
    # TERABOX
    # ========================================================

    elif platform == "TeraBox":

        print(    
            f"🟦 TeraBox detected: {url}"
        )

        data, api_used = await call_api_async(
            call_terabox_sync,
            url
        )

        if data:
            print(
                "✅ TeraBox video info received"
            )

            return data, api_used
 
        print(
            "❌ TeraBox video info failed"
        )

        return None, None


# ============================================================
# ====================== DOWNLOAD ROUTER =====================
# ============================================================

async def download_and_send(
    client,
    message,
    url: str,
    premium: bool = False
) -> bool:

    user = message.from_user

    user_id = user.id

    chat_id = message.chat.id

    username = (
        user.username
        or user.first_name
        or "Unknown"
    )

    platform = get_platform(
        url
    )

    if not platform:

        await client.send_message(
            chat_id=chat_id,
            text="❌ <b>Unsupported URL.</b>",
            parse_mode=enums.ParseMode.HTML
        )

        return False

    # ========================================================
    # FETCH INFO
    # ========================================================

    processing_msg = await client.send_message(
        chat_id=chat_id,
        text="🔍 ꜰᴇᴛᴄʜɪɴɢ.",
        parse_mode=enums.ParseMode.HTML
    )

    proc_id = processing_msg.id

    processing_stop = asyncio.Event()

    processing_task = asyncio.create_task(
        processing_animation(
            client,
            chat_id,
            proc_id,
            processing_stop
        )
    )

    try:

        data, api_used = (
            await fetch_video_info_async(
                url,
                platform
            )
        )

        processing_stop.set()

        try:
            await processing_task
        except Exception:
            pass

    except Exception as e:

        processing_stop.set()

        try:
            await processing_task
        except Exception:
            pass

        error_msg = (
            f"API fetch error: {str(e)}"
        )

        await log_to_channel(
            client,
            user_id,
            username,
            platform,
            "—",
            "❌ API Fetch Error",
            url,
            error=error_msg
        )

        await safe_edit_message(
            client,
            chat_id,
            proc_id,
            (
                "❌ <b>Failed to fetch video info.</b>\n\n"
                f"<code>{html.escape(str(e)[:200])}</code>"
            ),
            enums.ParseMode.HTML
        )

        return False

    if not data:

        await log_to_channel(
            client,
            user_id,
            username,
            platform,
            "—",
            "❌ No Data from API",
            url
        )

        await safe_edit_message(
            client,
            chat_id,
            proc_id,
            (
                "❌ <b>Failed to fetch video info.</b>\n\n"
                f"API: <code>{html.escape(api_used or 'None')}</code>\n"
                "💡 Try again later."
            ),
            enums.ParseMode.HTML
        )

        return False

    # ========================================================
    # COMMON VARIABLES
    # ========================================================

    download_url = None
    file_name = None
    file_size = 0
    caption = ""

    # ========================================================
    # FASTSAVER NORMAL
    # ========================================================

    if api_used == "FastSaver":

        if data.get("type") == "video":

            download_url = (
                data.get("download_url")
                or data.get("url")
            )

            caption = data.get(
                "caption",
                ""
            )

        elif data.get("type") == "image":

            download_url = (
                data.get("download_url")
                or data.get("url")
            )

            caption = data.get(
                "caption",
                ""
            )

        elif data.get("type") == "album":

            items = data.get(
                "items",
                []
            )

            if items:

                first_item = items[0]

                if isinstance(
                    first_item,
                    dict
                ):

                    download_url = (
                        first_item.get(
                            "download_url"
                        )
                        or first_item.get(
                            "video_url"
                        )
                        or first_item.get(
                            "url"
                        )
                        or ""
                    )

                caption = data.get(
                    "caption",
                    ""
                )

    # ========================================================
    # YOINKU
    # ========================================================

    elif api_used == "Yoinku":

        formats = data.get(
            "formats",
            []
        )

        if formats:

            await show_yoinku_quality_options(
                client,
                chat_id,
                proc_id,
                formats,
                url,
                platform,
                premium,
                data,
                user_id
            )

            return True

        await log_to_channel(
            client,
            user_id,
            username,
            platform,
            api_used,
            "❌ No Formats",
            url
        )

        await safe_edit_message(
            client,
            chat_id,
            proc_id,
            "❌ <b>No formats available.</b>",
            enums.ParseMode.HTML
        )

        return False

    # ========================================================
    # FASTSAVER YOUTUBE
    # ========================================================

    elif api_used == "FastSaver YouTube":

        formats = extract_youtube_formats(
            data
        )

        if formats:

            await show_fastsaver_youtube_quality_options(
                client,
                chat_id,
                proc_id,
                formats,
                url,
                platform,
                premium,
                data,
                user_id
            )

            return True

        await log_to_channel(
            client,
            user_id,
            username,
            platform,
            api_used,
            "❌ No YouTube Formats",
            url
        )

        await safe_edit_message(
            client,
            chat_id,
            proc_id,
            "❌ <b>No YouTube formats available.</b>",
            enums.ParseMode.HTML
        )

        return False

   # ========================================================
   # TERABOX
   # ========================================================

    elif api_used == "TeraBox":

        files = data.get("list", [])
 
        if not files:
            await safe_edit_message(
                client, chat_id, proc_id,
                "❌ <b>No files found in TeraBox.</b>",
                enums.ParseMode.HTML
            )
            return False

        file_info = files[0]
 
        download_url = file_info.get("normal_dlink")
        file_name = file_info.get("name", "video.mp4")
        file_size = file_info.get("size", 0)

        # Thumbnail nikaalo
        # Thumbnail nikaalo — TeraBox API 'thumbnail' field deta hai
        thumb_url = (
            file_info.get("thumbnail")
            or file_info.get("thumb")
            or file_info.get("thumb_url")
        )

        # Fallback: purana thumbs dict
        if not thumb_url:
            thumbs = file_info.get("thumbs", {})
            if isinstance(thumbs, dict):
                thumb_url = (
                    thumbs.get("url3")
                    or thumbs.get("url2")
                    or thumbs.get("url1")
                    or thumbs.get("url")
                )

        # Caption
        caption = (
            f"📁 <b>{html.escape(str(file_name))}</b>\n"
            f"📦 Size: {format_size(file_size)}"
        )
 
        # Session data save karo (download ke liye)
        terabox_data[user_id] = {
            "url": url,
            "premium": premium,
            "file_info": file_info,
            "download_url": download_url,
            "file_name": file_name,
        }
 
        # Download button
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📥 Download",
                    callback_data="tb_download"
                )
            ]
        ])

        # Processing message delete karo
        try:
            await client.delete_messages(
                chat_id=chat_id,
                message_ids=proc_id
            )
        except Exception:
            pass

        # Thumbnail download karo
        thumb_path = None
        if thumb_url:
            try:
                thumb_path = os.path.join(
                    THUMBNAIL_DIR,
                    f"thumb_{user_id}_{int(time.time())}.jpg"
                )
                async with aiohttp.ClientSession() as session:
                    async with session.get(thumb_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(thumb_path, "wb") as f:
                                await f.write(await resp.read())
                        else:
                            thumb_path = None
            except Exception as e:
                print(f"⚠️ Thumbnail download failed: {e}")
                thumb_path = None

        # Photo bhejo
        try:
            if thumb_path and os.path.exists(thumb_path):
                await client.send_photo(
                    chat_id=chat_id,
                    photo=thumb_path,
                    caption=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=keyboard
                )
                os.remove(thumb_path)
            else:
                # Thumbnail fail — simple text message
                await client.send_message(
                    chat_id=chat_id,
                    text=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=keyboard
                )
        except Exception as e:
            print(f"⚠️ Send photo failed: {e}")
            # Fallback text
            try:
                await client.send_message(
                    chat_id=chat_id,
                    text=caption,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=keyboard
                )
            except Exception:
                pass

        return True

    # ========================================================
    # INSTAGRAM API
    # ========================================================

    elif api_used == "Instagram API":

        media_items = (
            data.get("data", {})
            .get("mediaItems", [])
        )

        if media_items:

            first_item = media_items[0]

            if isinstance(
                first_item,
                dict
            ):

                download_url = (
                    first_item.get(
                        "url"
                    )
                    or first_item.get(
                        "download_url"
                    )
                )

            caption = (
                data.get("data", {})
                .get("postInfo", {})
                .get("caption", "")
            )

    # ========================================================
    # GETVIDFB
    # ========================================================

    elif api_used == "GetVidFB":

        links = data.get(
            "links",
            {}
        )

        download_url = (
            links.get("hd")
            or links.get("sd")
            or links.get("audio")
            or ""
        )

        caption = (
            data.get("description")
            or data.get("title")
            or ""
        )

    # ========================================================
    # NO URL
    # ========================================================

    if not download_url:

        await log_to_channel(
            client,
            user_id,
            username,
            platform,
            api_used,
            "❌ No URL Found",
            url
        )

        await safe_edit_message(
            client,
            chat_id,
            proc_id,
            "❌ <b>No download URL found.</b>",
            enums.ParseMode.HTML
        )

        return False

    # ========================================================
    # PERFORM DOWNLOAD
    # ========================================================

    success, file_size_downloaded, error_reason = (
        await perform_download(
            client,
            chat_id,
            proc_id,
            download_url,
            caption,
            file_name,
            premium,
            user_id,
            platform,
            api_used,
            username,
            url
        )
    )

    if success:

        update_platform_stats(
            platform
        )

        update_api_stats(
            api_used
        )

        await check_and_reward_referrals(
            client,
            user_id
        )

        await log_to_channel(
            client,
            user_id,
            username,
            platform,
            api_used,
            "✅ Success",
            url,
            format_size(
                file_size_downloaded
            )
        )

        return True

    await log_to_channel(
        client,
        user_id,
        username,
        platform,
        api_used,
        "❌ Download Failed",
        url,
        error=error_reason
    )

    await safe_edit_message(
        client,
        chat_id,
        proc_id,
        (
            "❌ <b>Download failed!</b>\n\n"
            f"Reason: <code>"
            f"{html.escape(str(error_reason)[:200])}"
            f"</code>\n\n"
            "Please try again later."
        ),
        enums.ParseMode.HTML
    )

    return False


# ============================================================
# ====================== YOINKU QUALITY ======================
# ============================================================

async def show_yoinku_quality_options(
    client,
    chat_id,
    proc_id,
    formats,
    url,
    platform,
    premium,
    data,
    user_id
):
    """Show quality buttons for Yoinku (with thumbnail + title)."""

    buttons = []
    row = []

    yoinku_data[user_id] = {
        "url": url,
        "platform": platform,
        "premium": premium,
        "data": data,
        "api_used": "Yoinku"
    }

    # ========================================================
    # VIDEO BUTTONS
    # ========================================================

    for f in formats:

        if not isinstance(f, dict):
            continue

        if (
            f.get("kind") == "video"
            and f.get("hasVideo")
        ):

            quality = f.get("quality", "")

            if quality:

                # Filesize bhi dikhao
                filesize = f.get("filesizeBytes")
                label = str(quality)

                if filesize:
                    try:
                        label = f"{quality} • {format_size(filesize)}"
                    except Exception:
                        pass

                row.append(
                    InlineKeyboardButton(
                        label,
                        callback_data=(
                            f"dl_{f.get('id', quality)}"
                        )
                    )
                )

                if len(row) == 2:
                    buttons.append(row)
                    row = []

    if row:
        buttons.append(row)

    # ========================================================
    # AUDIO BUTTON
    # ========================================================

    for f in formats:

        if not isinstance(f, dict):
            continue

        if f.get("kind") == "audio":

            buttons.append(
                [
                    InlineKeyboardButton(
                        "🎵 Audio",
                        callback_data=(
                            f"dl_{f.get('id', 'audio')}"
                        )
                    )
                ]
            )

            break

    buttons.append(
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="dl_cancel"
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(buttons)

    # ========================================================
    # TITLE + THUMBNAIL NIKAALO
    # ========================================================

    title = (
        data.get("title")
        or data.get("video_title")
        or "YouTube Video"
    )

    thumbnail = (
        data.get("thumbnailUrl")
        or data.get("thumbnail")
        or data.get("thumb")
    )

    # Caption banao
    caption = (
        f"🎬 <b>{html.escape(str(title)[:200])}</b>\n\n"
        f"📺 <b>Choose Quality:</b>"
    )

    # ========================================================
    # THUMBNAIL DOWNLOAD
    # ========================================================

    thumb_path = None

    if thumbnail:
        try:
            thumb_path = os.path.join(
                THUMBNAIL_DIR,
                f"yt_thumb_{user_id}_{int(time.time())}.jpg"
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    thumbnail,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(thumb_path, "wb") as f:
                            await f.write(await resp.read())
                    else:
                        print(f"⚠️ YT thumbnail HTTP {resp.status}")
                        thumb_path = None

        except Exception as e:
            print(f"⚠️ YT thumbnail download failed: {e}")
            thumb_path = None

    # ========================================================
    # PROCESSING MESSAGE DELETE
    # ========================================================

    try:
        await client.delete_messages(
            chat_id=chat_id,
            message_ids=proc_id
        )
    except Exception:
        pass

    # ========================================================
    # PHOTO + BUTTONS BHEJO
    # ========================================================

    if thumb_path and os.path.exists(thumb_path):

        try:

            await client.send_photo(
                chat_id=chat_id,
                photo=thumb_path,
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=keyboard
            )

            os.remove(thumb_path)
            return

        except Exception as e:

            print(f"⚠️ Send YT photo failed: {e}")

            try:
                os.remove(thumb_path)
            except Exception:
                pass

    # ========================================================
    # FALLBACK — TEXT MESSAGE
    # ========================================================

    await client.send_message(
        chat_id=chat_id,
        text=caption,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard
    )


# ============================================================
# ================= FASTSAVER YOUTUBE QUALITY ================
# ============================================================

async def show_fastsaver_youtube_quality_options(
    client,
    chat_id,
    proc_id,
    formats,
    url,
    platform,
    premium,
    data,
    user_id
):
    """
    ONLY YOUTUBE.

    FastSaver supported:
        144p
        240p
        360p
        480p
        720p
        1080p
        1440p
        2160p
        audio
    """

    buttons = []
    row = []

    yoinku_data[user_id] = {
        "url": url,
        "platform": platform,
        "premium": premium,
        "data": data,
        "api_used": "FastSaver YouTube"
    }

    video_buttons_added = set()

    # ========================================================
    # VIDEO FORMATS
    # ========================================================

    for f in formats:

        if not isinstance(
            f,
            dict
        ):
            continue

        format_id = (
            f.get("format")
            or f.get("id")
            or f.get("quality")
        )

        if not format_id:
            continue

        format_id = str(
            format_id
        )

        # Audio ko video grid me mat dalo.
        if format_id.lower() == "audio":
            continue

        kind = str(
            f.get("type")
            or f.get("kind")
            or "video"
        ).lower()

        label = (
            f.get("label")
            or f.get("quality")
            or format_id
        )

        # Explicit audio item skip.
        if kind == "audio":
            continue

        if format_id in video_buttons_added:
            continue

        filesize = (
            f.get("filesize")
            or f.get("file_size")
            or ""
        )

        if filesize:

            try:
                if isinstance(
                    filesize,
                    (int, float)
                ):
                    filesize = format_size(
                        filesize
                    )
            except Exception:
                pass

            label = (
                f"{label} • "
                f"{filesize}"
            )

        row.append(
            InlineKeyboardButton(
                str(label),
                callback_data=(
                    f"dl_{format_id}"
                )
            )
        )

        video_buttons_added.add(
            format_id
        )

        if len(row) == 2:

            buttons.append(
                row
            )

            row = []

    if row:
        buttons.append(
            row
        )

    # ========================================================
    # AUDIO
    # ========================================================

    audio_found = False

    for f in formats:

        if not isinstance(
            f,
            dict
        ):
            continue

        format_id = (
            f.get("format")
            or f.get("id")
            or ""
        )

        kind = str(
            f.get("type")
            or f.get("kind")
            or ""
        ).lower()

        label = str(
            f.get("label")
            or ""
        ).lower()

        if (
            str(format_id).lower()
            == "audio"
            or kind == "audio"
            or "audio" in label
        ):

            buttons.append(
                [
                    InlineKeyboardButton(
                        "🎵 Audio",
                        callback_data=(
                            f"dl_{format_id or 'audio'}"
                        )
                    )
                ]
            )

            audio_found = True

            break

    buttons.append(
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="dl_cancel"
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(
        buttons
    )

    await safe_edit_message(
        client,
        chat_id,
        proc_id,
        (
            "🎬 <b>Select Quality</b>\n\n"
            "📺 Choose YouTube video quality:"
        ),
        enums.ParseMode.HTML,
        keyboard
    )


# ============================================================
# ====================== TERABOX QUALITY ====================
# ============================================================

async def show_terabox_quality_options(
    client,
    chat_id,
    proc_id,
    stream_urls,
    file_info,
    url,
    premium,
    user_id
):
    """Show quality buttons for TeraBox."""

    buttons = []

    terabox_data[user_id] = {
        "url": url,
        "premium": premium,
        "file_info": file_info,
        "stream_urls": stream_urls
    }

    for quality, stream_url in stream_urls.items():

        if stream_url:

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"📺 {quality}",
                        callback_data=(
                            f"tb_{quality}"
                        )
                    )
                ]
            )

    if file_info.get(
        "normal_dlink"
    ):

        buttons.append(
            [
                InlineKeyboardButton(
                    "📥 Direct Download",
                    callback_data="tb_direct"
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="dl_cancel"
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(
        buttons
    )

    await safe_edit_message(
        client,
        chat_id,
        proc_id,
        (
            "🎬 <b>Select Quality</b>\n\n"
            f"📁 "
            f"{html.escape(str(file_info.get('name', 'Video')))}\n"
            f"📦 Size: "
            f"{format_size(file_info.get('size', 0))}"
        ),
        enums.ParseMode.HTML,
        keyboard
    )


# ============================================================
# ====================== UPLOAD PROGRESS ====================
# ============================================================

def create_upload_progress_callback(
    client,
    chat_id,
    proc_id
):
    """
    Pyrogram upload callback.
    """

    state = {
        "last_current": 0,
        "total": 0,
        "start_time": time.time(),
        "finished": False
    }

    def upload_progress(
        current,
        total
    ):

        if total <= 0:
            return

        state["last_current"] = (
            current
        )

        state["total"] = (
            total
        )

    return (
        upload_progress,
        state
    )


async def upload_progress_updater(
    client,
    chat_id,
    proc_id,
    state
):
    """
    Upload progress updater.

    Telegram connection temporary reconnect kare to
    upload ko crash nahi karta.
    """

    while not state["finished"]:

        try:

            current = state[
                "last_current"
            ]

            total = state[
                "total"
            ]

            if total > 0:

                now = time.time()

                elapsed = (
                    now
                    - state["start_time"]
                )

                speed = (
                    current / elapsed
                    if elapsed > 0
                    else 0
                )

                pct = (
                    current / total * 100
                    if total > 0
                    else 0
                )

                remaining = (
                    (total - current)
                    / speed
                    if speed > 0
                    and total > current
                    else 0
                )

                eta = (
                    format_eta(
                        remaining
                    )
                    if remaining > 0
                    else "Calculating..."
                )

                bar = get_progress_bar(
                    pct
                )

                text = (
                    f"📤 **Uploading**\n\n"
                    f"`{bar}` **{pct:.1f}%**\n"
                    f"📦 **{format_size(current)}** / "
                    f"**{format_size(total)}**\n"
                    f"⚡ **Speed:** "
                    f"{format_speed(speed)}\n"
                    f"⏳ **ETA:** {eta}"
                )

            else:

                dots = (
                    "." * (
                        int(time.time() * 2)
                        % 3 + 1
                    )
                )

                text = (
                    f"📤 ᴜᴘʟᴏᴀᴅɪɴɢ{dots}"
                )

            await safe_edit_message(
                client,
                chat_id,
                proc_id,
                text,
                enums.ParseMode.MARKDOWN
            )

        except Exception as e:

            print(
                "⚠️ Upload progress "
                f"updater error: "
                f"{type(e).__name__}: {e}"
            )

        await asyncio.sleep(
            0.5
        )


# ============================================================
# ====================== FILE TYPE ===========================
# ============================================================

def get_file_extension(
    file_name
):
    """
    Detect extension safely.
    """

    if not file_name:
        return ".mp4"

    try:

        name = os.path.basename(
            str(file_name)
        )

        ext = os.path.splitext(
            name
        )[1].lower()

        if ext:
            return ext

    except Exception:
        pass

    return ".mp4"


def is_audio_file(
    file_name
):
    ext = get_file_extension(
        file_name
    )

    return ext in {
        ".m4a",
        ".mp3",
        ".aac",
        ".wav",
        ".ogg",
        ".flac"
    }


# ============================================================
# ====================== PERFORM DOWNLOAD ===================
# ============================================================

async def perform_download(
    client,
    chat_id,
    proc_id,
    download_url,
    caption="",
    file_name=None,
    premium=False,
    user_id=None,
    platform="",
    api_used="",
    username="",
    url=""
):
    """
    Download file -> Upload Telegram.

    Returns:
        (
            success,
            file_size,
            error_reason
        )
    """

    extension = get_file_extension(
        file_name
    )

    temp_file = os.path.join(
        TEMP_DOWNLOAD_DIR,
        f"user_{user_id or 'user'}_{int(time.time())}{extension}"
    )

    file_size_downloaded = 0

    error_reason = ""

    download_stop = asyncio.Event()
    download_animation_task = None

    try:
        download_animation_task = asyncio.create_task(
            processing_animation(
                client,
                chat_id,
                proc_id,
                download_stop
            )
        )
        # ====================================================
        # GET FILE SIZE
        # ====================================================

        total = 0

        try:

            async with aiohttp.ClientSession() as session:

                total = await async_head(
                    session,
                    download_url
                )

        except Exception:

            total = 0

        # ====================================================
        # DOWNLOAD
        # ====================================================

        async def update_progress(
            d,
            t,
            s
        ):

            nonlocal file_size_downloaded

            file_size_downloaded = d

            download_stop.set()

            try:
                await download_animation_task
            except Exception:
                pass

            try:

                text = get_live_progress_text(
                    d,
                    t,
                    s,
                    "Downloading"
                )

                await safe_edit_message(
                    client,
                    chat_id,
                    proc_id,
                    text,
                    enums.ParseMode.MARKDOWN
                )

            except Exception:
                pass

        try:

            async with aiohttp.ClientSession() as session:

                (
                    downloaded,
                    total
                ) = await async_download_with_progress(
                    session,
                    download_url,
                    temp_file,
                    update_progress
                )

                file_size_downloaded = (
                    downloaded
                )

        except Exception as e:

            error_reason = (
                f"Download error: "
                f"{str(e)[:200]}"
            )

            raise RuntimeError(
                error_reason
            )

        # ====================================================
        # FILE CHECK
        # ====================================================

        if not os.path.exists(
            temp_file
        ):

            error_reason = (
                "Temp file not created"
            )

            raise RuntimeError(
                error_reason
            )

        actual_size = os.path.getsize(
            temp_file
        )

        if actual_size <= 0:

            error_reason = (
                "Downloaded file is empty "
                "(0 bytes)"
            )

            raise RuntimeError(
                error_reason
            )

        file_size_downloaded = (
            actual_size
        )

        # ====================================================
        # UPLOADING
        # ====================================================

        await safe_edit_message(
            client,
            chat_id,
            proc_id,
            "📤 <b>Uploading...</b>",
            enums.ParseMode.HTML
        )

        safe_caption = (
            html.escape(
                str(caption)[:1000]
            )
            if caption
            else ""
        )

        sent = None

        upload_task = None
        upload_state = None

        try:

            (
                upload_progress,
                upload_state
            ) = create_upload_progress_callback(
                client,
                chat_id,
                proc_id
            )

            upload_task = asyncio.create_task(
                upload_progress_updater(
                    client,
                    chat_id,
                    proc_id,
                    upload_state
                )
            )

            with open(
                temp_file,
                "rb"
            ) as f:

                # =================================================
                # AUDIO
                # =================================================

                if is_audio_file(
                    file_name
                ):

                    sent = await client.send_audio(
                        chat_id=chat_id,
                        audio=f,
                        caption=safe_caption,
                        parse_mode=enums.ParseMode.HTML,
                        progress=upload_progress
                    )

                # =================================================
                # VIDEO
                # =================================================

                else:

                    sent = await client.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=safe_caption,
                        supports_streaming=True,
                        parse_mode=enums.ParseMode.HTML,
                        progress=upload_progress
                    )

        except Exception as e:

            error_reason = (
                f"Upload error: "
                f"{str(e)[:200]}"
            )

            raise RuntimeError(
                error_reason
            )

        finally:

            if upload_state is not None:

                upload_state[
                    "finished"
                ] = True

            if upload_task is not None:

                try:
                    await upload_task

                except asyncio.CancelledError:
                    pass

                except Exception:
                    pass

        # ====================================================
        # AUTO DELETE WARNING
        # ====================================================

        try:

            warning_msg = await client.send_message(
                chat_id=chat_id,
                text=(
                    "⚠️ <b>Forward/Save this file!</b>\n\n"
                    "This file will be <b>automatically "
                    "deleted</b> after <b>10 minutes</b>."
                ),
                parse_mode=enums.ParseMode.HTML
            )

        except Exception:

            warning_msg = None

        # ====================================================
        # TEMP FILE CLEANUP
        # ====================================================

        try:

            os.remove(
                temp_file
            )

        except Exception:
            pass

        # ====================================================
        # DELETE PROCESSING MESSAGE
        # ====================================================

        try:

            await client.delete_messages(
                chat_id=chat_id,
                message_ids=proc_id
            )

        except Exception:
            pass

        # ====================================================
        # CREDIT
        # ====================================================

        if not premium:

            try:

                credit_cost = CREDIT_COSTS.get(
                    platform,
                    0
                )

                if credit_cost > 0:

                    deducted = await deduct_credit_atomic(
                        user_id,
                        credit_cost
                    )

                    if not deducted:
 
                        await log_to_channel(
                            client,
                            user_id,
                            username,
                            platform,
                            api_used,
                            "⚠️ Credit deduct failed",
                            url
                        )

            except Exception as e:

                print(
                    "⚠️ Credit deduction error: "
                    f"{type(e).__name__}: {e}"
                )

        # ====================================================
        # AUTO DELETE
        # ====================================================

        if warning_msg and sent:

            asyncio.create_task(
                auto_delete_callback(
                    client,
                    chat_id,
                    sent.id,
                    warning_msg.id
                )
            )

        return (
            True,
            file_size_downloaded,
            ""
        )

    except Exception as e:

        download_stop.set()

        if download_animation_task is not None:
            try:
                await download_animation_task
            except Exception:
                pass

        try:

            if os.path.exists(
                temp_file
            ):
                os.remove(
                    temp_file
                )

        except Exception:
            pass

        if not error_reason:

            error_reason = (
                f"{type(e).__name__}: "
                f"{str(e)[:200]}"
            )

        return (
            False,
            0,
            error_reason
        )


# ============================================================
# ====================== AUTO DELETE =========================
# ============================================================

async def auto_delete_callback(
    client,
    chat_id,
    video_msg_id,
    warning_msg_id
):
    """
    Delete downloaded file + warning
    after 10 minutes.
    """

    await asyncio.sleep(
        600
    )

    try:

        if video_msg_id:

            await client.delete_messages(
                chat_id=chat_id,
                message_ids=video_msg_id
            )

    except Exception:
        pass

    try:

        if warning_msg_id:

            await client.delete_messages(
                chat_id=chat_id,
                message_ids=warning_msg_id
            )

    except Exception:
        pass


# ============================================================
# =================== YOUTUBE CALLBACK ======================
# ============================================================

async def handle_youtube_callback(
    client,
    callback_query,
    format_id,
    yt_data
):
    """
    ONLY YOUTUBE.

    Quality button click:
        dl_144p
        dl_720p
        dl_audio
    """

    user_id = callback_query.from_user.id

    message = callback_query.message

    chat_id = message.chat.id

    url = yt_data.get(
        "url"
    )

    premium = yt_data.get(
        "premium",
        False
    )

    platform = yt_data.get(
        "platform",
        "YouTube"
    )

    api_used = yt_data.get(
        "api_used",
        "Yoinku"
    )

    username = (
        callback_query.from_user.username
        or callback_query.from_user.first_name
        or "User"
    )

    # ========================================================
    # START MESSAGE
    # ========================================================

    processing_stop = asyncio.Event()
    processing_task = None

    try:

        processing_task = asyncio.create_task(
            processing_animation(
                client,
                chat_id,
                message.id,
                processing_stop
            )
        )

        # ====================================================
        # FASTSAVER YOUTUBE
        # ====================================================

        if api_used == "FastSaver YouTube":

            (
                download_url,
                filename
            ) = await call_api_async(
                call_fastsaver_youtube_download_sync,
                url,
                format_id
            )

        # ====================================================
        # YOINKU YOUTUBE
        # ====================================================

        else:

            def call_yoinku_download():

                for key in YOINKU_API_KEYS:

                    if (
                        not key
                        or key.startswith("YOUR_")
                        or key.startswith("PASTE_")
                    ):
                        continue

                    try:

                        resp = requests.get(
                            "https://yoinku.com/api/v1/download",
                            params={
                                "url": url,
                                "format": format_id
                            },
                            headers={
                                "x-api-key": key
                            },
                            timeout=60
                        )

                        try:
                            response_data = resp.json()
                        except Exception:
                            response_data = {}

                        if response_data.get("ok"):
                            

                            return extract_yoinku_download(
                                response_data
                            )

                    except Exception:
                        continue

                return None, None

            (
                download_url,
                filename
            ) = await call_api_async(
                call_yoinku_download
            )

        # ====================================================
        # NO URL
        # ====================================================

        processing_stop.set()

        try:
            if processing_task is not None:
                await processing_task
        except Exception:
            pass
            
        if not download_url:

            await safe_edit_message(
                client,
                chat_id,
                message.id,
                (
                    "❌ <b>Failed to get "
                    "download URL.</b>\n\n"
                    f"API: "
                    f"<code>{html.escape(str(api_used))}</code>"
                ),
                enums.ParseMode.HTML
            )

            await log_to_channel(
                client,
                user_id,
                username,
                platform,
                api_used,
                "❌ No URL",
                url
            )

            return False

        # ====================================================
        # PERFORM YOUTUBE DOWNLOAD
        # ====================================================

        (
            success,
            size,
            error_reason
        ) = await perform_download(
            client,
            chat_id,
            message.id,
            download_url,
            "",
            filename,
            premium,
            user_id,
            platform,
            api_used,
            username,
            url
        )

        # ====================================================
        # CLEANUP QUALITY DATA
        # ====================================================

        yoinku_data.pop(
            user_id,
            None
        )

        # ====================================================
        # SUCCESS
        # ====================================================

        if success:

            update_platform_stats(
                platform
            )

            update_api_stats(
                api_used
            )

            await check_and_reward_referrals(
                client,
                user_id
            )

            await log_to_channel(
                client,
                user_id,
                username,
                platform,
                api_used,
                "✅ Success",
                url,
                format_size(size)
            )

            return True

        # ====================================================
        # FAILED
        # ====================================================

        await log_to_channel(
            client,
            user_id,
            username,
            platform,
            api_used,
            "❌ Download Failed",
            url,
            error=error_reason
        )

        await safe_edit_message(
            client,
            chat_id,
            message.id,
            (
                "❌ <b>Download failed!</b>\n\n"
                f"Reason: <code>"
                f"{html.escape(str(error_reason)[:200])}"
                f"</code>"
            ),
            enums.ParseMode.HTML
        )

        return False

    except Exception as e:

        processing_stop.set()

        try:
            await processing_task
        except Exception:
            pass

        error_reason = (
            f"{api_used} YouTube download error: "
            f"{str(e)[:200]}"
        )

        await log_to_channel(
            client,
            user_id,
            username,
            platform,
            api_used,
            "❌ Error",
            url,
            error=error_reason
        )

        await safe_edit_message(
            client,
            chat_id,
            message.id,
            (
                "❌ <b>YouTube download error:</b>\n"
                f"<code>"
                f"{html.escape(str(e)[:200])}"
                f"</code>"
            ),
            enums.ParseMode.HTML
        )

        return False


# ============================================================
# =================== TERABOX CALLBACK ======================
# ============================================================

async def handle_terabox_callback(
    client,
    callback_query,
    quality
):
    """
    ONLY TERABOX.
    """

    user_id = (
        callback_query.from_user.id
    )

    message = (
        callback_query.message
    )

    chat_id = (
        message.chat.id
    )

    tb_data = terabox_data.get(
        user_id,
        {}
    )

    if not tb_data:

        await safe_edit_message(
            client,
            chat_id,
            message.id,
            (
                "❌ <b>Session expired. "
                "Please try again.</b>"
            ),
            enums.ParseMode.HTML
        )

        return False

    await safe_edit_message(
        client,
        chat_id,
        message.id,
        "📥 <b>Starting download...</b>",
        enums.ParseMode.HTML
    )

    stream_urls = tb_data.get(
        "stream_urls",
        {}
    )

    download_url = stream_urls.get(
        quality
    )

    # Direct fallback.
    if not download_url:

        download_url = (
            tb_data.get(
                "file_info",
                {}
            ).get(
                "normal_dlink"
            )
        )

    if not download_url:

        await safe_edit_message(
            client,
            chat_id,
            message.id,
            (
                "❌ <b>No download URL found "
                "for this quality.</b>"
            ),
            enums.ParseMode.HTML
        )

        return False

    username = (
        callback_query.from_user.username
        or callback_query.from_user.first_name
        or "User"
    )

    (
        success,
        size,
        error_reason
    ) = await perform_download(
        client,
        chat_id,
        message.id,
        download_url,
        "",
        tb_data.get(
            "file_info",
            {}
        ).get(
            "name",
            "video"
        ),
        tb_data.get(
            "premium",
            False
        ),
        user_id,
        "TeraBox",
        "TeraBox API",
        username,
        tb_data.get(
            "url",
            ""
        )
    )

    url = tb_data.get(
        "url",
        ""
    )

    terabox_data.pop(
        user_id,
        None
    )

    if success:

        update_platform_stats(
            "TeraBox"
        )

        update_api_stats(
            "TeraBox API"
        )

        await check_and_reward_referrals(
            client,
            user_id
        )

        await log_to_channel(
            client,
            user_id,
            username,
            "TeraBox",
            "TeraBox API",
            "✅ Success",
            url,
            format_size(size)
        )

        return True

    await log_to_channel(
        client,
        user_id,
        username,
        "TeraBox",
        "TeraBox API",
        "❌ Download Failed",
        url,
        error=error_reason
    )

    await safe_edit_message(
        client,
        chat_id,
        message.id,
        (
            "❌ <b>Download failed!</b>\n\n"
            f"Reason: <code>"
            f"{html.escape(str(error_reason)[:200])}"
            f"</code>"
        ),
        enums.ParseMode.HTML
    )

    return False


# ============================================================
# ===================== COMMON CALLBACK ======================
# ============================================================

async def download_callback(
    client,
    callback_query
):
    """
    Callback dispatcher.

    Platform-specific processing ko separate functions
    me bheja gaya hai.
    """

    try:
        await callback_query.answer()
    except Exception:
        pass

    user_id = (
        callback_query.from_user.id
    )

    message = (
        callback_query.message
    )

    if not message:
        return

    chat_id = message.chat.id

    data = (
        callback_query.data
        or ""
    )

    # ========================================================
    # CANCEL
    # ========================================================

    if data == "dl_cancel":

        await safe_edit_message(
            client,
            chat_id,
            message.id,
            "❌ <b>Download cancelled.</b>",
            enums.ParseMode.HTML
        )

        yoinku_data.pop(
            user_id,
            None
        )

        terabox_data.pop(
            user_id,
            None
        )

        return


    # ========================================================
    # TERABOX DOWNLOAD
    # ========================================================

    if data == "tb_download":

        tb_data = terabox_data.get(user_id)

        if not tb_data:
            try:
                await callback_query.answer(
                    "❌ Session expired. Try again.",
                    show_alert=True
                )
            except Exception:
                pass
            return

        # Credit check (non-premium)
        if not tb_data.get("premium", False):
            from helper.credit import has_credits
            has = await has_credits(user_id, 1)
            if not has:
                try:
                    await callback_query.answer(
                        "❌ Insufficient credits!",
                        show_alert=True
                    )
                except Exception:
                    pass
                return
    
        username = (
            callback_query.from_user.username
            or callback_query.from_user.first_name
            or "User"
        )

        (
            success,
            size,
            error_reason
        ) = await perform_download(
            client,
            chat_id,
            message.id,
            tb_data["download_url"],
            "",
            tb_data["file_name"],
            tb_data.get("premium", False),
            user_id,
            "TeraBox",
            "TeraBox API",
            username,
            tb_data["url"]
        )

        url = tb_data.get("url", "")

        terabox_data.pop(user_id, None)

        if success:
            update_platform_stats("TeraBox")
            update_api_stats("TeraBox API")
            await check_and_reward_referrals(client, user_id)
            await log_to_channel(
                client, user_id, username,
                "TeraBox", "TeraBox API",
                "✅ Success", url,
                format_size(size)
            )
            return True

        await log_to_channel(
            client, user_id, username,
            "TeraBox", "TeraBox API",
            "❌ Download Failed", url,
            error=error_reason
        )

        await safe_edit_message(
            client, chat_id, message.id,
            (
                "❌ <b>Download failed!</b>\n\n"
                f"Reason: <code>"
                f"{html.escape(str(error_reason)[:200])}"
                f"</code>"
            ),
            enums.ParseMode.HTML
        )

        return
    # ========================================================
    # TERABOX
    # ========================================================

    if data.startswith(
        "tb_"
    ):

        quality = data.replace(
            "tb_",
            "",
            1
        )

        # Direct download button.
        if quality == "direct":

            tb_data = terabox_data.get(
                user_id,
                {}
            )

            if not tb_data:

                await safe_edit_message(
                    client,
                    chat_id,
                    message.id,
                    (
                        "❌ <b>Session expired. "
                        "Please try again.</b>"
                    ),
                    enums.ParseMode.HTML
                )

                return

            file_info = tb_data.get(
                "file_info",
                {}
            )

            quality = "__direct__"

            stream_urls = tb_data.get(
                "stream_urls",
                {}
            )

            download_url = (
                file_info.get(
                    "normal_dlink"
                )
            )

            if not download_url:

                await safe_edit_message(
                    client,
                    chat_id,
                    message.id,
                    "❌ <b>No direct URL found.</b>",
                    enums.ParseMode.HTML
                )

                return

            username = (
                callback_query.from_user.username
                or callback_query.from_user.first_name
                or "User"
            )

            await safe_edit_message(
                client,
                chat_id,
                message.id,
                "📥 <b>Starting download...</b>",
                enums.ParseMode.HTML
            )

            (
                success,
                size,
                error_reason
            ) = await perform_download(
                client,
                chat_id,
                message.id,
                download_url,
                "",
                file_info.get(
                    "name",
                    "video"
                ),
                tb_data.get(
                    "premium",
                    False
                ),
                user_id,
                "TeraBox",
                "TeraBox API",
                username,
                tb_data.get(
                    "url",
                    ""
                )
            )

            url = tb_data.get(
                "url",
                ""
            )

            terabox_data.pop(
                user_id,
                None
            )

            if success:

                update_platform_stats(
                    "TeraBox"
                )

                update_api_stats(
                    "TeraBox API"
                )

                await check_and_reward_referrals(
                    client,
                    user_id
                )

                await log_to_channel(
                    client,
                    user_id,
                    username,
                    "TeraBox",
                    "TeraBox API",
                    "✅ Success",
                    url,
                    format_size(size)
                )

            else:

                await log_to_channel(
                    client,
                    user_id,
                    username,
                    "TeraBox",
                    "TeraBox API",
                    "❌ Download Failed",
                    url,
                    error=error_reason
                )

            return

        await handle_terabox_callback(
            client,
            callback_query,
            quality
        )

        return

    # ========================================================
    # YOUTUBE / YOINKU QUALITY
    # ========================================================

    if data.startswith(
        "dl_"
    ):

        format_id = data.replace(
            "dl_",
            "",
            1
        )

        yt_data = yoinku_data.get(
            user_id,
            {}
        )

        if not yt_data:

            await safe_edit_message(
                client,
                chat_id,
                message.id,
                (
                    "❌ <b>Session expired. "
                    "Please try again.</b>"
                ),
                enums.ParseMode.HTML
            )

            return

        api_used = yt_data.get(
            "api_used",
            "Yoinku"
        )

        # YouTube-specific isolated code.
        if api_used == "FastSaver YouTube":

            await handle_youtube_callback(
                client,
                callback_query,
                format_id,
                yt_data
            )

            return

        # Yoinku YouTube / existing quality flow.
        await handle_youtube_callback(
            client,
            callback_query,
            format_id,
            yt_data
        )

        return


async def processing_animation(
    client,
    chat_id,
    message_id,
    stop_event
):
    words = [
        "🔍 ꜰᴇᴛᴄʜɪɴɢ",
        "🔎 ʀᴇꜱᴏʟᴠɪɴɢ",
        "⚙️ ᴘʀᴏᴄᴇꜱꜱɪɴɢ",
        "📡 ᴄᴏɴɴᴇᴄᴛɪɴɢ"
    ]

    dots = [
        ".",
        "..",
        "..."
    ]

    word_index = 0
    dot_index = 0

    while not stop_event.is_set():

        text = (
            f"{words[word_index]}"
            f"{dots[dot_index]}"
        )

        try:
            await safe_edit_message(
                client,
                chat_id,
                message_id,
                text,
                enums.ParseMode.HTML
            )
        except Exception:
            pass

        dot_index += 1

        if dot_index >= len(dots):
            dot_index = 0
            word_index = (
                word_index + 1
            ) % len(words)

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=0.5
            )
        except asyncio.TimeoutError:
            pass
# ============================================================
# =================== REGISTER HANDLERS ======================
# ============================================================

def register_downloader_handlers(app):

    app.add_handler(
        CallbackQueryHandler(
            download_callback,
            filters.regex(
                r"^dl_"
            )
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            download_callback,
            filters.regex(
                r"^tb_"
            )
        )
    )