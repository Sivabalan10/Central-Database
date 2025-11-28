# models.py
import os
from typing import List, Dict, Any, Optional

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import certifi

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(
    MONGO_URI,
    tls=True,                 # ensure TLS
    tlsCAFile=certifi.where() # use trusted CA bundle
)

SECURE_DB_NAME = "secure_auth"
SECURE_USERS_COLL = "users"

secure_auth_db: Database = client[SECURE_DB_NAME]
secure_users: Collection = secure_auth_db[SECURE_USERS_COLL]


def init_auth_collection() -> None:
    """
    Ensure secure_auth.users exists and has at least one admin user.
    """
    if secure_users.count_documents({}) == 0:
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

        secure_users.insert_one({
            "username": admin_username,
            "password_hash": generate_password_hash(admin_password),
            "role": "admin"
        })
        print(f"[INIT] Created default admin user: {admin_username}")


def verify_user(username: str, password: str) -> bool:
    user = secure_users.find_one({"username": username})
    if not user:
        return False
    return check_password_hash(user["password_hash"], password)


def list_databases() -> List[str]:
    # filter out internal DBs if you want
    dbs = client.list_database_names()
    # Keep secure_auth because we manage credentials
    filtered = [d for d in dbs if d not in ["admin", "local", "config"]]
    return filtered


def get_collections(db_name: str) -> List[str]:
    db = client[db_name]
    return db.list_collection_names()

# --------- Database & Collection Management --------- #

def create_collection(db_name: str, coll_name: str) -> bool:
    """
    Create a collection in a database.
    If the DB doesn't exist, Mongo will create it automatically.
    Returns False if the collection already exists.
    """
    db = client[db_name]
    existing = db.list_collection_names()
    if coll_name in existing:
        return False
    db.create_collection(coll_name)
    return True


def delete_collection(db_name: str, coll_name: str) -> bool:
    """
    Drop a collection if it exists.
    """
    db = client[db_name]
    existing = db.list_collection_names()
    if coll_name not in existing:
        return False
    db.drop_collection(coll_name)
    return True


def delete_database(db_name: str) -> bool:
    """
    Drop a whole database.
    Protect internal DBs and secure_auth.
    """
    if db_name in ["admin", "local", "config"]:
        return False
    if db_name == SECURE_DB_NAME:
        return False
    client.drop_database(db_name)
    return True


def get_collection(db_name: str, coll_name: str) -> Collection:
    return client[db_name][coll_name]


def paginate_documents(
    db_name: str,
    coll_name: str,
    page: int = 1,
    page_size: int = 10
) -> Dict[str, Any]:
    coll = get_collection(db_name, coll_name)
    total = coll.count_documents({})
    skip = (page - 1) * page_size
    cursor = coll.find().skip(skip).limit(page_size)

    docs = []
    for d in cursor:
        d["_id"] = str(d["_id"])
        docs.append(d)

    return {
        "documents": docs,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
    }


def get_document(
    db_name: str,
    coll_name: str,
    doc_id: str
) -> Optional[Dict[str, Any]]:
    coll = get_collection(db_name, coll_name)
    try:
        oid = ObjectId(doc_id)
    except Exception:
        return None

    d = coll.find_one({"_id": oid})
    if not d:
        return None
    d["_id"] = str(d["_id"])
    return d


def insert_document(
    db_name: str,
    coll_name: str,
    data: Dict[str, Any]
) -> str:
    coll = get_collection(db_name, coll_name)
    result = coll.insert_one(data)
    return str(result.inserted_id)


def update_document(
    db_name: str,
    coll_name: str,
    doc_id: str,
    data: Dict[str, Any]
) -> bool:
    coll = get_collection(db_name, coll_name)
    try:
        oid = ObjectId(doc_id)
    except Exception:
        return False

    result = coll.update_one({"_id": oid}, {"$set": data})
    return result.modified_count > 0


def delete_document(
    db_name: str,
    coll_name: str,
    doc_id: str
) -> bool:
    coll = get_collection(db_name, coll_name)
    try:
        oid = ObjectId(doc_id)
    except Exception:
        return False
    result = coll.delete_one({"_id": oid})
    return result.deleted_count > 0


# ---------- Credential Management (secure_auth.users) ----------

def list_credentials() -> List[Dict[str, Any]]:
    users = []
    for u in secure_users.find():
        users.append({
            "_id": str(u["_id"]),
            "username": u["username"],
            "role": u.get("role", "")
        })
    return users


def add_credential(username: str, password: str, role: str = "user") -> str:
    doc = {
        "username": username,
        "password_hash": generate_password_hash(password),
        "role": role
    }
    res = secure_users.insert_one(doc)
    return str(res.inserted_id)


def update_credential(user_id: str, username: str, password: Optional[str], role: str) -> bool:
    try:
        oid = ObjectId(user_id)
    except Exception:
        return False

    update = {"username": username, "role": role}
    if password:
        update["password_hash"] = generate_password_hash(password)

    res = secure_users.update_one({"_id": oid}, {"$set": update})
    return res.modified_count > 0


def delete_credential(user_id: str) -> bool:
    try:
        oid = ObjectId(user_id)
    except Exception:
        return False
    res = secure_users.delete_one({"_id": oid})
    return res.deleted_count > 0
