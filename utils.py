import re
import secrets
import asyncio
from pathlib import Path
from datetime import datetime
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from config import *
from database import *
import logging

log = logging.getLogger("ytbot")

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "output"

def store_url(url: str) -> str:
    token = secrets.token_urlsafe(16)
    PENDING[token] = {"url": url, "exp": asyncio.get_event_loop().time() + 3600}
    return token

def cleanup_old_files():
    try:
        all_files = sorted(DOWNLOAD_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in all_files[10:]:
            f.unlink()
    except:
        pass

def get_ytdl_options(quality: str, download_id: str) -> dict:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": str(DOWNLOAD_DIR / f"%(title)s_{download_id}.%(ext)s"),
    }
    
    cookies_path = Path(COOKIES_FILE)
    if cookies_path.exists() and cookies_path.stat().st_size > 0:
        ydl_opts["cookiefile"] = str(cookies_path)
    
    if quality == "mp3":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts.update({
            "format": f"bestvideo[height<={quality}][vcodec^=avc][ext=mp4]+bestaudio[acodec^=mp4a][ext=m4a]/best[height<={quality}][ext=mp4]",
            "merge_output_format": "mp4",
            "postprocessor_args": {
                "MOV+FFmpegVideoConvertor+mp4": [
                    "-movflags", "+faststart",
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-preset", "faster",
                    "-crf", "23"
                ]
            }
        })
    
    return ydl_opts

def quality_keyboard(url: str) -> InlineKeyboardMarkup:
    token = store_url(url)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"q|{token}|mp3")],
        [InlineKeyboardButton("🎬 360p", callback_data=f"q|{token}|360")],
        [InlineKeyboardButton("🎬 480p", callback_data=f"q|{token}|480")],
        [InlineKeyboardButton("🎬 720p", callback_data=f"q|{token}|720")],
        [InlineKeyboardButton("🎬 1080p", callback_data=f"q|{token}|1080")],
    ])

def is_owner(user_id: int) -> bool:
    return int(user_id) == OWNER_ID

def is_admin(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    if not MONGO_AVAILABLE or admins_col is None:
        return False
    try:
        return admins_col.find_one({"_id": user_id}) is not None
    except:
        return False

def is_premium(user_id: int) -> bool:
    if not MONGO_AVAILABLE or users_col is None:
        return False
    try:
        user = users_col.find_one({"_id": user_id}, {"premium": 1})
        return user.get("premium", False) if user else False
    except:
        return False

def ensure_user(update: Update):
    """Track user in database"""
    if not MONGO_AVAILABLE or update.effective_user is None:
        return
    
    try:
        u = update.effective_user
        users_col.update_one(
            {"_id": u.id},
            {
                "$set": {
                    "name": u.full_name or u.username or str(u.id),
                    "username": u.username,
                },
                "$setOnInsert": {
                    "credits": BASE_CREDITS,
                    "daily_usage": 0,
                    "last_usage_date": get_today_str(),
                    "video_gen_limit": BASE_VIDEO_GEN_LIMIT,
                    "video_gen_today": 0,
                    "video_gen_date": get_today_str(),
                    "referrals_made": 0,
                    "first_seen": datetime.now(),
                }
            },
            upsert=True
        )
    except Exception as e:
        log.error(f"User tracking failed: {e}")

async def ensure_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not FORCE_JOIN_CHANNEL:
        return True
    
    # Only enforce in groups if bot is mentioned
    if update.message and update.message.chat.type in ["group", "supergroup"]:
        if not (update.message.text and f"@{context.bot.username}" in update.message.text):
            return True
    
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(
            chat_id=FORCE_JOIN_CHANNEL,
            user_id=user_id
        )
        if member.status not in ["left", "kicked"]:
            return True
    except Exception as e:
        log.error(f"Membership check failed: {e}")
        await update.message.reply_text("❌ Could not verify membership. Try again.")
        return False
    
    channel_username = FORCE_JOIN_CHANNEL.replace('@', '')
    join_url = f"https://t.me/{channel_username}"
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Join Channel 🔔", url=join_url),
        InlineKeyboardButton("✅ Verify", callback_data="verify_membership")
    ]])
    
    await update.message.reply_text(
        f"⚠️ <b>You must join {FORCE_JOIN_CHANNEL} to use this bot!</b>\n\n"
        f"Please join and click 'Verify'.",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    return False

async def log_to_group(
    update: Optional[Update], 
    context: ContextTypes.DEFAULT_TYPE, 
    action: str, 
    details: str = "", 
    user_id: Optional[int] = None, 
    is_error: bool = False,
    original_message: Optional[Message] = None,
    response_message: Optional[Message] = None
):
    """
    Log activity to log group with dual functionality:
    1. Original text logging (kept)
    2. Message forwarding (NEW)
    """
    if not LOG_GROUP_ID:
        return
        
    try:
        # NEW: Forward messages if provided
        forwarded_any = False
        
        if original_message:
            await context.bot.forward_message(
                chat_id=LOG_GROUP_ID,
                from_chat_id=original_message.chat_id,
                message_id=original_message.message_id
            )
            forwarded_any = True
        
        if response_message:
            await context.bot.forward_message(
                chat_id=LOG_GROUP_ID,
                from_chat_id=response_message.chat_id,
                message_id=response_message.message_id
            )
            forwarded_any = True
        
        # Keep original text logging for non-media actions
        if not forwarded_any:
            user = update.effective_user if update and update.effective_user else None
            user_info = f"👤 User: {user.full_name or user.username or 'Unknown'} (<code>{user.id}</code>)" if user else ""
            
            action_info = f"🎯 Action: {action}"
            details_info = f"📄 Details: {details}" if details else ""
            
            log_text = (
                f"❌ <b>ERROR LOG</b>\n\n{user_info}\n{action_info}\n{details_info}\n\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ) if is_error else (
                f"✅ <b>ACTIVITY LOG</b>\n\n{user_info}\n{action_info}\n{details_info}\n\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await context.bot.send_message(
                chat_id=LOG_GROUP_ID,
                text=log_text,
                parse_mode=ParseMode.HTML
            )
        
        log.info(f"✅ Log sent to group {LOG_GROUP_ID}")
        
    except Exception as e:
        log.error(f"❌ Failed to send log to group {LOG_GROUP_ID}: {e}")

async def fetch_lyrics(song_title: str) -> Optional[str]:
    """Fetch lyrics for a song title using an external API"""
    try:
        clean_title = re.sub(r'\(official.*?\)|\[official.*?\]|\(audio\)|\[audio\]|\(lyric.*?\)|\[lyric.*?\]|\(video.*?\)|\[video.*?\]|\(hd\)|\[hd\]|\(4k\)|\[4k\]|\(feat\..*?\)|\[feat\..*?\]', '', song_title, flags=re.IGNORECASE)
        clean_title = re.sub(r'[–—|-]', ' ', clean_title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        api_url = f"https://api.maher-zubair.tech/lyrics?q={clean_title}"

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == 200 and data.get("result"):
                        return data["result"]
    except Exception as e:
        log.error(f"Failed to fetch lyrics for '{song_title}': {e}")

    return None
