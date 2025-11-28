from pymongo import MongoClient
from datetime import datetime
from config import *

# In-memory storage
PENDING: Dict[str, dict] = {}
USER_CONVERSATIONS: Dict[int, List[dict]] = {}
BROADCAST_STORE: Dict[int, List[dict]] = {}
BROADCAST_STATE: Dict[int, bool] = {}

# MongoDB Setup
MONGO_AVAILABLE = False
mongo_client = None
db = None
users_col = None
admins_col = None
redeem_col = None
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
    whitelist_col = db[MONGO_WHITELIST]
    MONGO_AVAILABLE = True
    
    # Indexes
    users_col.create_index("referral_code", unique=True, sparse=True)
    redeem_col.create_index("code", unique=True)
    
    # Add owner as admin if empty
    if admins_col.count_documents({}) == 0:
        admins_col.insert_one({
            "_id": OWNER_ID, "name": "Owner",
            "added_by": OWNER_ID, "added_at": datetime.now()
        })
        
except Exception as e:
    print(f"❌ MongoDB failed: {e}")
