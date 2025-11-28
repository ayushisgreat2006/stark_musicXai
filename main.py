import logging
import signal
import sys
from pathlib import Path
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler, filters
)
from config import *
from database import *
from credits import *
from utils import *
from handlers import *
from callbacks import *
from message_handlers import *

# Logging setup
logging.basicConfig(
    level=logging.INFO, 
    format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("ytbot")

def shutdown_handler(signum, frame):
    log.info("Shutting down...")
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)

def main():
    # Startup info
    cookies_path = Path(COOKIES_FILE)
    cookies_working = cookies_path.exists() and cookies_path.stat().st_size > 0
    
    log.info("="*60)
    log.info("🔍 BOT STARTUP")
    log.info(f"Bot Token: {'✅ Set' if BOT_TOKEN else '❌ Missing'}")
    log.info(f"Owner ID: {OWNER_ID}")
    log.info(f"Log Group: {LOG_GROUP_ID}")
    log.info(f"AI API: {'✅ Set' if groq_client else '❌ Not Set'}")
    log.info(f"Cookies: {'✅ Found' if cookies_working else '❌ Missing'}")
    log.info(f"MongoDB: {'✅ Connected' if MONGO_AVAILABLE else '❌ Disconnected'}")
    log.info("="*60)
    
    app = ApplicationBuilder().token(BOT_TOKEN).connect_timeout(60).read_timeout(60).write_timeout(60).build()
    
    # Error handler
    async def error_handler(update: object, context):
        log.error("Exception while handling an update:", exc_info=context.error)
    
    app.add_error_handler(error_handler)

    # Add all handlers here
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    # ... add all other command handlers
    
    app.add_handler(CallbackQueryHandler(on_quality, pattern=r"^q\|"))
    app.add_handler(CallbackQueryHandler(on_search_pick, pattern=r"^s\|"))
    # ... add other callbacks
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))
    
    app.add_handler(ChatMemberHandler(my_chat_member_handler, ChatMemberHandler.MY_CHAT_MEMBER))
    
    log.info("🚀 Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
