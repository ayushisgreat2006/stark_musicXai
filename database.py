from pymongo import MongoClient
from datetime import datetime
from collections import deque
from config import *
import asyncio

# In-memory storage
PENDING: dict = {}
USER_CONVERSATIONS: dict = {}
BROADCAST_STORE: dict = {}
BROADCAST_STATE: dict = {}
video_generation_queue = deque()
active_generations = 0
generation_semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
user_active_tasks: dict = {}

# MongoDB Setup
MONGO_AVAILABLE = False
mongo_client = None
db = None
users_col = None
admins_col = None
redeem_col = None
vdo_redeem_col = None
whitelist_col = None

try:
    mongo_client = MongoClient(
        MONGO_URI, tls=True, tlsAllowInvalidCertificates=False,
        serverSelectionTimeoutMS=5000, retryWrites=True, w='majority'
    )
    mongo_client.admin.command('ping')
    db = mongo_client[MONGO_DB]
    users_col = db[MONGO_USERS]
    admins_col = db[MONGO_ADMINS]
    redeem_col = db[MONGO_REDEEM]
    vdo_redeem_col = db[MONGO_VDO_REDEEM]
    whitelist_col = db[MONGO_WHITELIST]
    MONGO_AVAILABLE = True
    
    # Indexes
    users_col.create_index("referral_code", unique=True, sparse=True)
    redeem_col.create_index("code", unique=True)
    vdo_redeem_col.create_index("code", unique=True)
    
    # Add owner as admin if empty
    if admins_col.count_documents({}) == 0:
        admins_col.insert_one({
            "_id": OWNER_ID, "name": "Owner",
            "added_by": OWNER_ID, "added_at": datetime.now()
        })
        
except Exception as e:
    print(f"❌ MongoDB failed: {e}")
