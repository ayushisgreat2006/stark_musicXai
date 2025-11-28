import asyncio
import secrets
import aiofiles
from datetime import datetime
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import *
from database import *
from credits import *
from utils import *
import logging

log = logging.getLogger("ytbot")

async def download_and_send(chat_id, reply_msg, context, url, quality):
    user_id = reply_msg.chat.id
    download_id = f"{user_id}_{secrets.token_urlsafe(8)}"
    
    try:
        status_msg = await reply_msg.reply_text("⏳ Preparing download...")
        
        ydl_opts = get_ytdl_options(quality, download_id)
        await status_msg.edit_text("⬇️ Downloading from YouTube...")
        
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            title = sanitize_filename(info.get("title", "video"))

        ext = ".mp3" if quality == "mp3" else ".mp4"
        files = sorted(DOWNLOAD_DIR.glob(f"*{download_id}{ext}"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if not files:
            await status_msg.edit_text("⚠️ File not found after download.")
            return

        final_path = files[0]
        file_size = final_path.stat().st_size
        is_user_premium = is_premium(user_id)

        # Size limit checks
        if file_size > MAX_FREE_SIZE and not is_user_premium:
            final_path.unlink()
            premium_msg = (
                f"❌ <b>File too large!</b>\n\n"
                f"📦 Size: {file_size / 1024 / 1024:.1f}MB\n"
                f"💳 Free limit: {MAX_FREE_SIZE / 1024 / 1024}MB\n\n"
                f"👉 Contact {PREMIUM_BOT_USERNAME} to subscribe premium!"
            )
            await status_msg.edit_text(premium_msg, parse_mode=ParseMode.HTML)
            return

        if file_size > PREMIUM_SIZE:
            final_path.unlink()
            await status_msg.edit_text("❌ File exceeds maximum size (450MB). Try lower quality.")
            return

        caption = f"📥 <b>{title}</b> ({file_size/1024/1024:.1f}MB)\n\nDownloaded by @spotifyxmusixbot"
        await status_msg.edit_text("⬆️ Uploading to Telegram...")
        
        async with aiofiles.open(final_path, 'rb') as f:
            file_data = await f.read()
        
        # Capture response message for forwarding
        if quality == "mp3":
            response_msg = await reply_msg.reply_document(
                document=file_data,
                caption=caption,
                filename=f"{title}.mp3",
                parse_mode=ParseMode.HTML,
                connect_timeout=60,
                read_timeout=60,
                write_timeout=60
            )
        else:
            response_msg = await reply_msg.reply_video(
                video=file_data,
                caption=caption,
                filename=f"{title}.mp4",
                supports_streaming=True,
                parse_mode=ParseMode.HTML,
                connect_timeout=60,
                read_timeout=60,
                write_timeout=60
            )
        
        await status_msg.delete()
        
        # Add lyrics button for MP3
        if quality == "mp3":
            lyrics_button = InlineKeyboardButton("📝 Get Lyrics", callback_data=f"lyrics|{title}")
            keyboard = InlineKeyboardMarkup([[lyrics_button]])
            await reply_msg.reply_text(
                "🎵 Download complete! Click below to get lyrics:",
                reply_markup=keyboard
            )
        
        # NEW: Forward messages to log group
        await log_to_group(
            update=None,
            context=context,
            action="Download Success",
            details=f"User {user_id}: {title[:50]}",
            original_message=reply_msg,
            response_message=response_msg
        )
            
    except Exception as e:
        error_msg = f"⚠️ Error: {str(e)[:100]}"
        await reply_msg.reply_text(error_msg)
        log.error(f"Download failed: {e}", exc_info=True)
    
    finally:
        final_path.unlink(missing_ok=True)
        cleanup_old_files()
