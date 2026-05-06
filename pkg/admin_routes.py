import os
import re
from datetime import datetime, timedelta

from flask import abort, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from pkg import app
from pkg.blogmodel import Admin, Category, Comment, Post, Subcategory, Tag, db
from pkg.forms import (
    AdminLoginForm,
    CreateAdminAccountForm,
    CreatePostForm,
    MAX_UPLOAD_IMAGE_BYTES,
    UpdateProfileForm,
    _get_file_size_bytes,
    _strip_html,
)
from pkg.limiter import limiter
from pkg.route_constants import ADMIN_SESSION_KEY


def _format_post_date(created_at):
    if not created_at:
        return ""
    return created_at.strftime("%B %d, %Y").replace(" 0", " ")


def _serialize_admin_user(admin_obj):
    return {
        "id": admin_obj.id,
        "name": admin_obj.name,
        "email": admin_obj.email,
        "role": (admin_obj.role or "reader").capitalize(),
        "created_at": _format_post_date(admin_obj.created_at),
    }





def _render_create_account_page(form, form_error=None, form_success=None, bootstrap_mode=False):
    admins = Admin.query.order_by(Admin.created_at.desc(), Admin.id.desc()).all()
    payload = [_serialize_admin_user(item) for item in admins]
    return render_template(
        "admin/create_account.html",
        form=form,
        admins=payload,
        form_error=form_error,
        form_success=form_success,
        bootstrap_mode=bootstrap_mode,
    )


def _get_comment_status(comment_obj):
    if comment_obj.flagged_at:
        return "flagged"
    return "approved"


def _serialize_admin_comment(comment_obj):
    delete_on = comment_obj.flagged_at + timedelta(days=2) if comment_obj.flagged_at else None
    return {
        "id": comment_obj.id,
        "content": comment_obj.content,
        "status": _get_comment_status(comment_obj),
        "created_at": _format_post_date(comment_obj.created_at),
        "flagged_at": _format_post_date(comment_obj.flagged_at),
        "delete_on": _format_post_date(delete_on) if delete_on else "",
        "reader_name": comment_obj.reader.name if comment_obj.reader else "Unknown Reader",
        "post_id": comment_obj.post.id if comment_obj.post else None,
        "post_title": comment_obj.post.title if comment_obj.post else "Unknown Post",
    }


def _render_comments_page(form_error=None, form_success=None):
    comments = (
        Comment.query
        .order_by(Comment.flagged_at.desc(), Comment.created_at.desc())
        .all()
    )
    payload = [_serialize_admin_comment(item) for item in comments]
    return render_template(
        "admin/comments.html",
        comments=payload,
        form_error=form_error,
        form_success=form_success,
    )


def _normalize_label(raw_value):
    return re.sub(r"\s+", " ", (raw_value or "").strip())


def _get_category_overview_rows():
    rows = (
        db.session.query(
            Category.id,
            Category.name,
            func.count(Post.id).label("post_count"),
            func.count(func.distinct(Subcategory.id)).label("subcategory_count"),
        )
        .outerjoin(Subcategory, Subcategory.category_id == Category.id)
        .outerjoin(Post, Post.subcategory_id == Subcategory.id)
        .group_by(Category.id, Category.name)
        .order_by(Category.name.asc())
        .all()
    )

    return [
        {
            "id": row.id,
            "name": row.name,
            "post_count": int(row.post_count or 0),
            "subcategory_count": int(row.subcategory_count or 0),
        }
        for row in rows
    ]


def _render_categories_page(form_error=None, form_success=None):
    categories = Category.query.order_by(Category.name.asc()).all()
    subcategories = (
        Subcategory.query
        .join(Category, Category.id == Subcategory.category_id)
        .order_by(Category.name.asc(), Subcategory.name.asc())
        .all()
    )
    tags = Tag.query.order_by(Tag.name.asc()).all()
    overview_rows = _get_category_overview_rows()
    return render_template(
        "admin/categories.html",
        categories=categories,
        subcategories=subcategories,
        tags=tags,
        overview_rows=overview_rows,
        form_error=form_error,
        form_success=form_success,
    )


def _allowed_image(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in {"jpg", "jpeg", "png", "gif", "webp"}


def _save_uploaded_image(file_obj):
    if not file_obj or not file_obj.filename:
        return None

    filename = secure_filename(file_obj.filename)
    if not filename or not _allowed_image(filename):
        return None

    upload_dir = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    unique_name = f"{timestamp}_{filename}"
    file_path = os.path.join(upload_dir, unique_name)
    file_obj.save(file_path)

    return f"/static/uploads/{unique_name}"


def _get_post_category(post_obj):
    if post_obj.subcategory and post_obj.subcategory.category:
        return post_obj.subcategory.category.name
    return "General"


def _serialize_admin_draft(post_obj):
    excerpt_source = (post_obj.excerpt or "").strip() or _strip_html(post_obj.content)
    excerpt = excerpt_source[:180].rstrip()
    if len(excerpt_source) > 180:
        excerpt = f"{excerpt}..."

    return {
        "id": post_obj.id,
        "title": post_obj.title,
        "excerpt": excerpt,
        "category": _get_post_category(post_obj),
        "cover_image": post_obj.cover_image or "/static/city.jpg",
        "created_at": _format_post_date(post_obj.created_at),
        "tags": [tag.name for tag in post_obj.tags],
    }


def _get_or_create_default_category():
    category_obj = Category.query.order_by(Category.id.asc()).first()
    if category_obj:
        return category_obj

    category_obj = Category(name="General")
    db.session.add(category_obj)
    db.session.flush()
    return category_obj


def _get_or_create_default_subcategory(category_obj=None):
    if category_obj is None:
        category_obj = _get_or_create_default_category()

    subcategory_obj = Subcategory.query.filter_by(category_id=category_obj.id).order_by(Subcategory.id.asc()).first()
    if subcategory_obj:
        return subcategory_obj

    subcategory_obj = Subcategory(name="General Updates", category_id=category_obj.id)
    db.session.add(subcategory_obj)
    db.session.flush()
    return subcategory_obj


def _load_category_and_tag_choices():
    categories = Category.query.order_by(Category.name.asc()).all()
    if not categories:
        categories = [_get_or_create_default_category()]
        db.session.commit()

    tags = Tag.query.order_by(Tag.name.asc()).all()
    return categories, tags


def _format_time_only(created_at):
    if not created_at:
        return ""
    return created_at.strftime("%I:%M %p").lstrip("0")


def _serialize_dashboard_post(post_obj):
    normalized_status = (post_obj.status or "draft").strip().lower()
    if normalized_status == "published":
        status_label = "published"
        badge_class = "success"
    else:
        status_label = "drafts"
        badge_class = "warning"

    return {
        "title": post_obj.title,
        "time": _format_time_only(post_obj.created_at),
        "status": status_label,
        "badge_class": badge_class,
    }


@app.route("/wakadobe/admin/signup", methods=["GET", "POST"])
@limiter.limit(
    "3 per hour",
    methods=["POST"],
    error_message="Too many admin signup attempts from your IP. Please try again in an hour.",
)
def admin_signup():
    # Allow public signup for admin accounts (not protected by admin session)
    form = CreateAdminAccountForm()
    if request.method == "GET":
        return render_template("admin/admin_signup.html", form=form, form_error=None, form_success=None)

    if not form.validate_on_submit():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Please fix invalid fields and try again."
        return render_template("admin/admin_signup.html", form=form, form_error=first_error, form_success=None)

    # Create new admin
    hashed_password = generate_password_hash(form.password.data)
    new_admin = Admin(
        name=form.name.data.strip(),
        email=form.email.data.strip().lower(),
        password=hashed_password,
        role=form.role.data or "admin"
    )

    try:
        db.session.add(new_admin)
        db.session.commit()

        # Show success message (don't auto-login for security)
        return render_template("admin/admin_signup.html", form=CreateAdminAccountForm(), form_error=None, form_success="Admin account created successfully! You can now log in.")

    except Exception as e:
        db.session.rollback()
        return render_template("admin/admin_signup.html", form=form, form_error="Failed to create admin account. Please try again.", form_success=None)


@app.route("/wakadobe/admin/login", methods=["GET", "POST"])
@limiter.limit(
    "5 per 10 minutes",
    methods=["POST"],
    error_message="Too many admin login attempts from your IP. Please try again in 10 minutes.",
)
def admin_login():
    if session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin"))

    form = AdminLoginForm()
    show_created = request.args.get("created") == "1"
    if request.method == "GET":
        return render_template("admin/login.html", form=form, form_error=None, show_created=show_created)

    if not form.validate_on_submit():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Please fix invalid fields and try again."
        return render_template("admin/login.html", form=form, form_error=first_error, show_created=False)

    input_email = (form.email.data or "").strip().lower()
    admin_obj = Admin.query.filter(func.lower(Admin.email) == input_email).first()
    candidate = form.password.data or ""
    authenticated = False
    if admin_obj and candidate:
        stored = admin_obj.password or ""
        try:
            authenticated = check_password_hash(stored, candidate)
        except ValueError:
            pass
        if not authenticated and stored == candidate:
            admin_obj.password = generate_password_hash(candidate)
            db.session.commit()
            authenticated = True
    if not authenticated:
        return render_template("admin/login.html", form=form, form_error="Invalid email or password.", show_created=False)

    session[ADMIN_SESSION_KEY] = admin_obj.id

    next_url = request.args.get("next", "")
    if next_url.startswith("/wakadobe/admin"):
        return redirect(next_url)
    return redirect(url_for("admin"))


@app.route("/wakadobe/admin")
def admin():
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    recent_posts = (
        Post.query
        .order_by(Post.created_at.desc())
        .limit(8)
        .all()
    )
    payload = [_serialize_dashboard_post(item) for item in recent_posts]
    return render_template("admin/dashboard.html", recent_posts=payload)


@app.route("/wakadobe/admin/settings", methods=["GET", "POST"])
def admin_settings():
    admin_id = session.get(ADMIN_SESSION_KEY)
    if not admin_id:
        return redirect(url_for("admin_login", next=request.path))
    admin_obj = Admin.query.get(admin_id)
    if admin_obj is None:
        session.pop(ADMIN_SESSION_KEY, None)
        return redirect(url_for("admin_login"))

    form = UpdateProfileForm(current_admin_id=admin_obj.id)

    if request.method == "GET":
        form.name.data = admin_obj.name
        form.email.data = admin_obj.email
        return render_template("admin/settings.html", form=form, form_success=None, form_error=None)

    if form.validate_on_submit():
        admin_obj.name = (form.name.data or "").strip()
        admin_obj.email = (form.email.data or "").strip().lower()
        if form.password.data:
            admin_obj.password = generate_password_hash(form.password.data)
        db.session.commit()

        form.password.data = ""
        form.confirm_password.data = ""
        return render_template(
            "admin/settings.html",
            form=form,
            form_success="Profile updated successfully.",
            form_error=None,
        )

    first_error = next(iter(form.errors.values()))[0] if form.errors else "Please fix invalid fields and try again."
    return render_template("admin/settings.html", form=form, form_success=None, form_error=first_error)


@app.route("/wakadobe/admin/create-account", methods=["GET", "POST"])
def admin_create_account():
    bootstrap_mode = Admin.query.count() == 0
    if not bootstrap_mode and not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    form = CreateAdminAccountForm()

    if request.method == "GET":
        return _render_create_account_page(form, bootstrap_mode=bootstrap_mode)

    if form.validate_on_submit():
        admin_obj = Admin(
            name=(form.name.data or "").strip(),
            email=(form.email.data or "").strip().lower(),
            role="admin" if bootstrap_mode else (form.role.data or "reader").strip().lower(),
            password=generate_password_hash(form.password.data),
        )
        db.session.add(admin_obj)
        db.session.commit()

        if bootstrap_mode:
            return redirect(url_for("admin_login", created=1))

        session.pop(ADMIN_SESSION_KEY, None)
        return redirect(url_for("admin_login"))

    first_error = next(iter(form.errors.values()))[0] if form.errors else "Please fix invalid fields and try again."
    return _render_create_account_page(form, form_error=first_error, bootstrap_mode=bootstrap_mode)


@app.route("/wakadobe/admin/comments")
def admin_comments():
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    return _render_comments_page()


@app.route("/wakadobe/admin/comments/<int:comment_id>/approve", methods=["POST"])
def approve_comment(comment_id):
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    comment_obj = Comment.query.get(comment_id)
    if comment_obj is None:
        return _render_comments_page(form_error="Comment not found.")

    comment_obj.is_approved = True
    comment_obj.flagged_at = None
    db.session.commit()
    return _render_comments_page(form_success="Comment approved.")


@app.route("/wakadobe/admin/comments/<int:comment_id>/flag", methods=["POST"])
def flag_comment(comment_id):
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    comment_obj = Comment.query.get(comment_id)
    if comment_obj is None:
        return _render_comments_page(form_error="Comment not found.")

    comment_obj.is_approved = False
    comment_obj.flagged_at = datetime.utcnow()
    db.session.commit()
    return _render_comments_page(form_success="Comment flagged. It will be deleted after two days if not restored.")


@app.route("/wakadobe/admin/comments/purge-flagged", methods=["POST"])
def purge_flagged_comments():
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))

    cutoff = datetime.utcnow() - timedelta(days=2)
    deleted = Comment.query.filter(
        Comment.is_approved.is_(False),
        Comment.flagged_at.is_not(None),
        Comment.flagged_at <= cutoff,
    ).delete(synchronize_session=False)
    db.session.commit()

    return _render_comments_page(form_success=f"Purged {deleted} expired flagged comment(s).")


@app.route("/wakadobe/admin/categories")
def admin_categories():
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    return _render_categories_page()


@app.route("/wakadobe/admin/categories/create-category", methods=["POST"])
def create_category():
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    name = _normalize_label(request.form.get("name"))
    if not name:
        return _render_categories_page(form_error="Category name is required.")

    existing = Category.query.filter(func.lower(Category.name) == name.lower()).first()
    if existing:
        return _render_categories_page(form_error="Category already exists.")

    db.session.add(Category(name=name))
    db.session.commit()
    return _render_categories_page(form_success="Category added successfully.")


@app.route("/wakadobe/admin/categories/create-subcategory", methods=["POST"])
def create_subcategory():
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    name = _normalize_label(request.form.get("name"))
    category_id = request.form.get("category_id", type=int)

    if not name:
        return _render_categories_page(form_error="Sub-category name is required.")
    if not category_id:
        return _render_categories_page(form_error="Please select a category for the sub-category.")

    category_obj = Category.query.get(category_id)
    if category_obj is None:
        return _render_categories_page(form_error="Selected category does not exist.")

    existing = Subcategory.query.filter(
        Subcategory.category_id == category_id,
        func.lower(Subcategory.name) == name.lower(),
    ).first()
    if existing:
        return _render_categories_page(form_error="Sub-category already exists in this category.")

    db.session.add(Subcategory(name=name, category_id=category_id))
    db.session.commit()
    return _render_categories_page(form_success="Sub-category added successfully.")


@app.route("/wakadobe/admin/categories/create-tag", methods=["POST"])
def create_tag():
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    name = _normalize_label(request.form.get("name"))
    if not name:
        return _render_categories_page(form_error="Tag name is required.")

    existing = Tag.query.filter(func.lower(Tag.name) == name.lower()).first()
    if existing:
        return _render_categories_page(form_error="Tag already exists.")

    db.session.add(Tag(name=name))
    db.session.commit()
    return _render_categories_page(form_success="Tag added successfully.")


@app.route("/wakadobe/admin/categories/<int:category_id>/update", methods=["POST"])
def update_category(category_id):
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    category_obj = Category.query.get(category_id)
    if category_obj is None:
        return _render_categories_page(form_error="Category not found.")

    name = _normalize_label(request.form.get("name"))
    if not name:
        return _render_categories_page(form_error="Category name is required.")

    existing = Category.query.filter(
        Category.id != category_id,
        func.lower(Category.name) == name.lower(),
    ).first()
    if existing:
        return _render_categories_page(form_error="Another category already uses this name.")

    category_obj.name = name
    db.session.commit()
    return _render_categories_page(form_success="Category updated successfully.")


@app.route("/wakadobe/admin/categories/<int:category_id>/delete", methods=["GET", "POST"])
def delete_category(category_id):
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    category_obj = Category.query.get(category_id)
    if category_obj is None:
        return _render_categories_page(form_error="Category not found.")

    if Subcategory.query.filter_by(category_id=category_id).count() > 0:
        return _render_categories_page(form_error="Cannot delete category with sub-categories. Remove sub-categories first.")

    db.session.delete(category_obj)
    db.session.commit()
    return _render_categories_page(form_success="Category deleted successfully.")


@app.route("/wakadobe/admin/subcategories/<int:subcategory_id>/update", methods=["POST"])
def update_subcategory(subcategory_id):
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    subcategory_obj = Subcategory.query.get(subcategory_id)
    if subcategory_obj is None:
        return _render_categories_page(form_error="Sub-category not found.")

    name = _normalize_label(request.form.get("name"))
    category_id = request.form.get("category_id", type=int)

    if not name:
        return _render_categories_page(form_error="Sub-category name is required.")
    if not category_id:
        return _render_categories_page(form_error="Please select a category for the sub-category.")

    category_obj = Category.query.get(category_id)
    if category_obj is None:
        return _render_categories_page(form_error="Selected category does not exist.")

    existing = Subcategory.query.filter(
        Subcategory.id != subcategory_id,
        Subcategory.category_id == category_id,
        func.lower(Subcategory.name) == name.lower(),
    ).first()
    if existing:
        return _render_categories_page(form_error="Another sub-category with this name already exists in that category.")

    subcategory_obj.name = name
    subcategory_obj.category_id = category_id
    db.session.commit()
    return _render_categories_page(form_success="Sub-category updated successfully.")


@app.route("/wakadobe/admin/subcategories/<int:subcategory_id>/delete", methods=["GET", "POST"])
def delete_subcategory(subcategory_id):
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    subcategory_obj = Subcategory.query.get(subcategory_id)
    if subcategory_obj is None:
        return _render_categories_page(form_error="Sub-category not found.")

    if Post.query.filter_by(subcategory_id=subcategory_id).count() > 0:
        return _render_categories_page(form_error="Cannot delete sub-category linked to posts.")

    db.session.delete(subcategory_obj)
    db.session.commit()
    return _render_categories_page(form_success="Sub-category deleted successfully.")


@app.route("/wakadobe/admin/tags/<int:tag_id>/update", methods=["POST"])
def update_tag(tag_id):
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    tag_obj = Tag.query.get(tag_id)
    if tag_obj is None:
        return _render_categories_page(form_error="Tag not found.")

    name = _normalize_label(request.form.get("name"))
    if not name:
        return _render_categories_page(form_error="Tag name is required.")

    existing = Tag.query.filter(
        Tag.id != tag_id,
        func.lower(Tag.name) == name.lower(),
    ).first()
    if existing:
        return _render_categories_page(form_error="Another tag already uses this name.")

    tag_obj.name = name
    db.session.commit()
    return _render_categories_page(form_success="Tag updated successfully.")


@app.route("/wakadobe/admin/tags/<int:tag_id>/delete", methods=["GET", "POST"])
def delete_tag(tag_id):
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    tag_obj = Tag.query.get(tag_id)
    if tag_obj is None:
        return _render_categories_page(form_error="Tag not found.")

    if tag_obj.posts.count() > 0:
        return _render_categories_page(form_error="Cannot delete tag linked to posts.")

    db.session.delete(tag_obj)
    db.session.commit()
    return _render_categories_page(form_success="Tag deleted successfully.")


@app.route("/wakadobe/admin/drafts")
def admin_drafts():
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    drafts = (
        Post.query.filter_by(status="draft")
        .order_by(Post.created_at.desc())
        .all()
    )
    payload = [_serialize_admin_draft(item) for item in drafts]
    return render_template("admin/drafts.html", drafts=payload)


@app.route("/wakadobe/admin/drafts/<int:post_id>/preview")
def preview_draft(post_id):
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    post_obj = Post.query.filter_by(id=post_id, status="draft").first()
    if post_obj is None:
        abort(404)

    post_payload = {
        "id": post_obj.id,
        "title": post_obj.title,
        "author": post_obj.author.name if post_obj.author else "Wakadobe",
        "date": _format_post_date(post_obj.created_at),
        "category": _get_post_category(post_obj),
        "image": post_obj.cover_image or "/static/city.jpg",
        "excerpt": (post_obj.excerpt or "").strip(),
        "content_html": post_obj.content or "",
        "tags": [tag.name for tag in post_obj.tags],
    }
    return render_template("admin/draft_preview.html", post=post_payload)


@app.route("/wakadobe/admin/create-post", methods=["GET", "POST"])
def create_post():
    admin_id = session.get(ADMIN_SESSION_KEY)
    if not admin_id:
        return redirect(url_for("admin_login", next=request.path))
    categories, tags = _load_category_and_tag_choices()
    subcategories = (
        Subcategory.query
        .join(Category, Category.id == Subcategory.category_id)
        .order_by(Category.name.asc(), Subcategory.name.asc())
        .all()
    )
    # print(subcategories)
    form = CreatePostForm()
    form.category_id.choices = [(category.id, category.name) for category in categories]
    form.subcategory_id.choices = [(subcategory.id, subcategory.name) for subcategory in subcategories]
    form.tag_ids.choices = [(tag.id, tag.name) for tag in tags]

    draft_id = request.args.get("draft_id", type=int)
    editing_post = None
    if draft_id:
        editing_post = Post.query.filter_by(id=draft_id, status="draft").first()
        if editing_post:
            form.draft_id.data = str(editing_post.id)
            form.title.data = editing_post.title
            form.excerpt.data = editing_post.excerpt
            form.content_html.data = editing_post.content
            if editing_post.subcategory:
                form.subcategory_id.data = editing_post.subcategory.id
                if editing_post.subcategory.category:
                    form.category_id.data = editing_post.subcategory.category.id
            form.tag_ids.data = [tag.id for tag in editing_post.tags]

    if request.method == "GET":
        return render_template(
            "admin/create_post.html",
            form=form,
            categories=categories,
            subcategories=subcategories,
            tags=tags,
        )

    if not form.validate_on_submit():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Please fix the errors and try again."
        return render_template(
            "admin/create_post.html",
            form=form,
            form_error=first_error,
            categories=categories,
            subcategories=subcategories,
            tags=tags,
        )

    title = (form.title.data or "").strip()
    excerpt = (form.excerpt.data or "").strip()
    content_html = (form.content_html.data or "").strip()
    category_id = form.category_id.data
    selected_tag_ids = getattr(form, "valid_tag_ids", form.tag_ids.data or [])
    new_tags = getattr(form, "normalized_new_tags", [])
    post_status = (form.post_status.data or "published").strip().lower()
    editing_draft_id = form.draft_id.data

    cover_path = _save_uploaded_image(form.cover_image.data)

    valid_status = "draft" if post_status == "draft" else "published"

    admin_obj = Admin.query.get(admin_id)

    category_obj = None
    if category_id:
        category_obj = Category.query.get(category_id)
    if category_obj is None:
        category_obj = _get_or_create_default_category()

    subcategory_obj = None
    if form.subcategory_id.data:
        subcategory_obj = Subcategory.query.get(form.subcategory_id.data)
        if subcategory_obj is not None and subcategory_obj.category_id != category_obj.id:
            subcategory_obj = None
    if subcategory_obj is None:
        subcategory_obj = _get_or_create_default_subcategory(category_obj)

    tags = []
    if selected_tag_ids:
        tags = Tag.query.filter(Tag.id.in_(selected_tag_ids)).all()

    if new_tags:
        for clean_name in new_tags:
            existing = Tag.query.filter_by(name=clean_name).first()
            if existing:
                if existing not in tags:
                    tags.append(existing)
                continue
            tag_obj = Tag(name=clean_name)
            db.session.add(tag_obj)
            db.session.flush()
            tags.append(tag_obj)

    post_obj = None
    if editing_draft_id and str(editing_draft_id).isdigit():
        post_obj = Post.query.filter_by(id=int(editing_draft_id), status="draft").first()

    if post_obj is None:
        post_obj = Post(
            title=title,
            excerpt=excerpt,
            cover_image=cover_path,
            content=content_html,
            admin_id=admin_obj.id,
            subcategory_id=subcategory_obj.id,
            status=valid_status,
        )
    else:
        post_obj.title = title
        post_obj.excerpt = excerpt
        post_obj.content = content_html
        post_obj.subcategory_id = subcategory_obj.id
        post_obj.status = valid_status
        if cover_path:
            post_obj.cover_image = cover_path
        post_obj.tags.clear()

    for tag in tags:
        post_obj.tags.append(tag)

    db.session.add(post_obj)
    db.session.commit()

    return redirect(url_for("admin"))


@app.route("/wakadobe/admin/upload-inline-image", methods=["POST"])
def upload_inline_image():
    if not session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin_login", next=request.path))
    uploaded = request.files.get("image")
    if uploaded and _get_file_size_bytes(uploaded) > MAX_UPLOAD_IMAGE_BYTES:
        return jsonify({"error": "Image is too large. Max allowed is 5MB."}), 400

    image_url = _save_uploaded_image(uploaded)
    if not image_url:
        return jsonify({"error": "Invalid image file."}), 400

    return jsonify({"url": image_url})


@app.route("/wakadobe/admin/log-out")
def log_out():
    session.pop(ADMIN_SESSION_KEY, None)
    return redirect(url_for("admin_login"))
