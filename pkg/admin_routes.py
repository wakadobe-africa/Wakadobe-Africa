from datetime import datetime, timedelta
import email

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash

from pkg import app
from pkg.blogmodel import Admin, Category, Comment, Post, Subcategory, Tag, db
from pkg.token import generate_admin_otp, send_admin_otp_email, verify_admin_otp
from pkg.forms import (
    AdminLoginForm,
    AdminOTPForm,
    AdminResetPasswordForm,
    AdminResetPasswordRequestForm,
    CreateAdminAccountForm,
    CreatePostForm,
    MAX_UPLOAD_IMAGE_BYTES,
    UpdateProfileForm,
    _get_file_size_bytes,
)
from pkg.helpers import (
    _format_post_date,
    _serialize_admin_user,
    _render_create_account_page,
    _get_comment_status,
    _serialize_admin_comment,
    _render_comments_page,
    _normalize_label,
    _render_categories_page,
    _allowed_image,
    _save_uploaded_image,
    _upload_cover_image,
    _get_post_category,
    _serialize_admin_draft,
    _get_or_create_default_category,
    _get_or_create_default_subcategory,
    _load_category_and_tag_choices,
    _serialize_dashboard_post,
    _format_time_only
    
)
from pkg.limiter import limiter
from pkg.route_constants import ADMIN_PENDING_OTP_KEY, ADMIN_SESSION_KEY
from pkg.token import generate_admin_otp, verify_admin_otp




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

    pending_data = {
        "action": "signup",
        "name": (form.name.data or "").strip(),
        "email": (form.email.data or "").strip().lower(),
        "role": form.role.data or "admin",
        "password_hash": generate_password_hash(form.password.data),
    }
    session[ADMIN_PENDING_OTP_KEY] = pending_data
    otp_code = generate_admin_otp(pending_data["email"])
    send_admin_otp_email(pending_data["email"], otp_code)
    # For testing in production temporarily
    flash(f"DEBUG MODE - Your Verification Code is: {otp_code}", "info")
    
    # Safely log it to Render logs using standard logging to avoid context errors
    print(f"DEBUG OTP for {pending_data['email']}: {otp_code}")
    return redirect(url_for("admin_verify", action="signup"))


@app.route("/wakadobe/admin/login", methods=["GET", "POST"])
@limiter.limit(
    "5 per 10 minutes",
    methods=["POST"],
    error_message="Too many admin login attempts",
)
def admin_login():
    if session.get(ADMIN_SESSION_KEY):
        return redirect(url_for("admin"))

    form = AdminLoginForm()
    show_created = request.args.get("created") == "1"
    show_reset_success = request.args.get("reset") == "1"
    if request.method == "GET":
        return render_template("admin/login.html", form=form, form_error=None, show_created=show_created, show_reset_success=show_reset_success)

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
        return render_template("admin/login.html", form=form, form_error="Invalid email or password.", show_created=False, show_reset_success=False)

    pending_data = {
        "action": "login",
        "admin_id": admin_obj.id,
        "email": admin_obj.email,
        "next_url": request.args.get("next", ""),
    }
    session[ADMIN_PENDING_OTP_KEY] = pending_data
    otp_code = generate_admin_otp(admin_obj.email)
    send_admin_otp_email(admin_obj.email, otp_code)
    # For testing in production temporarily
    flash(f"DEBUG MODE - Your Verification Code is: {otp_code}", "info")
    
    # Safely log it to Render logs using standard logging to avoid context errors
    print(f"DEBUG OTP for {pending_data['email']}: {otp_code}")
    return redirect(url_for("admin_verify", action="login"))


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
        pending_data = {
            "action": "create_account",
            "name": (form.name.data or "").strip(),
            "email": (form.email.data or "").strip().lower(),
            "role": "admin" if bootstrap_mode else (form.role.data or "author").strip().lower(),
            "password_hash": generate_password_hash(form.password.data),
        }
        session[ADMIN_PENDING_OTP_KEY] = pending_data
        otp_code = generate_admin_otp(pending_data["email"])
        send_admin_otp_email(pending_data["email"], otp_code)
        return redirect(url_for("admin_verify", action="create_account"))

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


@app.route("/wakadobe/admin/reset-password", methods=["GET", "POST"])
@limiter.limit(
    "3 per hour",
    methods=["POST"],
    error_message="Too many admin reset attempts from your IP. Please try again in an hour.",
)
def admin_reset_password():
    form = AdminResetPasswordRequestForm()
    if request.method == "GET":
        return render_template("admin/admin_reset_password.html", form=form, form_error=None, form_success=None)

    if not form.validate_on_submit():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Please fix invalid fields and try again."
        return render_template("admin/admin_reset_password.html", form=form, form_error=first_error, form_success=None)

    email = form.email.data
    pending_data = {
        "action": "reset_password",
        "email": email,
    }
    session[ADMIN_PENDING_OTP_KEY] = pending_data
    admin_obj = Admin.query.filter(func.lower(Admin.email) == email).first()
    if admin_obj:
        otp_code = generate_admin_otp(admin_obj.email)
        send_admin_otp_email(admin_obj.email, otp_code)

    return redirect(url_for("admin_verify", action="reset_password"))


@app.route("/wakadobe/admin/verify", methods=["GET", "POST"])
def admin_verify():
    pending = session.get(ADMIN_PENDING_OTP_KEY)
    if not pending:
        return redirect(url_for("admin_login"))

    action = request.args.get("action") or pending.get("action")
    otp_form = AdminOTPForm()
    reset_form = AdminResetPasswordForm() if action == "reset_password" else None

    if request.method == "GET":
        return render_template(
            "admin/verify_admin.html",
            action=action,
            otp_form=otp_form,
            reset_form=reset_form,
            form_error=None,
            message="A verification code was sent to the email address provided.",
        )

    if not otp_form.validate_on_submit():
        first_error = next(iter(otp_form.errors.values()))[0] if otp_form.errors else "Please enter the verification code."
        return render_template(
            "admin/verify_admin.html",
            action=action,
            otp_form=otp_form,
            reset_form=reset_form,
            form_error=first_error,
            message=None,
        )

    email = (pending.get("email") or "").strip().lower()
    if not verify_admin_otp(email, otp_form.otp_code.data):
        return render_template(
            "admin/verify_admin.html",
            action=action,
            otp_form=otp_form,
            reset_form=reset_form,
            form_error="Invalid or expired verification code.",
            message=None,
        )

    if action in {"signup", "create_account"}:
        existing = Admin.query.filter(func.lower(Admin.email) == email).first()
        if existing:
            session.pop(ADMIN_PENDING_OTP_KEY, None)
            return render_template(
                "admin/verify_admin.html",
                action=action,
                otp_form=otp_form,
                reset_form=reset_form,
                form_error="An admin account with that email already exists.",
                message=None,
            )

        name = pending.get("name")
        role = pending.get("role", "admin")
        password_hash = pending.get("password_hash")
        if not name or not password_hash:
            session.pop(ADMIN_PENDING_OTP_KEY, None)
            return redirect(url_for("admin_login"))

        admin_obj = Admin(name=name, email=email, role=role, password=password_hash)
        db.session.add(admin_obj)
        db.session.commit()
        session.pop(ADMIN_PENDING_OTP_KEY, None)

        if action == "signup":
            return redirect(url_for("admin_login", created=1))

        return render_template(
            "admin/create_account.html",
            form=CreateAdminAccountForm(),
            admins=[_serialize_admin_user(item) for item in Admin.query.order_by(Admin.created_at.desc(), Admin.id.desc()).all()],
            form_error=None,
            form_success="Admin account created successfully.",
            bootstrap_mode=False,
        )

    if action == "login":
        session[ADMIN_SESSION_KEY] = pending.get("admin_id")
        next_url = pending.get("next_url", "")
        session.pop(ADMIN_PENDING_OTP_KEY, None)
        if next_url.startswith("/wakadobe/admin"):
            return redirect(next_url)
        return redirect(url_for("admin"))

    if action == "reset_password" and reset_form:
        if not reset_form.validate_on_submit():
            first_error = next(iter(reset_form.errors.values()))[0] if reset_form.errors else "Please correct the reset information."
            return render_template(
                "admin/verify_admin.html",
                action=action,
                otp_form=otp_form,
                reset_form=reset_form,
                form_error=first_error,
                message=None,
            )

        admin_obj = Admin.query.filter(func.lower(Admin.email) == email).first()
        if admin_obj:
            admin_obj.password = generate_password_hash(reset_form.new_password.data)
            db.session.add(admin_obj)
            db.session.commit()

        session.pop(ADMIN_PENDING_OTP_KEY, None)
        return redirect(url_for("admin_login", reset=1))

    session.pop(ADMIN_PENDING_OTP_KEY, None)
    return redirect(url_for("admin_login"))


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

    cover_path = _upload_cover_image(form.cover_image.data)

    valid_status = "draft" if post_status == "draft" else "published"

    category_obj = Category.query.get(category_id) if category_id else None
    if category_obj is None:
        category_obj = _get_or_create_default_category()

    subcat_map = {subcat.id: subcat for subcat in subcategories}
    chosen_subcat = subcat_map.get(form.subcategory_id.data)
    if chosen_subcat and chosen_subcat.category_id == category_obj.id:
        subcategory_obj = chosen_subcat
    else:
        subcategory_obj = _get_or_create_default_subcategory(category_obj)

    post_tags = Tag.query.filter(Tag.id.in_(selected_tag_ids)).all() if selected_tag_ids else []
    for clean_name in new_tags:
        existing = Tag.query.filter_by(name=clean_name).first()
        if not existing:
            existing = Tag(name=clean_name)
            db.session.add(existing)
            db.session.flush()
        if existing not in post_tags:
            post_tags.append(existing)

    post_obj = None
    if editing_draft_id and str(editing_draft_id).isdigit():
        post_obj = Post.query.filter_by(id=int(editing_draft_id), status="draft").first()

    if post_obj is None:
        post_obj = Post(
            admin_id=admin_id,
            title=title,
            excerpt=excerpt,
            cover_image=cover_path,
            content=content_html,
            subcategory_id=subcategory_obj.id,
            status=valid_status,
        )
        db.session.add(post_obj)
    else:
        post_obj.title = title
        post_obj.excerpt = excerpt
        post_obj.content = content_html
        post_obj.subcategory_id = subcategory_obj.id
        post_obj.status = valid_status
        if cover_path:
            post_obj.cover_image = cover_path

    post_obj.tags = post_tags
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
