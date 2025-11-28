# api.py
import os
import json
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash
)

from models import (
    init_auth_collection, verify_user, list_databases,
    get_collections, paginate_documents, get_document,
    insert_document, update_document, delete_document,
    list_credentials, add_credential, update_credential,
    delete_credential, SECURE_DB_NAME,
    create_collection, delete_collection, delete_database
)


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

# Initialize secure_auth DB and default admin
init_auth_collection()


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def api_auth_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return view_func(*args, **kwargs)
    return wrapper


@app.route("/", methods=["GET"])
def login():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_post():
    username = request.form.get("username")
    password = request.form.get("password")

    if verify_user(username, password):
        session["username"] = username
        flash("Login successful", "success")
        return redirect(url_for("dashboard"))
    else:
        flash("Invalid credentials", "error")
        return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    dbs = list_databases()
    return render_template("dashboard.html", dbs=dbs, secure_db=SECURE_DB_NAME)

@app.route("/db/create", methods=["POST"])
@login_required
def create_database_view():
    db_name = request.form.get("db_name", "").strip()
    coll_name = request.form.get("coll_name", "").strip()

    if not db_name:
        flash("Database name is required", "error")
        return redirect(url_for("dashboard"))

    if not coll_name:
        coll_name = "default"

    try:
        ok = create_collection(db_name, coll_name)
        if ok:
            flash(f"Database '{db_name}' created with collection '{coll_name}'", "success")
        else:
            flash("Collection already exists in that database", "error")
    except Exception as e:
        print(e)
        flash("Error creating database/collection", "error")

    return redirect(url_for("dashboard"))

@app.route("/db/<db_name>/delete", methods=["POST"])
@login_required
def delete_database_view(db_name):
    if db_name == SECURE_DB_NAME:
        flash("Cannot delete secure_auth database", "error")
        return redirect(url_for("dashboard"))

    ok = delete_database(db_name)
    if ok:
        flash(f"Database '{db_name}' deleted", "success")
    else:
        flash("Could not delete this database (maybe protected or not found)", "error")
    return redirect(url_for("dashboard"))




@app.route("/db/<db_name>/collections")
@login_required
def view_collections(db_name):
    cols = get_collections(db_name)
    return render_template(
        "collections.html",
        db_name=db_name,
        collections=cols,
        secure_db=SECURE_DB_NAME
    )


@app.route("/db/<db_name>/collection/<coll_name>")
@login_required
def view_collection_data(db_name, coll_name):
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 10))
    data = paginate_documents(db_name, coll_name, page, page_size)

    return render_template(
        "collection_view.html",
        db_name=db_name,
        coll_name=coll_name,
        documents=data["documents"],
        page=data["page"],
        page_size=data["page_size"],
        total=data["total"],
        total_pages=data["total_pages"],
        secure_db=SECURE_DB_NAME
    )


@app.route("/db/<db_name>/collection/<coll_name>/insert", methods=["POST"])
@login_required
def insert_doc_view(db_name, coll_name):
    raw = request.form.get("json_data")
    try:
        data = json.loads(raw)
        insert_document(db_name, coll_name, data)
        flash("Document inserted", "success")
    except Exception as e:
        print(e)
        flash("Invalid JSON or insert error", "error")
    return redirect(url_for("view_collection_data", db_name=db_name, coll_name=coll_name))

@app.route("/db/<db_name>/collection/create", methods=["POST"])
@login_required
def create_collection_view(db_name):
    coll_name = request.form.get("coll_name", "").strip()
    if not coll_name:
        flash("Collection name is required", "error")
        return redirect(url_for("view_collections", db_name=db_name))

    try:
        ok = create_collection(db_name, coll_name)
        if ok:
            flash(f"Collection '{coll_name}' created in '{db_name}'", "success")
        else:
            flash("Collection already exists", "error")
    except Exception as e:
        print(e)
        flash("Error creating collection", "error")

    return redirect(url_for("view_collections", db_name=db_name))

@app.route("/db/<db_name>/collection/<coll_name>/delete", methods=["POST"])
@login_required
def delete_collection_view(db_name, coll_name):
    # Protect secure_auth.users from being deleted
    if db_name == SECURE_DB_NAME and coll_name == "users":
        flash("Cannot delete 'users' collection from secure_auth", "error")
        return redirect(url_for("view_collections", db_name=db_name))

    ok = delete_collection(db_name, coll_name)
    if ok:
        flash(f"Collection '{coll_name}' deleted from '{db_name}'", "success")
    else:
        flash("Could not delete collection (maybe not found)", "error")

    return redirect(url_for("view_collections", db_name=db_name))


@app.route("/db/<db_name>/collection/<coll_name>/document/<doc_id>/edit", methods=["GET", "POST"])
@login_required
def edit_doc_view(db_name, coll_name, doc_id):
    if request.method == "GET":
        doc = get_document(db_name, coll_name, doc_id)
        if not doc:
            flash("Document not found", "error")
            return redirect(url_for("view_collection_data", db_name=db_name, coll_name=coll_name))
        return render_template(
            "edit_document.html",
            db_name=db_name,
            coll_name=coll_name,
            doc=doc,
            secure_db=SECURE_DB_NAME
        )

    # POST
    raw = request.form.get("json_data")
    try:
        data = json.loads(raw)
        # Remove _id if present in updated doc
        if "_id" in data:
            del data["_id"]
        ok = update_document(db_name, coll_name, doc_id, data)
        if ok:
            flash("Document updated", "success")
        else:
            flash("Update failed", "error")
    except Exception as e:
        print(e)
        flash("Invalid JSON or update error", "error")

    return redirect(url_for("view_collection_data", db_name=db_name, coll_name=coll_name))


@app.route("/db/<db_name>/collection/<coll_name>/document/<doc_id>/delete", methods=["POST"])
@login_required
def delete_doc_view(db_name, coll_name, doc_id):
    ok = delete_document(db_name, coll_name, doc_id)
    if ok:
        flash("Document deleted", "success")
    else:
        flash("Delete failed", "error")
    return redirect(url_for("view_collection_data", db_name=db_name, coll_name=coll_name))


# ----------------- Credential Management UI -----------------


@app.route("/credentials")
@login_required
def credentials_page():
    users = list_credentials()
    return render_template(
        "credentials.html",
        users=users,
        secure_db=SECURE_DB_NAME
    )


@app.route("/credentials/add", methods=["POST"])
@login_required
def add_cred_view():
    username = request.form.get("username")
    password = request.form.get("password")
    role = request.form.get("role", "user")
    if not username or not password:
        flash("Username and password required", "error")
    else:
        add_credential(username, password, role)
        flash("Credential added", "success")
    return redirect(url_for("credentials_page"))


@app.route("/credentials/<user_id>/update", methods=["POST"])
@login_required
def update_cred_view(user_id):
    username = request.form.get("username")
    password = request.form.get("password")  # may be empty
    role = request.form.get("role", "user")
    pwd = password if password.strip() else None
    ok = update_credential(user_id, username, pwd, role)
    if ok:
        flash("Credential updated", "success")
    else:
        flash("Update failed", "error")
    return redirect(url_for("credentials_page"))


@app.route("/credentials/<user_id>/delete", methods=["POST"])
@login_required
def delete_cred_view(user_id):
    ok = delete_credential(user_id)
    if ok:
        flash("Credential deleted", "success")
    else:
        flash("Delete failed", "error")
    return redirect(url_for("credentials_page"))


# ----------------- JSON API endpoints (protected) -----------------

@app.route("/api/databases")
@api_auth_required
def api_databases():
    return jsonify({"databases": list_databases()})


@app.route("/api/databases/<db_name>/collections")
@api_auth_required
def api_collections(db_name):
    return jsonify({"db": db_name, "collections": get_collections(db_name)})


@app.route("/api/databases/<db_name>/collections/<coll_name>/documents")
@api_auth_required
def api_documents(db_name, coll_name):
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 10))
    data = paginate_documents(db_name, coll_name, page, page_size)
    return jsonify(data)


@app.route("/api/databases/<db_name>/collections/<coll_name>/documents", methods=["POST"])
@api_auth_required
def api_insert_document(db_name, coll_name):
    try:
        payload = request.get_json(force=True)
        new_id = insert_document(db_name, coll_name, payload)
        return jsonify({"inserted_id": new_id}), 201
    except Exception as e:
        print(e)
        return jsonify({"error": "Invalid JSON"}), 400


@app.route("/api/databases/<db_name>/collections/<coll_name>/documents/<doc_id>", methods=["PUT"])
@api_auth_required
def api_update_document(db_name, coll_name, doc_id):
    try:
        payload = request.get_json(force=True)
        if "_id" in payload:
            del payload["_id"]
        ok = update_document(db_name, coll_name, doc_id, payload)
        if ok:
            return jsonify({"status": "updated"})
        return jsonify({"error": "Not updated"}), 400
    except Exception as e:
        print(e)
        return jsonify({"error": "Invalid JSON"}), 400


@app.route("/api/databases/<db_name>/collections/<coll_name>/documents/<doc_id>", methods=["DELETE"])
@api_auth_required
def api_delete_document(db_name, coll_name, doc_id):
    ok = delete_document(db_name, coll_name, doc_id)
    if ok:
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Not deleted"}), 400


if __name__ == "__main__":
    app.run(debug=True)
