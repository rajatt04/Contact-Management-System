"""
Menu-driven Contact Management System using MongoDB (pymongo).
Save as contacts.py and run: python contacts.py
"""

import json
import sys
from pprint import pprint
from typing import Optional

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from bson.objectid import ObjectId

# ---------- CONFIG ----------
# Replace with your MongoDB URI if using Atlas, e.g.:
# MONGO_URI = "mongodb+srv://<user>:<pass>@cluster0.mongodb.net/?retryWrites=true&w=majority"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "contact_manager"
COLLECTION_NAME = "contacts"
# ----------------------------

# Connect
def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        # quick ping to fail fast if DB unreachable
        client.admin.command("ping")
    except ServerSelectionTimeoutError as e:
        print("ERROR: Can't connect to MongoDB. Check MONGO_URI and that the server is running.")
        print(e)
        sys.exit(1)
    return client[DB_NAME]

db = get_db()
col = db[COLLECTION_NAME]


# ---------- Utilities ----------
def input_nonempty(prompt: str, optional=False) -> Optional[str]:
    while True:
        val = input(prompt).strip()
        if val == "" and optional:
            return None
        if val != "":
            return val
        print("Input cannot be empty. Try again.")


def normalize_phone(phone: str) -> str:
    # simple normalization: remove spaces/hyphens
    return "".join(ch for ch in phone if ch.isdigit() or ch == "+")


def show_contact(doc):
    if not doc:
        return
    print("-" * 40)
    print(f"ID: {doc.get('_id')}")
    print(f"Name: {doc.get('name')}")
    print(f"Phone: {doc.get('phone')}")
    print(f"Email: {doc.get('email')}")
    print(f"Address: {doc.get('address')}")
    print(f"Tags: {', '.join(doc.get('tags', []))}")
    print("-" * 40)


# ---------- CRUD ----------
def add_contact():
    print("\nAdd a new contact")
    name = input_nonempty("Name: ")
    phone = input_nonempty("Phone: ")
    phone = normalize_phone(phone)
    email = input("Email (optional): ").strip() or None
    address = input("Address (optional): ").strip() or None
    tags_raw = input("Tags (comma separated, optional): ").strip()
    tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else []
    doc = {
        "name": name,
        "phone": phone,
        "email": email,
        "address": address,
        "tags": tags,
    }
    res = col.insert_one(doc)
    print(f"Contact added with id: {res.inserted_id}")


def list_contacts(limit=0):
    print("\nContacts:")
    cursor = col.find().sort("name", 1).limit(limit or 0)
    found = False
    for doc in cursor:
        found = True
        show_contact(doc)
    if not found:
        print("No contacts found.")


def find_contacts_by_text():
    term = input_nonempty("Search term (name/phone/email/tag): ")
    term_norm = term.strip()
    # Search across several fields (case-insensitive)
    query = {
        "$or": [
            {"name": {"$regex": term_norm, "$options": "i"}},
            {"phone": {"$regex": term_norm, "$options": "i"}},
            {"email": {"$regex": term_norm, "$options": "i"}},
            {"tags": {"$regex": term_norm, "$options": "i"}},  # matches tag substrings
        ]
    }
    cursor = col.find(query).sort("name", 1)
    hits = list(cursor)
    if not hits:
        print("No matches.")
        return
    print(f"Found {len(hits)} result(s):")
    for doc in hits:
        show_contact(doc)


def get_contact_by_id(prompt="Enter contact ID: "):
    raw = input_nonempty(prompt)
    try:
        _id = ObjectId(raw)
    except Exception:
        # maybe user entered string id that's not ObjectId
        try:
            # search by string id stored as _id (less common)
            doc = col.find_one({"_id": raw})
            if doc:
                return doc
        except Exception:
            pass
        print("Invalid ID format.")
        return None
    doc = col.find_one({"_id": _id})
    if not doc:
        print("No contact found with that ID.")
    return doc


def update_contact():
    print("\nUpdate contact")
    doc = get_contact_by_id()
    if not doc:
        return
    print("Current values (leave blank to keep):")
    show_contact(doc)
    name = input("Name: ").strip() or doc.get("name")
    phone = input("Phone: ").strip() or doc.get("phone")
    phone = normalize_phone(phone)
    email = input("Email: ").strip() or doc.get("email")
    address = input("Address: ").strip() or doc.get("address")
    tags_raw = input("Tags (comma separated): ").strip()
    tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else doc.get("tags", [])
    update = {
        "name": name,
        "phone": phone,
        "email": email,
        "address": address,
        "tags": tags,
    }
    col.update_one({"_id": doc["_id"]}, {"$set": update})
    print("Contact updated.")


def delete_contact():
    print("\nDelete contact")
    doc = get_contact_by_id()
    if not doc:
        return
    show_contact(doc)
    confirm = input("Type 'yes' to confirm deletion: ").strip().lower()
    if confirm == "yes":
        col.delete_one({"_id": doc["_id"]})
        print("Deleted.")
    else:
        print("Aborted.")


# ---------- Import / Export ----------
def export_contacts():
    path = input_nonempty("Export file path (e.g. contacts_export.json): ")
    cursor = col.find()
    docs = []
    for d in cursor:
        d = d.copy()
        d["_id"] = str(d["_id"])
        docs.append(d)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(docs)} contacts to {path}")


def import_contacts():
    path = input_nonempty("Import file path (JSON array): ")
    try:
        with open(path, "r", encoding="utf-8") as f:
            docs = json.load(f)
    except Exception as e:
        print("Failed to read JSON:", e)
        return
    count = 0
    for d in docs:
        # Remove _id if present (avoid duplicate key errors); allow optional fields
        d.pop("_id", None)
        # Ensure required fields exist minimally
        if "name" not in d or not d.get("name"):
            continue
        if "phone" in d and d["phone"]:
            d["phone"] = normalize_phone(d["phone"])
        else:
            d.setdefault("phone", "")
        d.setdefault("tags", d.get("tags", []))
        col.insert_one(d)
        count += 1
    print(f"Imported {count} contacts from {path}")


# ---------- Menu ----------
def menu():
    print("\nContact Manager")
    print("=" * 20)
    print("1) Add contact")
    print("2) List all contacts")
    print("3) Search contacts")
    print("4) Update contact")
    print("5) Delete contact")
    print("6) Export contacts to JSON")
    print("7) Import contacts from JSON")
    print("0) Exit")
    choice = input("Choose: ").strip()
    return choice


def main_loop():
    while True:
        choice = menu()
        if choice == "1":
            add_contact()
        elif choice == "2":
            list_contacts()
        elif choice == "3":
            find_contacts_by_text()
        elif choice == "4":
            update_contact()
        elif choice == "5":
            delete_contact()
        elif choice == "6":
            export_contacts()
        elif choice == "7":
            import_contacts()
        elif choice == "0":
            print("Goodbye.")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    print(f"Using MongoDB: {MONGO_URI}, DB: {DB_NAME}, Collection: {COLLECTION_NAME}")
    main_loop()
