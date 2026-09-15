# helper/database.py

from pymongo import MongoClient

from config import (
    MONGO_URI,
    DB_NAME
)


# ==================== CONNECTION ====================

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000
)

db = client[DB_NAME]


# ==================== COLLECTIONS ====================

# User Collections
users_col = db["users"]
credits_col = db["credits"]
premium_col = db["premium"]


# Referral Collections
referrals_col = db["referrals"]


# FSUB Collections
fsub_collection = db["fsub_channels"]
join_requests_collection = db["join_requests"]
channel_users_collection = db["channel_users"]
pending_checks_collection = db["pending_checks"]
auto_delete_collection = db["auto_delete"]


# Broadcast Collection
broadcast_collection = db["broadcast_messages"]


# Ads Collections
ads_col = db["ads"]
tutorial_col = db["tutorial"]


# Stats Collection
stats_col = db["bot_stats"]


# ==================== TEST CONNECTION ====================

def test_connection():
    """Test MongoDB connection"""

    try:

        client.admin.command("ping")

        print(
            "✅ MongoDB connected successfully!"
        )

        return True

    except Exception as e:

        print(
            f"❌ MongoDB connection failed: {e}"
        )

        return False


# ==================== INIT DB ====================

def init_db():
    """Create indexes for better performance"""

    # ==================== USERS INDEXES ====================

    users_col.create_index(
        "username"
    )

    users_col.create_index(
        "referral_code"
    )

    users_col.create_index(
        "referred_by"
    )


    # ==================== CREDITS INDEXES ====================

    credits_col.create_index(
        "last_claim"
    )


    # ==================== PREMIUM INDEXES ====================

    premium_col.create_index(
        "expiry"
    )


    # ==================== REFERRALS INDEXES ====================

    referrals_col.create_index(
        "referrer_id"
    )

    referrals_col.create_index(
        "referred_id"
    )


    # ==================== FSUB INDEXES ====================

    fsub_collection.create_index(
        "channel_id"
    )


    # ==================== ADS INDEXES ====================

    ads_col.create_index(
        "user_id"
    )

    ads_col.create_index(
        "token"
    )

    ads_col.create_index(
        "expires_at"
    )

    ads_col.create_index(
        "date"
    )

    ads_col.create_index(
        "status"
    )


    # ==================== TUTORIAL INDEXES ====================

    tutorial_col.create_index(
        "set_at"
    )


    # ==================== BROADCAST INDEXES ====================

    broadcast_collection.create_index(
        "delete_after"
    )

    broadcast_collection.create_index(
        "user_id"
    )


    # ==================== AUTO DELETE INDEXES ====================

    auto_delete_collection.create_index(
        "delete_time"
    )


    print(
        "✅ Database indexes created!"
    )


# ==================== RUN INIT ====================

if __name__ == "__main__":

    test_connection()

    init_db()