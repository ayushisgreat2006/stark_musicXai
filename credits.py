from datetime import datetime
from database import *
from config import *

def get_today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

# AI/GPT Credits (existing)
async def get_user_credits(user_id: int) -> tuple[int, int, bool]:
    if not MONGO_AVAILABLE:
        return BASE_CREDITS, 0, False
    
    if is_admin(user_id):
        return 99999, 0, True
    
    today = get_today_str()
    whitelist_entry = whitelist_col.find_one({"_id": user_id}) if whitelist_col else None
    if whitelist_entry:
        limit = whitelist_entry.get("daily_limit", BASE_CREDITS)
        last_date = whitelist_entry.get("last_usage_date", today)
        used = whitelist_entry.get("daily_usage", 0) if last_date == today else 0
        return limit, used, True
    
    user = users_col.find_one({"_id": user_id}, {"credits": 1, "daily_usage": 1, "last_usage_date": 1})
    if not user:
        return BASE_CREDITS, 0, False
    
    last_date = user.get("last_usage_date", today)
    if last_date != today:
        users_col.update_one(
            {"_id": user_id},
            {"$set": {"daily_usage": 0, "last_usage_date": today}}
        )
        return user.get("credits", BASE_CREDITS), 0, False
    
    return user.get("credits", BASE_CREDITS), user.get("daily_usage", 0), False

async def consume_credit(user_id: int) -> bool:
    if not MONGO_AVAILABLE or is_admin(user_id):
        return True
    
    credits, used, is_whitelisted = await get_user_credits(user_id)
    if used >= credits:
        return False
    
    today = get_today_str()
    update_fields = {"$inc": {"daily_usage": 1}}
    
    if is_whitelisted:
        whitelist_col.update_one(
            {"_id": user_id},
            {**update_fields, "$set": {"last_usage_date": today}},
            upsert=True
        )
    else:
        users_col.update_one(
            {"_id": user_id},
            {**update_fields, "$set": {"last_usage_date": today}},
            upsert=True
        )
    
    return True

# Video Generation Credits (NEW)
async def get_user_video_credits(user_id: int) -> tuple[int, int]:
    """Returns (limit, used_today) for video generation"""
    if not MONGO_AVAILABLE:
        return BASE_VIDEO_GEN_LIMIT, 0
    
    if is_admin(user_id):
        return ADMIN_VIDEO_GEN_LIMIT, 0
    
    today = get_today_str()
    user = users_col.find_one({"_id": user_id}, {
        "video_gen_limit": 1, 
        "video_gen_today": 1, 
        "video_gen_date": 1
    })
    
    if not user:
        return BASE_VIDEO_GEN_LIMIT, 0
    
    last_date = user.get("video_gen_date", today)
    if last_date != today:
        users_col.update_one(
            {"_id": user_id},
            {"$set": {"video_gen_today": 0, "video_gen_date": today}}
        )
        return user.get("video_gen_limit", BASE_VIDEO_GEN_LIMIT), 0
    
    return (
        user.get("video_gen_limit", BASE_VIDEO_GEN_LIMIT), 
        user.get("video_gen_today", 0)
    )

async def consume_video_credit(user_id: int) -> bool:
    """Consume 1 video credit"""
    if not MONGO_AVAILABLE or is_admin(user_id):
        return True
    
    limit, used = await get_user_video_credits(user_id)
    if used >= limit:
        return False
    
    today = get_today_str()
    users_col.update_one(
        {"_id": user_id},
        {"$inc": {"video_gen_today": 1}, "$set": {"video_gen_date": today}},
        upsert=True
    )
    
    return True

async def add_video_credits(user_id: int, amount: int) -> bool:
    """Add video generation credits to user"""
    if not MONGO_AVAILABLE:
        return False
    
    try:
        # Increase the limit (not consumed credits)
        users_col.update_one(
            {"_id": user_id},
            {"$inc": {"video_gen_limit": amount}},
            upsert=True
        )
        return True
    except Exception as e:
        return False
