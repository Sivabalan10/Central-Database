from pymongo import MongoClient
import os

# ===== 1. MongoDB connection =====
# Use your Atlas URI or local MongoDB
# Example Atlas URI:
# MONGO_URI = "mongodb+srv://user:password@cluster0.xxx.mongodb.net/?retryWrites=true&w=majority"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

client = MongoClient(MONGO_URI)

# ===== 2. Choose database =====
db_name = "test_db"
db = client[db_name]

# ===== 3. Create collections & insert sample docs =====

# Collection: users
users_coll = db["users"]
users_docs = [
    {"username": "alice", "role": "admin", "active": True},
    {"username": "bob", "role": "user", "active": True},
    {"username": "charlie", "role": "user", "active": False},
]
users_result = users_coll.insert_many(users_docs)
print(f"Inserted {len(users_result.inserted_ids)} documents into test_db.users")

# Collection: products
products_coll = db["products"]
products_docs = [
    {"name": "Laptop", "price": 75000, "stock": 10},
    {"name": "Mouse", "price": 800, "stock": 50},
    {"name": "Keyboard", "price": 1500, "stock": 30},
]
products_result = products_coll.insert_many(products_docs)
print(f"Inserted {len(products_result.inserted_ids)} documents into test_db.products")

# Collection: logs
logs_coll = db["logs"]
logs_docs = [
    {"type": "login",  "user": "alice",   "status": "success"},
    {"type": "login",  "user": "bob",     "status": "failed"},
    {"type": "action", "user": "alice",   "detail": "created product"},
]
logs_result = logs_coll.insert_many(logs_docs)
print(f"Inserted {len(logs_result.inserted_ids)} documents into test_db.logs")

# ===== 4. Verify by listing DBs, collections and sample docs =====

print("\n=== Databases ===")
print(client.list_database_names())

print("\n=== Collections in test_db ===")
print(db.list_collection_names())

print("\n=== Sample documents ===")
print("users:")
for doc in users_coll.find():
    print(" ", doc)

print("\nproducts:")
for doc in products_coll.find():
    print(" ", doc)

print("\nlogs:")
for doc in logs_coll.find():
    print(" ", doc)

print("\nDone. test_db is ready for your Flask DBMS.")
