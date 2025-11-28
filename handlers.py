import asyncio
import secrets
import aiofiles
from datetime import datetime
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from config import *
from database import *
from credits import *
from utils import *
from downloader import download_and_send
from ai_clients import groq_client, GeminiGenAPI, parse_netscape_cookies
import logging

log = logging.getLogger("ytbot")

# =========================
# Command Handlers
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    
    if not await ensure_membership(update, context):
        return
    
    # Store chat ID for broadcast
    if MONGO_AVAILABLE and update.message.chat.type in ["group", "supergroup", "channel"]:
        try:
            db["broadcast_chats"].update_one(
                {"_id": update.message.chat.id},
                {"$set": {
                    "title": update.message.chat.title,
                    "type": update.message.chat.type,
                    "added_at": datetime.now()
                }},
                upsert=True
            )
        except:
            pass
    
    # Check cookies status
    cookies_path = Path(COOKIES_FILE)
    cookies_working = cookies_path.exists() and cookies_path.stat().st_size > 0
    
    start_text = (
        "<b>🎧 Welcome to SpotifyX Musix Bot 🎧</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>🔥 Features:</b>\n"
        "• Download MP3 music 🎧\n"
        "• Download Videos (360p-1080p) 🎬\n"
        "• Search YouTube 🔍\n"
        "• Generate AI images 🎨\n"
        "• Generate AI videos 🎬\n"
        "• AI Chat with Groq 💬\n"
        "• Get song lyrics 📝\n"
        "• Premium: Up to 450MB files 💳\n\n"
        f"<b>💳 AI Credits:</b> {BASE_CREDITS} queries/day\n"
        f"<b>🎬 Video Credits:</b> {BASE_VIDEO_GEN_LIMIT} videos/day\n"
        f"<b>🎁 Refer:</b> /refer to earn more\n\n"
        f"<b>📌 Cookies Status:</b> {'✅ Working' if cookies_working else '❌ Not configured'}\n"
        f"<b>📌 Use /help for commands</b>\n\n"
        "<b>⚠️ YouTube Notice:</b> If search fails, cookies may need refresh. Use /testcookies"
    )
    
    response_msg = await update.message.reply_text(start_text, parse_mode=ParseMode.HTML)
    
    # NEW: Forward to log group
    await log_to_group(
        update=update,
        context=context,
        action="/start",
        details="User started bot",
        original_message=update.message,
        response_message=response_msg
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    
    ai_status = "✅" if groq_client else "❌"
    cookies_path = Path(COOKIES_FILE)
    cookies_working = cookies_path.exists() and cookies_path.stat().st_size > 0
    
    help_text = (
        "<b>✨ SpotifyX Musix Bot — Commands ✨</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>User Commands:</b>\n"
        "<code>/start</code> — Start bot\n"
        "<code>/help</code> — Show help\n"
        "<code>/search &lt;name&gt;</code> — Search YouTube\n"
        "<code>/lyrics &lt;song&gt;</code> — Get song lyrics 📝\n"
        "<code>/gen &lt;prompt&gt;</code> — Generate AI image\n"
        "<code>/vdogen &lt;prompt&gt;</code> — Generate AI video 🎬\n"
        "<code>/gpt &lt;query&gt;</code> — Chat with AI (20/day)\n"
        "<code>/refer</code> — Generate referral code\n"
        "<code>/claim &lt;code&gt;</code> — Claim referral\n"
        "<code>/vdoredeem &lt;code&gt;</code> — Redeem video credits (NEW!)\n"
        "<code>/credits</code> — Check your balances\n\n"
        "<b>Admin Commands:</b>\n"
        "<code>/stats</code> — View statistics\n"
        "<code>/broadcast</code> — Broadcast message\n"
        "<code>/adminlist</code> — List admins\n"
        "<code>/gen_redeem &lt;value&gt; &lt;code&gt;</code> — Generate AI credit code\n"
        "<code>/genvdo_redeem &lt;value&gt; &lt;code&gt;</code> — Generate video credit code (NEW!)\n"
        "<code>/whitelist_ai &lt;id&gt; &lt;value&gt;</code> — Whitelist for AI\n"
        "<code>/whitelist_vdo &lt;id&gt; &lt;value&gt;</code> — Whitelist for video (NEW!)\n"
        "<code>/testcookies</code> — Test YouTube cookies\n\n"
        "<b>Owner Commands:</b>\n"
        "<code>/addadmin &lt;id&gt;</code> — Add admin\n"
        "<code>/rmadmin &lt;id&gt;</code> — Remove admin\n\n"
        f"<b>Updates:</b> {UPDATES_CHANNEL}\n"
        f"<b>Support:</b> {PREMIUM_BOT_USERNAME}\n\n"
        f"<b>AI Status:</b> {ai_status} {'Configured' if groq_client else 'Not Set'}\n"
        f"<b>Cookies Status:</b> {'✅ Working' if cookies_working else '❌ Not configured'}"
    )
    
    response_msg = await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    
    await log_to_group(
        update=update,
        context=context,
        action="/help",
        original_message=update.message,
        response_message=response_msg
    )

async def credits_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check user's credit balances"""
    ensure_user(update)
    user_id = update.effective_user.id
    
    # AI Credits
    ai_credits, ai_used, is_whitelisted = await get_user_credits(user_id)
    ai_remaining = ai_credits - ai_used
    
    # Video Credits
    vdo_limit, vdo_used = await get_user_video_credits(user_id)
    vdo_remaining = vdo_limit - vdo_used
    
    status = "👑 Whitelisted" if is_whitelisted else "🎫 Regular User"
    
    credits_text = (
        f"💳 <b>Your Credit Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Status: {status}\n\n"
        f"<b>🤖 AI Credits:</b>\n"
        f"📊 Daily Limit: {ai_credits}\n"
        f"✅ Used Today: {ai_used}\n"
        f"🎁 Remaining: {ai_remaining}\n\n"
        f"<b>🎬 Video Credits:</b>\n"
        f"📊 Daily Limit: {vdo_limit}\n"
        f"✅ Used Today: {vdo_used}\n"
        f"🎁 Remaining: {vdo_remaining}\n\n"
        f"<b>Want more?</b>\n"
        f"• /refer - Earn {REFERRER_BONUS} AI credits\n"
        f"• /vdoredeem - Redeem video credit codes\n"
        f"• Contact {PREMIUM_BOT_USERNAME} for premium"
    )
    
    response_msg = await update.message.reply_text(credits_text, parse_mode=ParseMode.HTML)
    
    await log_to_group(
        update=update,
        context=context,
        action="/credits",
        original_message=update.message,
        response_message=response_msg
    )

async def refer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate referral code"""
    ensure_user(update)
    user_id = update.effective_user.id
    
    if not MONGO_AVAILABLE:
        await update.message.reply_text("❌ Database not available.")
        return
    
    code = secrets.token_urlsafe(12).upper()
    
    try:
        users_col.update_one(
            {"_id": user_id},
            {"$set": {"referral_code": code}},
            upsert=True
        )
        
        response_msg = await update.message.reply_text(
            f"🎁 <b>Your Referral Code</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<code>{code}</code>\n\n"
            f"<b>Share this code!</b>\n"
            f"• You get +{REFERRER_BONUS} AI credits when someone uses it\n"
            f"• They get +{CLAIMER_BONUS} AI credits\n\n"
            f"Use: /claim {code}",
            parse_mode=ParseMode.HTML
        )
        
        await log_to_group(
            update=update,
            context=context,
            action="/refer",
            details=f"Generated code: {code[:10]}...",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

async def claim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim a referral code"""
    ensure_user(update)
    
    if not context.args:
        await update.message.reply_text("Usage: /claim <referral_code>")
        return
    
    if not MONGO_AVAILABLE:
        await update.message.reply_text("❌ Database not available.")
        return
    
    code = context.args[0].strip().upper()
    user_id = update.effective_user.id
    
    try:
        referrer = users_col.find_one({"referral_code": code})
        if not referrer:
            await update.message.reply_text("❌ Invalid referral code!")
            return
        
        referrer_id = referrer["_id"]
        if referrer_id == user_id:
            await update.message.reply_text("❌ You cannot use your own code!")
            return
        
        claimed = users_col.find_one({"_id": user_id, f"claimed_codes.{code}": {"$exists": True}})
        if claimed:
            await update.message.reply_text("❌ You already claimed this code!")
            return
        
        # Give bonuses
        users_col.update_one(
            {"_id": referrer_id},
            {"$inc": {"credits": REFERRER_BONUS, "referrals_made": 1}}
        )
        
        await add_credits(user_id, CLAIMER_BONUS)
        
        users_col.update_one(
            {"_id": user_id},
            {"$set": {f"claimed_codes.{code}": datetime.now()}}
        )
        
        # NEW: Notify both users
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 <b>Referral Used!</b>\n\nUser {user_id} used your code!\n✅ You earned +{REFERRER_BONUS} AI credits",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        
        response_msg = await update.message.reply_text(
            f"🎉 <b>Success!</b>\n\n"
            f"✅ You earned +{CLAIMER_BONUS} AI credits\n"
            f"📊 Your referrer got +{REFERRER_BONUS} AI credits\n\n"
            f"Use /credits to check balance",
            parse_mode=ParseMode.HTML
        )
        
        await log_to_group(
            update=update,
            context=context,
            action="/claim",
            details=f"User {user_id} claimed code from {referrer_id}",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

# NEW: Generate video redeem code (Admin/Owner only)
async def genvdo_redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate one-time video redeem code"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /genvdo_redeem <value> <code_name>")
        return
    
    if not MONGO_AVAILABLE:
        await update.message.reply_text("❌ Database not available.")
        return
    
    try:
        value = int(context.args[0])
        code_name = context.args[1].strip().upper()
        
        # Single-use code
        vdo_redeem_col.insert_one({
            "code": code_name,
            "value": value,
            "created_by": update.effective_user.id,
            "created_at": datetime.now(),
            "used_by": None,  # NEW: Single user only
            "max_uses": 1
        })
        
        response_msg = await update.message.reply_text(
            f"✅ Single-use video redeem code created!\n\n"
            f"<b>Code:</b> <code>{code_name}</code>\n"
            f"<b>Video Credits:</b> {value}\n"
            f"<b>Uses:</b> 1 time only\n\n"
            f"Users can claim with: /vdoredeem {code_name}",
            parse_mode=ParseMode.HTML
        )
        
        await log_to_group(
            update=update,
            context=context,
            action="/genvdo_redeem",
            details=f"Code: {code_name}, Value: {value}",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

# NEW: Redeem video code
async def vdoredeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem video generation credits"""
    ensure_user(update)
    
    if not context.args:
        await update.message.reply_text("Usage: /vdoredeem <code_name>")
        return
    
    code_name = context.args[0].strip().upper()
    user_id = update.effective_user.id
    
    try:
        code_entry = vdo_redeem_col.find_one({"code": code_name})
        if not code_entry:
            await update.message.reply_text("❌ Invalid redeem code!")
            return
        
        # Check if already used
        if code_entry.get("used_by") is not None:
            await update.message.reply_text("❌ This code has already been used!")
            return
        
        # Mark as used and give credits
        vdo_redeem_col.update_one(
            {"code": code_name},
            {"$set": {"used_by": user_id}}
        )
        
        value = code_entry["value"]
        await add_video_credits(user_id, value)
        
        response_msg = await update.message.reply_text(
            f"🎉 <b>Video Credits Redeemed!</b>\n\n"
            f"✅ You received <b>{value}</b> video generation credits!\n\n"
            f"Use /vdogen to generate videos!",
            parse_mode=ParseMode.HTML
        )
        
        await log_to_group(
            update=update,
            context=context,
            action="/vdoredeem",
            details=f"User {user_id} redeemed {code_name} for {value} video credits",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

async def gen_redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate AI redeem code (Admin/Owner only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /gen_redeem <value> <code_name>")
        return
    
    if not MONGO_AVAILABLE:
        await update.message.reply_text("❌ Database not available.")
        return
    
    try:
        value = int(context.args[0])
        code_name = context.args[1].strip().upper()
        
        redeem_col.insert_one({
            "code": code_name,
            "value": value,
            "created_by": update.effective_user.id,
            "created_at": datetime.now(),
            "used_by": [],
            "max_uses": 1
        })
        
        response_msg = await update.message.reply_text(
            f"✅ Single-use redeem code created!\n\n"
            f"<b>Code:</b> <code>{code_name}</code>\n"
            f"<b>AI Credits:</b> {value}\n"
            f"<b>Uses:</b> 1 time only\n\n"
            f"Users can claim with: /redeem {code_name}",
            parse_mode=ParseMode.HTML
        )
        
        await log_to_group(
            update=update,
            context=context,
            action="/gen_redeem",
            details=f"Code: {code_name}, Value: {value}",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

async def redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem AI credits code"""
    ensure_user(update)
    
    if not context.args:
        await update.message.reply_text("Usage: /redeem <code_name>")
        return
    
    code_name = context.args[0].strip().upper()
    user_id = update.effective_user.id
    
    try:
        code_entry = redeem_col.find_one({"code": code_name})
        if not code_entry:
            await update.message.reply_text("❌ Invalid redeem code!")
            return
        
        if user_id in code_entry.get("used_by", []):
            await update.message.reply_text("❌ You already used this code!")
            return
        
        value = code_entry["value"]
        user_data = users_col.find_one({"_id": user_id}, {"media_gen_limit": 1})
        current_limit = user_data.get("media_gen_limit", BASE_MEDIA_GEN_LIMIT) if user_data else BASE_MEDIA_GEN_LIMIT
        
        users_col.update_one(
            {"_id": user_id},
            {"$set": {"media_gen_limit": current_limit + value}},
            upsert=True
        )
        
        redeem_col.update_one(
            {"code": code_name},
            {"$push": {"used_by": user_id}}
        )
        
        response_msg = await update.message.reply_text(
            f"🎉 <b>Redeemed Successfully!</b>\n\n"
            f"✅ Your media generation limit increased by <b>{value}</b>\n"
            f"📊 New limit: {current_limit + value} per day\n\n"
            f"Use /vdogen or /gen to generate media!",
            parse_mode=ParseMode.HTML
        )
        
        await log_to_group(
            update=update,
            context=context,
            action="/redeem",
            details=f"User {user_id} redeemed {code_name} for {value} media credits",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

async def whitelist_ai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Whitelist user for AI credits"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /whitelist_ai <user_id> <limit>")
        return
    
    try:
        target_id = int(context.args[0])
        limit = int(context.args[1])
        
        whitelist_col.update_one(
            {"_id": target_id},
            {"$set": {
                "daily_limit": limit,
                "last_usage_date": get_today_str(),
                "daily_usage": 0
            }},
            upsert=True
        )
        
        user_info = users_col.find_one({"_id": target_id}, {"name": 1})
        name = user_info.get("name", str(target_id)) if user_info else str(target_id)
        
        response_msg = await update.message.reply_text(
            f"✅ <b>User Whitelisted for AI</b>\n\n"
            f"👤 User: <code>{target_id}</code> ({name})\n"
            f"📊 AI Limit: {limit} per day",
            parse_mode=ParseMode.HTML
        )
        
        await log_to_group(
            update=update,
            context=context,
            action="/whitelist_ai",
            details=f"Set AI limit to {limit} for user {target_id}",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

# NEW: Whitelist for video credits
async def whitelist_vdo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Whitelist user for video credits"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /whitelist_vdo <user_id> <limit>")
        return
    
    try:
        target_id = int(context.args[0])
        limit = int(context.args[1])
        
        users_col.update_one(
            {"_id": target_id},
            {"$set": {
                "video_gen_limit": limit,
                "video_gen_date": get_today_str(),
                "video_gen_today": 0
            }},
            upsert=True
        )
        
        user_info = users_col.find_one({"_id": target_id}, {"name": 1})
        name = user_info.get("name", str(target_id)) if user_info else str(target_id)
        
        response_msg = await update.message.reply_text(
            f"✅ <b>User Whitelisted for Video</b>\n\n"
            f"👤 User: <code>{target_id}</code> ({name})\n"
            f"📊 Video Limit: {limit} per day",
            parse_mode=ParseMode.HTML
        )
        
        await log_to_group(
            update=update,
            context=context,
            action="/whitelist_vdo",
            details=f"Set video limit to {limit} for user {target_id}",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

async def lyrics_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get lyrics for a song"""
    ensure_user(update)
    
    if not await ensure_membership(update, context):
        return
    
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usage: /lyrics <song name>\nExample: /lyrics Ed Sheeran Shape of You")
        return
    
    status_msg = await update.message.reply_text(f"📝 Searching lyrics for '<b>{query}</b>'...", parse_mode=ParseMode.HTML)
    
    lyrics = await fetch_lyrics(query)
    
    if lyrics:
        if len(lyrics) > 3800:
            lyrics = lyrics[:3800] + "\n\n... (lyrics truncated due to message limit)"
        
        response_msg = await status_msg.edit_text(
            f"🎵 <b>Lyrics for:</b> <code>{query}</code>\n\n"
            f"<pre>{lyrics}</pre>",
            parse_mode=ParseMode.HTML
        )
    else:
        response_msg = await status_msg.edit_text(
            f"❌ Lyrics not found for '<code>{query}</code>'\n\n"
            f"Tips:\n"
            f"• Include artist name for better results\n"
            f"• Check spelling\n"
            f"• Song might not be in database",
            parse_mode=ParseMode.HTML
        )
    
    await log_to_group(
        update=update,
        context=context,
        action="/lyrics",
        details=f"Query: {query}",
        original_message=update.message,
        response_message=response_msg
    )

# =========================
# Search & AI Commands
# =========================

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    
    if not await ensure_membership(update, context):
        return
    
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usage: /search <text>")
        return
    
    status_msg = await update.message.reply_text(f"Searching '<b>{query}</b>'...", parse_mode=ParseMode.HTML)

    cookies_path = Path(COOKIES_FILE)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "default_search": "ytsearch5",
        "extract_flat": False,
    }
    
    if cookies_path.exists() and cookies_path.stat().st_size > 0:
        ydl_opts["cookiefile"] = str(cookies_path)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
    except Exception as e:
        error_str = str(e)
        if "Sign in to confirm" in error_str:
            await status_msg.edit_text(
                "❌ <b>YouTube Bot Detection</b>\n\n"
                "YouTube is requiring sign-in to search. This means:\n"
                "• Your cookies are missing or expired\n"
                "• The cookies file format is wrong (must be Netscape)\n"
                "• YouTube flagged the session\n\n"
                "<b>Solution:</b>\n"
                "1. Export fresh cookies from YouTube\n"
                "2. Use browser extension 'Get cookies.txt LOCALLY'\n"
                "3. Make sure you're logged in to YouTube\n"
                "4. Save as <code>cookies.txt</code> in bot folder\n"
                "5. Run /testcookies to verify\n\n"
                "<b>Alternative:</b> Send direct YouTube URLs instead of searching",
                parse_mode=ParseMode.HTML
            )
        else:
            await status_msg.edit_text(f"⚠️ Search failed: {e}")
        return

    entries = info.get("entries", [])
    if not entries:
        await status_msg.edit_text("No results found.")
        return

    buttons = []
    for e in entries[:5]:
        title = sanitize_filename(e.get("title") or "video")
        video_id = e.get('id')
        url = f"https://youtube.com/watch?v={video_id}" if video_id else e.get('webpage_url')
        token = store_url(url)
        buttons.append([InlineKeyboardButton(title[:60], callback_data=f"s|{token}|pick")])

    response_msg = await status_msg.edit_text("Choose a video:", reply_markup=InlineKeyboardMarkup(buttons))
    
    await log_to_group(
        update=update,
        context=context,
        action="/search",
        details=f"Query: {query}",
        original_message=update.message,
        response_message=response_msg
    )

async def gen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate AI image"""
    ensure_user(update)
    
    if not await ensure_membership(update, context):
        return
    
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usage: /gen <description>")
        return
    
    user_id = update.effective_user.id
    
    # Check limit
    today = get_today_str()
    user_data = users_col.find_one({"_id": user_id}, {"media_gen_today": 1, "media_gen_date": 1})
    used_today = user_data.get("media_gen_today", 0) if user_data and user_data.get("media_gen_date") == today else 0
    
    if used_today >= BASE_MEDIA_GEN_LIMIT:
        await update.message.reply_text(f"❌ Daily limit: {used_today}/{BASE_MEDIA_GEN_LIMIT}")
        return
    
    # Generate image
    status = await update.message.reply_text(f"🎨 Generating: <b>{query}</b>...", parse_mode=ParseMode.HTML)
    
    try:
        encoded = query.replace(" ", "+")
        url = f"https://flux-pro.vercel.app/generate?q={encoded}"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await status.edit_text(f"❌ API Error: {resp.status}")
                    return
                
                data = await resp.read()
                path = DOWNLOAD_DIR / f"gen_{user_id}.png"
                async with aiofiles.open(path, "wb") as f:
                    await f.write(data)
        
        # Send with watermark
        caption = f"🖼️ <b>{query}</b>\n\n<i>Generated by @spotifyxmusixbot</i>"
        response_msg = await update.message.reply_photo(photo=path, caption=caption, parse_mode=ParseMode.HTML)
        
        # Update counter
        users_col.update_one(
            {"_id": user_id},
            {"$set": {"media_gen_date": today, "media_gen_today": used_today + 1}},
            upsert=True
        )
        
        await status.delete()
        path.unlink()
        
        # NEW: Forward to log group
        await log_to_group(
            update=update,
            context=context,
            action="/gen",
            details=f"Prompt: {query} | User: {user_id}",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        await status.edit_text(f"❌ Failed: {str(e)[:100]}")
        await log_to_group(
            update=update,
            context=context,
            action="/gen",
            details=f"Error: {str(e)[:100]} | User: {user_id}",
            is_error=True,
            original_message=update.message
        )

# =========================
# AI Video Generation
# =========================

async def vdogen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate AI video"""
    ensure_user(update)
    
    if not await ensure_membership(update, context):
        return
    
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usage: /vdogen <description>\nExample: /vdogen A cute girl dancing")
        return
    
    user_id = update.effective_user.id
    
    # Check if user already has an active generation
    if user_id in user_active_tasks and not user_active_tasks[user_id].done():
        await update.message.reply_text(
            "⏳ <b>You already have a video generating!</b>\n\n"
            "Please wait for your current request to complete before starting a new one.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check video credits (NEW)
    vdo_limit, vdo_used = await get_user_video_credits(user_id)
    if vdo_used >= vdo_limit:
        limit_msg = (
            f"❌ <b>Daily Video Limit Reached</b>\n\n"
            f"You can generate <b>{vdo_limit} videos</b> per day.\n\n"
            f"✅ Used today: {vdo_used}/{vdo_limit}\n\n"
            f"💡 <b>Get more:</b>\n"
            f"• Use /vdoredeem to claim codes\n"
            f"• Contact {PREMIUM_BOT_USERNAME} for premium\n\n"
            f"🔄 Resets at midnight UTC"
        )
        await update.message.reply_text(limit_msg, parse_mode=ParseMode.HTML)
        return
    
    # Check AI credits (for non-admins)
    if not is_admin(user_id):
        credits, used, is_whitelisted = await get_user_credits(user_id)
        remaining = credits - used
        if remaining <= 0 and not is_whitelisted:
            no_credits_text = (
                f"❌ <b>No AI Credits Remaining!</b>\n\n"
                f"📊 Your daily limit: {credits}\n"
                f"✅ Used: {used}\n\n"
                f"<b>Get more credits:</b>\n"
                f"• /refer - Generate referral code\n"
                f"• Contact {PREMIUM_BOT_USERNAME} for premium\n\n"
                f"📊 Video limit: {vdo_limit} per day"
            )
            await update.message.reply_text(no_credits_text, parse_mode=ParseMode.HTML)
            return
    
    # Acknowledge
    status_msg = await update.message.reply_text(
        f"🎬 <b>Video Request Received!</b>\n\n"
        f"📝 Prompt: <code>{query[:60]}...</code>\n\n"
        f"⏳ <i>Queue position: {len(video_generation_queue) + 1}</i>",
        parse_mode=ParseMode.HTML
    )
    
    # Log to group
    await log_to_group(
        update=update,
        context=context,
        action="/vdogen",
        details=f"Prompt: {query} | User: {user_id} | Queued",
        original_message=update.message
    )
    
    # Add to queue
    queue_item = {
        "user_id": user_id,
        "query": query,
        "status_msg": status_msg,
        "update": update,
        "context": context,
        "video_gen_today": vdo_used,
        "video_gen_limit": vdo_limit
    }
    
    video_generation_queue.append(queue_item)
    asyncio.create_task(process_video_queue())
    
    log.info(f"✅ Added to queue. Current queue size: {len(video_generation_queue)}")

async def process_video_queue():
    """Background worker for video generation"""
    global active_generations
    
    if active_generations >= MAX_CONCURRENT_GENERATIONS:
        log.info(f"⏳ Max concurrent generations reached ({MAX_CONCURRENT_GENERATIONS})")
        return
    
    if not video_generation_queue:
        return
    
    async with generation_semaphore:
        active_generations += 1
        queue_item = video_generation_queue.popleft()
        
        user_id = queue_item["user_id"]
        query = queue_item["query"]
        status_msg = queue_item["status_msg"]
        update = queue_item["update"]
        context = queue_item["context"]
        
        task = asyncio.current_task()
        user_active_tasks[user_id] = task
        
        try:
            log.info(f"🎬 Starting generation for user {user_id}")
            
            await status_msg.edit_text(
                f"🚀 <b>Submitting to AI...</b>\n"
                f"⏳ This takes 30-90 seconds",
                parse_mode=ParseMode.HTML
            )
            
            api = GeminiGenAPI(parse_netscape_cookies(COOKIE_FILE_CONTENT), BEARER_TOKEN)
            job_id = await api.generate_video(query)
            
            await status_msg.edit_text(
                f"⏳ <b>Generating video...</b>\n"
                f"🆔 Job: <code>{job_id[:8]}...</code>",
                parse_mode=ParseMode.HTML
            )
            
            video_url = await api.poll_for_video(job_id, timeout=300)
            await status_msg.edit_text("⬇️ <b>Downloading video...</b>", parse_mode=ParseMode.HTML)
            video_bytes = await api.download_video(video_url)
            
            await status_msg.edit_text("⬆️ <b>Uploading to Telegram...</b>", parse_mode=ParseMode.HTML)
            
            video_path = DOWNLOAD_DIR / f"vdo_{user_id}_{secrets.token_urlsafe(8)}.mp4"
            async with aiofiles.open(video_path, "wb") as f:
                await f.write(video_bytes)
            
            caption = (
                f"🎬 <b>{query}</b>\n\n"
                f"✨ Generated by @spotifyxmusixbot\n"
                f"🔖 Job: <code>{job_id[:8]}...</code>"
            )
            
            response_msg = await update.message.reply_video(
                video=video_path,
                caption=caption,
                filename=f"{query}.mp4",
                parse_mode=ParseMode.HTML,
                supports_streaming=True,
                connect_timeout=60,
                read_timeout=60,
                write_timeout=60
            )
            
            # Consume credits
            await consume_video_credit(user_id)
            if not is_admin(user_id):
                await consume_credit(user_id)
            
            await status_msg.delete()
            video_path.unlink(missing_ok=True)
            
            log.info(f"✅ SUCCESS! Video sent for user {user_id}")
            
            # Forward to log group
            await log_to_group(
                update=update,
                context=context,
                action="/vdogen",
                details=f"Prompt: {query} | User: {user_id} | Success",
                original_message=update.message,
                response_message=response_msg
            )
            
        except Exception as e:
            error_str = str(e)
            log.error(f"vdogen failed for user {user_id}: {e}", exc_info=True)
            
            try:
                await status_msg.edit_text(
                    "❌ <b>Video Generation Error</b>\n\n"
                    "Our AI video service is temporarily unavailable.\n\n"
                    "💡 <b>Try:</b>\n"
                    "• /gen for AI images\n"
                    "• Try again in a few minutes\n"
                    "• Contact @ayushxchat_robot for support",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
            
            await log_to_group(
                update=update,
                context=context,
                action="/vdogen",
                details=f"Error: {error_str[:150]} | User: {user_id}",
                is_error=True,
                original_message=update.message
            )
        
        finally:
            active_generations -= 1
            if user_id in user_active_tasks:
                del user_active_tasks[user_id]
            
            if video_generation_queue:
                asyncio.create_task(process_video_queue())

async def gpt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI Chat command"""
    ensure_user(update)
    
    try:
        if not await ensure_membership(update, context):
            return
    except Exception as e:
        await update.message.reply_text("❌ Error checking membership. Please try again.")
        return
    
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usage: /gpt <your question>")
        return
    
    if not groq_client:
        await update.message.reply_text("❌ AI not configured. Contact admin.", parse_mode=ParseMode.HTML)
        return
    
    user_id = update.effective_user.id
    
    # CREDIT CHECK
    try:
        credits, used, is_whitelisted = await get_user_credits(user_id)
        remaining = credits - used
        
    except Exception as e:
        credits, used, is_whitelisted = BASE_CREDITS, 0, False
        remaining = credits
    
    if remaining <= 0:
        no_credits_text = (
            f"❌ <b>No AI Credits Remaining!</b>\n\n"
            f"📊 Your daily limit: {credits}\n"
            f"✅ Used: {used}\n\n"
            f"<b>Get more credits:</b>\n"
            f"• /refer - Generate referral code (+{REFERRER_BONUS} per friend)\n"
            f"• Contact {PREMIUM_BOT_USERNAME} for premium access\n\n"
            f"Use /credits to check your balance"
        )
        await update.message.reply_text(no_credits_text, parse_mode=ParseMode.HTML)
        return
    
    status_msg = await update.message.reply_text(f"🤖 Processing... (Credits left: {remaining-1})")
    
    if user_id not in USER_CONVERSATIONS:
        USER_CONVERSATIONS[user_id] = [
            {"role": "system", "content": "You are a helpful assistant. Be concise and clear."}
        ]
    
    USER_CONVERSATIONS[user_id].append({"role": "user", "content": query})
    
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=USER_CONVERSATIONS[user_id],
            max_tokens=1000,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        USER_CONVERSATIONS[user_id].append({"role": "assistant", "content": answer})
        
        if len(USER_CONVERSATIONS[user_id]) > 10:
            USER_CONVERSATIONS[user_id] = [USER_CONVERSATIONS[user_id][0]] + USER_CONVERSATIONS[user_id][-9:]
        
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n... (truncated)"
        
        response_msg = await status_msg.edit_text(
            f"💬 <b>Query:</b> <code>{query}</code>\n\n"
            f"<b>Answer:</b>\n{answer}\n\n"
            f"<i>ai by @spotifyxmusixbot</i>",
            parse_mode=ParseMode.HTML
        )
        
        await consume_credit(user_id)
        
        await log_to_group(
            update=update,
            context=context,
            action="/gpt",
            details=f"User {user_id}: {query[:50]}... | Remaining: {remaining-1}",
            original_message=update.message,
            response_message=response_msg
        )
        
    except Exception as e:
        log.error(f"Gpt_cmd error for {user_id}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ AI Error: {str(e)[:200]}")
        USER_CONVERSATIONS[user_id] = [{"role": "system", "content": "You are a helpful assistant."}]
        
        await log_to_group(
            update=update,
            context=context,
            action="/gpt",
            details=f"Error: {e}",
            is_error
