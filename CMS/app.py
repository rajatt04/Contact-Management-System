from flask import Flask, request, jsonify, render_template, send_file, abort
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
import io
import csv
import os

# ---------- Config ----------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "contact_db")
COLL_NAME = os.getenv("COLL_NAME", "contacts")
# ---------------------------

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COLL_NAME]


def doc_to_json(d):
    j = {
        "_id": str(d.get("_id")),
        "name": d.get("name", ""),
        "phone": d.get("phone", ""),
        "email": d.get("email", ""),
        "address": d.get("address", ""),
        "tags": d.get("tags", []),
    }
    return j


@app.route("/")
def index():
    return render_template("index.html")


# Create contact
@app.route("/api/contacts", methods=["POST"])
def create_contact():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    contact = {
        "name": name,
        "phone": data.get("phone", "").strip(),
        "email": data.get("email", "").strip(),
        "address": data.get("address", "").strip(),
        "tags": data.get("tags", []),
    }
    res = col.insert_one(contact)
    contact["_id"] = str(res.inserted_id)
    return jsonify(doc_to_json(contact)), 201


# Read all contacts
@app.route("/api/contacts", methods=["GET"])
def get_contacts():
    docs = list(col.find().sort("name", 1))
    return jsonify([doc_to_json(d) for d in docs])


# Search contacts (q param - matches name, phone, email, tags)
@app.route("/api/contacts/search", methods=["GET"])
def search_contacts():
    q = (request.args.get("q") or "").strip()
    if q == "":
        return jsonify([])   # empty search -> return empty to let frontend call /api/contacts instead
    regex = {"$regex": q, "$options": "i"}
    query = {
        "$or": [
            {"name": regex},
            {"phone": regex},
            {"email": regex},
            {"tags": regex},
            {"address": regex},
        ]
    }
    docs = list(col.find(query).sort("name", 1))
    return jsonify([doc_to_json(d) for d in docs])

# Get single contact by ID
@app.route("/api/contacts/<id>", methods=["GET"])
def get_contact(id):
    try:
        doc = col.find_one({"_id": ObjectId(id)})
    except Exception:
        return jsonify({"error": "Invalid id"}), 400
    if not doc:
        return jsonify({"error": "Not found"}), 404
    return jsonify(doc_to_json(doc))

# Update contact
@app.route("/api/contacts/<id>", methods=["PUT"])
def update_contact(id):
    data = request.json or {}
    update = {}
    if "name" in data:
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "Name cannot be empty"}), 400
        update["name"] = name
    if "phone" in data:
        update["phone"] = data.get("phone", "").strip()
    if "email" in data:
        update["email"] = data.get("email", "").strip()
    if "address" in data:
        update["address"] = data.get("address", "").strip()
    if "tags" in data:
        update["tags"] = data.get("tags", [])
    if not update:
        return jsonify({"error": "Nothing to update"}), 400

    try:
        res = col.update_one({"_id": ObjectId(id)}, {"$set": update})
    except Exception:
        return jsonify({"error": "Invalid id"}), 400
    if res.matched_count == 0:
        return jsonify({"error": "Not found"}), 404
    doc = col.find_one({"_id": ObjectId(id)})
    return jsonify(doc_to_json(doc))


# Delete contact
@app.route("/api/contacts/<id>", methods=["DELETE"])
def delete_contact(id):
    try:
        res = col.delete_one({"_id": ObjectId(id)})
    except Exception:
        return jsonify({"error": "Invalid id"}), 400
    if res.deleted_count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"message": "Deleted"})


# Download CSV (returns all contacts as CSV)
@app.route("/api/contacts/download_csv", methods=["GET"])
def download_csv():
    docs = list(col.find().sort("name", 1))
    output = io.StringIO()
    writer = csv.writer(output)
    # header
    writer.writerow(["_id", "name", "phone", "email", "address", "tags"])
    for d in docs:
        writer.writerow([
            str(d.get("_id")),
            d.get("name", ""),
            d.get("phone", ""),
            d.get("email", ""),
            d.get("address", ""),
            ", ".join(d.get("tags", []))
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="contacts.csv"
    )

if __name__ == "__main__":
    # debug True only for development
    app.run(debug=True, host="127.0.0.1", port=5000)