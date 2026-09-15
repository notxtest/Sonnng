# config.py
"""
Bot Configuration
Saare hardcoded variables yahan aayenge.
"""

# ==================== TELEGRAM ====================

API_ID = 23640310
API_HASH = "079f8339732e35e032a64ee020e0b90b"

BOT_TOKEN = "8349697749:AAGWR30wW3263vN4yKG0OzHsbdK562dcRpw"
BOT_USERNAME = "Social_Media_Downloader_pro_Bot"


# ==================== ADMIN ====================

ADMIN_IDS = [7171541681]


# ==================== LOG CHANNEL ====================

LOG_CHANNEL_ID = -1003107521330


# ==================== DATABASE ====================

MONGO_URI = "mongodb+srv://rj5706603:O95nvJYxapyDHfkw@cluster0.fzmckei.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "downloader_bot"


# ==================== CONTACT ====================

CONTACT_ADMIN_URL = "https://t.me/cinevines_bot"


# ==================== PREMIUM ====================

PREMIUM_PRICE = "₹99/ᴍᴏɴᴛʜ"

PREMIUM_BENEFITS = (
    "✅ ᴜɴʟɪᴍɪᴛᴇᴅ ᴅᴏᴡɴʟᴏᴀᴅs\n"
    "✅ ɴᴏ ᴄʀᴇᴅɪᴛ ᴅᴇᴅᴜᴄᴛɪᴏɴ\n"
    "✅ ᴘʀɪᴏʀɪᴛʏ ᴘʀᴏᴄᴇssɪɴɢ\n"
    "✅ ɴᴏ ᴀᴅs"
)


# ==================== CREDIT ====================

CREDIT_COSTS = {
    "YouTube": 3,
    "Instagram": 1,
    "Facebook": 2,
    "TikTok": 2,
    "Pinterest": 1,
    "X/Twitter": 2,
    "TeraBox": 5,
}
DAILY_CLAIM_CREDITS = 3


# ==================== TIMEZONE ====================

TIMEZONE_OFFSET = 5.5 * 3600


# ==================== ADS (Watch & Earn) ====================

VPLINK_API = "ac446836edc44e309da1d158b069fc783e716c49"

MAX_ADS_PER_DAY = 5
ADS_REWARD = 20
AD_TIMER = 60


# ==================== REFERRAL ====================

REFERRAL_REWARD = 5
REFERRAL_DOWNLOADS_REQUIRED = 2