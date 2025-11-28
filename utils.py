import re
import secrets
import asyncio
from pathlib import Path
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from config import *
from database import *

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
