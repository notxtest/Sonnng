import asyncio
import logging
import dns.resolver
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# ==================== TERMUX MONGODB DNS FIX ====================
try:
    dns.resolver.default_resolver = dns.resolver.Resolver(
        "/data/data/com.termux/files/usr/etc/resolv.conf"
    )
except Exception:
    pass
    
# ==================== PYROGRAM IMPORTS ====================
from pyrogram import Client, filters, idle, enums
from pyrogram.handlers import MessageHandler

# ==================== PARSE MODE COMPATIBILITY ====================
from pyrogram import enums
_original_parser_parse = None
try:
    from pyrogram.parser import Parser
    _original_parser_parse = Parser.parse
    
    async def _parse_compat(self, text, mode=None):
        if isinstance(mode, str):
            try:
                mode = enums.ParseMode(mode.lower())
            except ValueError:
                pass

        return await _original_parser_parse(self, text, mode)

    Parser.parse = _parse_compat
    print("✅ ParseMode compatibility patch applied")

except Exception as e:
    print(f"⚠️ ParseMode compatibility patch failed: {e}")
    
# ================================================================
# PYTHON 3.14 + PYROGRAM 2.3.50 IDENTIFIER COMPATIBILITY PATCH
# ================================================================
try:
    from pyrogram.types.pyromod.identifier import Identifier
    _IDENTIFIER_FIELDS = tuple(
        getattr(
            Identifier,
            "__annotations__",
            {}
        ).keys()
    )
    
    def _identifier_matches(self, update):
        for field in _IDENTIFIER_FIELDS:
            pattern_value = getattr(
                self,
                field,
                None
            )

            update_value = getattr(
                update,
                field,
                None
            )

            if pattern_value is not None:
                if isinstance(update_value, list):
                    if isinstance(pattern_value, list):
                        if not set(update_value).intersection(
                            set(pattern_value)
                        ):
                            return False

                    elif pattern_value not in update_value:
                        return False
                elif isinstance(pattern_value, list):
                    if update_value not in pattern_value:
                        return False
                elif update_value != pattern_value:
                    return False
        return True

    def _identifier_count_populated(self):
        count = 0
        for field in _IDENTIFIER_FIELDS:
            if getattr(
                self,
                field,
                None
            ) is not None:

                count += 1
        return count

    Identifier.matches = _identifier_matches
    Identifier.count_populated = _identifier_count_populated
    print(
        "✅ Pyrogram Identifier compatibility patch applied"
    )

except Exception as e:
    print(
        f"⚠️ Identifier compatibility patch skipped: {e}"
    )

# ================================================================
# PYROGRAM PARSE MODE COMPATIBILITY PATCH
# ================================================================




# ==================== CONFIG ====================
from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN
)

# ==================== DATABASE ====================
from helper.database import (
    test_connection,
    init_db
)

# ==================== HANDLERS ====================
from helper.start import (
    register_start_handlers
)
from helper.credit import (
    register_credit_handlers
)
from helper.premium import (
    register_premium_handlers
)
from helper.referral import (
    register_refer_handlers
)
from helper.ads import (
    register_ads_handlers
)
from helper.fsub import (
    register_fsub_handlers
)
from helper.stats import (
    register_stats_handlers
)
from helper.broadcast import (
    register_broadcast_handlers,
    start_broadcast_cleanup
)
from helper.downloader import (
    register_downloader_handlers
)
from helper.manager import (
    handle_url
)
from helper.ping import (
    register_ping_handlers
)
# ==================== LOGGING ====================
logging.basicConfig(
    format=(
        "%(asctime)s - "
        "%(name)s - "
        "%(levelname)s - "
        "%(message)s"
    ),
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
# ==================== DISK STORAGE SETUP ====================
import os
import time
import glob
_BOT_ROOT = os.path.dirname(os.path.abspath(__file__))

TEMP_DOWNLOAD_DIR = os.path.join(_BOT_ROOT, "temp_downloads")
THUMBNAIL_DIR = os.path.join(_BOT_ROOT, "thumbnails")
CACHE_DIR = os.path.join(_BOT_ROOT, "cache")

os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

print(f"📁 Temp: {TEMP_DOWNLOAD_DIR}")
print(f"📁 Thumbs: {THUMBNAIL_DIR}")

def cleanup_disk_cache(max_age_seconds=3600):
    """1 ghante se purani files delete karo"""
    now = time.time()
    total = 0

    for folder in [TEMP_DOWNLOAD_DIR, THUMBNAIL_DIR, CACHE_DIR]:
        try:
            for filepath in glob.glob(os.path.join(folder, "*")):
                try:
                    if os.path.isfile(filepath):
                        age = now - os.path.getmtime(filepath)
                        if age > max_age_seconds:
                            os.remove(filepath)
                            total += 1
                except Exception:
                    pass
        except Exception:
            pass
    if total > 0:
        print(f"🧹 Cleaned {total} old files")

async def disk_cleanup_loop():
    """Har 30 minute me cleanup"""
    while True:
        try:
            cleanup_disk_cache(max_age_seconds=3600)
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")

        await asyncio.sleep(1800)

# ==================== MAIN ====================
async def main():
    # ============================================================
    # MONGODB CHECK
    # ============================================================
    print("\n🔄 Checking MongoDB...")
    try:
        if not test_connection():
            print(
                "❌ MongoDB connection failed!"
            )
            return
        print(
            "✅ MongoDB connected successfully!"
        )
    except Exception as e:
        print(
            f"❌ MongoDB error: {e}"
        )
        return

    # ============================================================
    # DATABASE INITIALIZATION
    # ============================================================
    try:
        init_db()
        print(
            "✅ Database ready!"
        )
    except Exception as e:
        print(
            f"❌ Database initialization failed: {e}"
        )
        return

    # ============================================================
    # STARTUP DISK CLEANUP
    # ============================================================
    print("🧹 Running startup disk cleanup...")
    cleanup_disk_cache(max_age_seconds=3600)
    print("✅ Startup cleanup done")

    # ============================================================
    # PYROGRAM CLIENT
    # ============================================================
    app = Client(
        "file_downloader_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        no_updates=False,
    )

    # ============================================================
    # REGISTER HANDLERS
    # ============================================================
    print(
        "\n=============================="
    )
    print(
        "📌 REGISTERING HANDLERS"
    )
    print(
        "=============================="
    )
    
    # ==================== START ====================
    try:
        register_start_handlers(app)
    except Exception as e:
        print(
            f"❌ Start handlers failed: {e}"
        )
        return

    # ==================== CREDIT ====================
    try:
        register_credit_handlers(app)
    except Exception as e:
        print(
            f"❌ Credit handlers failed: {e}"
        )
        return

    # ==================== PREMIUM ====================
    try:
        register_premium_handlers(app)
    except Exception as e:
        print(
            f"❌ Premium handlers failed: {e}"
        )
        return

    # ==================== REFERRAL ====================
    try:
        register_refer_handlers(app)
    except Exception as e:
        print(
            f"❌ Referral handlers failed: {e}"
        )
        return

    # ==================== ADS ====================
    try:
        register_ads_handlers(app)
    except Exception as e:
        print(
            f"❌ Ads handlers failed: {e}"
        )
        return

    # ==================== FSUB ====================
    try:
        register_fsub_handlers(app)
    except Exception as e:
        print(
            f"❌ FSUB handlers failed: {e}"
        )
        return

    # ==================== STATS ====================
    try:
        register_stats_handlers(app)
    except Exception as e:
        print(
            f"❌ Stats handlers failed: {e}"
        )
        return

    # ==================== BROADCAST ====================
    try:
        register_broadcast_handlers(app)
    except Exception as e:
        print(
            f"❌ Broadcast handlers failed: {e}"
        )
        return

    # ==================== DOWNLOADER ====================
    try:
        register_downloader_handlers(app)
    except Exception as e:
        print(
            f"❌ Downloader handlers failed: {e}"
        )
        return

    # ============================================================
    # MANAGER / URL HANDLER
    # ============================================================
    try:
        async def debug_handle_url(
            client,
            message
        ):
            print(
                "\n🔗 URL HANDLER TRIGGERED"
            )
            print(
                f"👤 User: "
                f"{message.from_user.id if message.from_user else 'None'}"
            )
            print(
                f"💬 Text: "
                f"{message.text!r}"
            )
            try:
                await handle_url(
                    client,
                    message
                )
                print(
                    "✅ URL HANDLER FINISHED"
                )
            except Exception as e:
                print(
                    "\n❌ URL HANDLER ERROR"
                )
                print(
                    f"Type: {type(e).__name__}"
                )
                print(
                    f"Error: {e}"
                )
                logger.exception(
                    "URL handler exception"
                )

        app.add_handler(
            MessageHandler(
                debug_handle_url,
                filters.text
                & ~filters.regex(r"^/")
            ),
            group=0,
        )
        print(
            "✅ Manager (URL) handler registered [GROUP 0]"
        )
    except Exception as e:
        print(
            f"❌ Manager handler failed: {e}"
        )
        return
     
     # ==================== PING ====================
    try:
        register_ping_handlers(app)
    except Exception as e:
        print(
            f"❌ Ping handlers failed: {e}"
        )
        return
    # ============================================================
    # ALL HANDLERS REGISTERED
    # ============================================================
    print(
        "=============================="
    )
    print(
        "✅ ALL HANDLERS REGISTERED"
    )
    print(
        "==============================\n"
    )

    # ============================================================
    # START PYROGRAM
    # ============================================================
    print(
        "🔄 Starting Pyrogram..."
    )
    try:
        await app.start()
    except Exception as e:
        print(
            f"❌ Failed to start bot: {e}"
        )
        try:
            await app.stop()
        except Exception:
            pass
        return

    # ============================================================
    # BOT INFORMATION
    # ============================================================
    try:
        me = await app.get_me()
        print(
            "\n=============================="
        )
        print(
            "🤖 CONNECTED BOT"
        )
        print(
            "=============================="
        )
        print(
            f"ID: {me.id}"
        )
        print(
            f"USERNAME: @{me.username}"
        )
        print(
            f"NAME: {me.first_name}"
        )
        print(
            "=============================="
        )
    except Exception as e:
        print(
            f"⚠️ Could not fetch bot info: {e}"
        )

    # ============================================================
    # BROADCAST CLEANUP
    # ============================================================
    cleanup_task = None
    try:
        cleanup_task = asyncio.create_task(
            start_broadcast_cleanup(app)
        )
        print(
            "✅ Broadcast cleanup task started"
        )
    except Exception as e:
        print(
            f"⚠️ Cleanup task failed to start: {e}"
        )

    # ============================================================
    # DISK CLEANUP TASK
    # ============================================================
    disk_cleanup_task = None
    try:
        disk_cleanup_task = asyncio.create_task(
            disk_cleanup_loop()
        )
        print(
            "✅ Disk cleanup task started"
        )
    except Exception as e:
        print(
            f"⚠️ Disk cleanup task failed: {e}"
        )

    # ============================================================
    # BOT RUNNING
    # ============================================================
    print(
        "\n🚀 Bot started successfully!"
    )
    print(
        "📡 Waiting for Telegram updates...\n"
    )

    # ============================================================
    # IDLE
    # ============================================================
    try:
        await idle()
    except KeyboardInterrupt:
        print(
            "\n🛑 Keyboard interrupt received"
        )
    except Exception as e:
        print(
            f"\n❌ Idle error: {e}"
        )

    # ============================================================
    # CLEANUP TASK STOP
    # ============================================================
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    if disk_cleanup_task:
        disk_cleanup_task.cancel()
        try:
            await disk_cleanup_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    # ============================================================
    # STOP BOT
    # ============================================================
    try:
        await app.stop()
        print(
            "🛑 Bot stopped successfully"
        )
    except Exception as e:
        print(
            f"⚠️ Error stopping bot: {e}"
        )

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    try:
        asyncio.run(
            main()
        )
    except KeyboardInterrupt:
        print(
            "\n🛑 Bot stopped by user"
        )
    except Exception as e:
        print(
            f"\n❌ Fatal error: {e}"
        )