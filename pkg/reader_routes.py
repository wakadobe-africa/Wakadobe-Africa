from flask import abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from pkg import app
from pkg.blogmodel import Category, Comment, Post, Reader, Subcategory, db
from pkg.token import generate_email_address_verify, send_email, verify_signup_token
from pkg.forms import PasswordResetEmailForm, ReaderLoginForm, ReaderResetPasswordForm, ReaderSignupForm, _strip_html
from pkg.helpers import (
    _format_post_date,
    _get_post_category,
    _serialize_post_card,
    _serialize_subcategory_option,
    
)
from pkg.limiter import limiter
from pkg.route_constants import READER_SESSION_KEY


@app.route("/")
def wakadobe_index():
    latest_posts_objs = (
        Post.query.filter_by(status="published")
        .order_by(Post.created_at.desc())
        .limit(2)
        .all()
    )

    latest_ids = {p.id for p in latest_posts_objs}

    popular_posts_objs = (
        Post.query
        .filter(Post.status == "published", Post.id.notin_(latest_ids))
        .order_by(func.rand())
        .all()
    )

    subcategories = (
        Subcategory.query
        .join(Post, Post.subcategory_id == Subcategory.id)
        .filter(Post.status == "published")
        .order_by(Subcategory.name.asc())
        .distinct()
        .all()
    )

    return render_template(
        "user/index.html",
        latest_posts=[_serialize_post_card(p) for p in latest_posts_objs],
        popular_posts=[_serialize_post_card(p) for p in popular_posts_objs],
        subcategories=[_serialize_subcategory_option(s) for s in subcategories],
    )


@app.route("/wakadobe/subcategories/<int:subcategory_id>/posts")
def subcategory_posts(subcategory_id):
    subcategory = Subcategory.query.get_or_404(subcategory_id)
    post_rows = (
        Post.query
        .filter_by(subcategory_id=subcategory.id, status="published")
        .order_by(Post.created_at.desc())
        .all()
    )
    return {
        "subcategory": _serialize_subcategory_option(subcategory),
        "posts": [_serialize_post_card(item) for item in post_rows],
    }


@app.route("/wakadobe/posts/<int:post_id>", defaults={"slug": None})
@app.route("/wakadobe/posts/<int:post_id>/<slug>")
def post_details(post_id, slug=None):
    post_obj = Post.query.filter_by(id=post_id, status="published").first()
    if post_obj is None:
        abort(404)
    if slug is None or slug != post_obj.slug:
        return redirect(url_for("post_details", post_id=post_obj.id, slug=post_obj.slug), 301)

    related_query = Post.query.filter(Post.id != post_obj.id, Post.status == "published")
    if post_obj.subcategory_id:
        related_query = related_query.filter(Post.subcategory_id == post_obj.subcategory_id)

    related_posts = [
        _serialize_post_card(item)
        for item in related_query.order_by(Post.created_at.desc()).limit(3).all()
    ]

    approved_comments = Comment.query.filter_by(post_id=post_id, is_approved=True).order_by(Comment.created_at.asc()).all()
    comment_records = [
        {
            "id": comment.id,
            "parent_id": comment.parent_id,
            "reader_name": comment.reader.name if comment.reader else "Anonymous",
            "content": comment.content,
            "date": _format_post_date(comment.created_at),
        }
        for comment in approved_comments
    ]

    comment_tree = {}
    for comment in comment_records:
        comment_tree.setdefault(comment["parent_id"], []).append(comment)

    comments_payload = comment_tree.get(None, [])
    comment_count = len(comment_records)

    post_payload = {
        "id": post_obj.id,
        "title": post_obj.title,
        "author": post_obj.author.name if post_obj.author else "Wakadobe",
        "date": _format_post_date(post_obj.created_at),
        "category": _get_post_category(post_obj),
        "image": post_obj.cover_image or "/static/city.jpg",
        "content_html": post_obj.content or "",
        "slug": post_obj.slug,
        "tags": [tag.name for tag in post_obj.tags],
    }
    reader_id = session.get(READER_SESSION_KEY)
    current_reader = Reader.query.get(reader_id) if reader_id else None
    return render_template(
        "user/post_contents.html",
        post=post_payload,
        related_posts=related_posts,
        comments=comments_payload,
        comment_tree=comment_tree,
        comment_count=comment_count,
        current_reader=current_reader,
    )


@app.route("/wakadobe/posts/<int:post_id>/<slug>/comment", methods=["POST"])
def add_comment(post_id, slug):
    post_obj = Post.query.filter_by(id=post_id, status="published").first()
    if post_obj is None:
        abort(404)
    if slug != post_obj.slug:
        return redirect(url_for("post_details", post_id=post_obj.id, slug=post_obj.slug), 301)

    reader_id = session.get(READER_SESSION_KEY)
    if not reader_id:
        return redirect(url_for("reader_login"))
    current_reader = Reader.query.get(reader_id)

    comment_text = request.form.get("comment", "").strip()
    if not comment_text:
        return redirect(url_for("post_details", post_id=post_id, slug=post_obj.slug))

    parent_id = request.form.get("parent_id")
    if parent_id:
        try:
            parent_id = int(parent_id)
        except (TypeError, ValueError):
            parent_id = None
        else:
            parent_comment = Comment.query.filter_by(id=parent_id, post_id=post_id, is_approved=True).first()
            if parent_comment is None:
                parent_id = None
    else:
        parent_id = None

    new_comment = Comment(
        content=comment_text,
        post_id=post_id,
        reader_id=current_reader.id,
        parent_id=parent_id,
        is_approved=True,
    )
    db.session.add(new_comment)
    db.session.commit()

    return redirect(url_for("post_details", post_id=post_id, slug=post_obj.slug) + f"#comment-{new_comment.id}")


@app.route("/wakadobe/about")
def about():
    return render_template("user/about.html")

@app.route("/wakadobe/readers/verify-signup-email")
def verify_signup_email():
    token = request.args.get('token')
    email = verify_signup_token(token, salt="email-verify")
    if email is None:
        flash("Invalid or expired verification link.", "danger")
        return redirect(url_for("reader_signup"))
    
    reader_obj = Reader.query.filter(func.lower(Reader.email) == email.lower()).first()
    if reader_obj is None:
        flash("No account found for this email. Please sign up.", "danger")
        return redirect(url_for("reader_signup"))
    reader_obj.is_email_verified = True
    db.session.add(reader_obj)
    db.session.commit()
    flash("Email verified successfully! You may continue browsing.", "success")
    return redirect(url_for("wakadobe_index"))


@app.route("/wakadobe/readers/sign-up", methods=["GET", "POST"])
def reader_signup():
    # abort(404)  # Disable public sign-up by returning 404
    if session.get(READER_SESSION_KEY):
        return redirect(url_for("wakadobe_index"))
    
    form = ReaderSignupForm()
    if request.method == "GET":
        return render_template("user/reader_signup.html", form=form, form_error=None)
    if not form.validate_on_submit():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Please fill the required fields and try again."
        return render_template("user/reader_signup.html", form=form, form_error=first_error)
    
    reader_obj = Reader(
        name=(form.name.data or "").strip(),
        email=(form.email.data or "").strip().lower(),
        password=generate_password_hash(form.password.data),
    )
    db.session.add(reader_obj)
    db.session.commit()
    verification_url = url_for(
    "verify_signup_email", 
    token=generate_email_address_verify(reader_obj.email, salt="email-verify"), 
    _external=True
    )
    send_email(reader_obj.email, verification_url)
    flash("Account created successfully! Please log in.")
    return redirect(url_for("reader_login", created=1))


@app.route("/wakadobe/readers/login", methods=["GET", "POST"])
@limiter.limit(
    "5 per 10 minutes",
    methods=["POST"],
    error_message="Too many login attempts. Please try again in 10 minutes.",
)
def reader_login():
    # abort(404)  # Disable public login by returning 404
    if session.get(READER_SESSION_KEY):
        return redirect(url_for("wakadobe_index"))
    
    form = ReaderLoginForm()
    resetform = PasswordResetEmailForm()
    show_created = request.args.get("created") == "1"
    show_reset_sent = request.args.get("reset_sent") == "1"
    show_reset_success = request.args.get("reset_done") == "1"

    if request.method == "GET":
        return render_template(
            "user/reader_login.html",
            form=form,
            resetform=resetform,
            form_error=None,
            show_created=show_created,
            show_reset_sent=show_reset_sent,
            show_reset_success=show_reset_success,
        )

    if not form.validate_on_submit():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Invalid email or password."
        return render_template(
            "user/reader_login.html",
            form=form,
            resetform=resetform,
            form_error=first_error,
            show_created=False,
            show_reset_sent=False,
            show_reset_success=False,
        )

    input_email = (form.email.data or "").strip().lower()
    reader_obj = Reader.query.filter(func.lower(Reader.email) == input_email).first()
    candidate = form.password.data or ""
    authenticated = False
    if reader_obj and candidate:
        stored = (reader_obj.password or "").strip()
        try:
            authenticated = check_password_hash(stored, candidate)
        except ValueError:
            pass
        if not authenticated and stored == candidate:
            reader_obj.password = generate_password_hash(candidate)
            db.session.commit()
            authenticated = True
    if not authenticated:
        return render_template(
            "user/reader_login.html",
            form=form,
            resetform=resetform,
            form_error="Invalid email or password.",
            show_created=False,
            show_reset_sent=False,
            show_reset_success=False,
        )

    session[READER_SESSION_KEY] = reader_obj.id
    return redirect(url_for("wakadobe_index"))

@app.route("/wakadobe/readers/reset-password", methods=["GET", "POST"])
def reader_reset_password():
    """Handle password reset with token - shows password reset form and validates new password"""
    if session.get(READER_SESSION_KEY):
        return redirect(url_for("wakadobe_index"))

    # Optimization: Extract and verify the token once for BOTH GET and POST
    token = request.args.get("token")
    if not token:
        flash("Password reset link is invalid.", "danger")
        return redirect(url_for("reader_login"))

    email = verify_signup_token(token, salt="password-reset")
    if email is None:
        flash("Invalid or expired password reset link.", "danger")
        return redirect(url_for("reader_login"))

    form = ReaderResetPasswordForm()

    if request.method == "GET":
        return render_template(
            "user/reset_password.html",
            resetform=form,
            form_error=None,
            token=token,
        )

    # Reset password submission and validation flow
    if not form.validate_on_submit():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Invalid input. Please try again."
        return render_template(
            "user/reset_password.html",
            resetform=form,
            form_error=first_error,
            token=token,
        )

    reader_obj = Reader.query.filter(func.lower(Reader.email) == email.lower()).first()
    if reader_obj is None:
        flash("No account found for this email. Please sign up.", "danger")
        return redirect(url_for("reader_signup"))

    # Security Fix: Use your model's bcrypt abstraction method instead of mixing tools
    reader_obj.password = generate_password_hash(form.new_password.data)
    db.session.add(reader_obj)  
    db.session.commit() 
    
    flash("Password reset successfully! Please log in.", "success")
    return redirect(url_for("reader_login", reset_done=1))


@app.route("/wakadobe/readers/verify-email", methods=["POST"])
def reset_verify_email():
    """Password reset email verification flow - sends reset link to email"""
    if session.get(READER_SESSION_KEY):
        return redirect(url_for("wakadobe_index"))

    form = PasswordResetEmailForm()
    if not form.validate_on_submit():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Please provide a valid email address."
        flash(first_error, "danger")
        return redirect(url_for("reader_login"))

    # Bug Fix: Ensure input email is lowered to match database query logic
    email = form.email.data.lower()
    reader_obj = Reader.query.filter(func.lower(Reader.email) == email).first()
    
    # Excellent practice: Keeping this logic uniform prevents database scraping
    if reader_obj:
        token = generate_email_address_verify(reader_obj.email, salt="password-reset")
        reset_url = url_for("reader_reset_password", token=token, _external=True)
        send_email(reader_obj.email, reset_url)
    
    flash("Password reset link has been sent to your email.", "info")
    return redirect(url_for("reader_login", reset_sent=1))


@app.route("/wakadobe/readers/log-out")
def reader_logout():
    session.pop(READER_SESSION_KEY, None)
    return redirect(url_for("reader_login"))


@app.route("/wakadobe/category/<int:category_id>")
def category_posts(category_id):
    category = Category.query.get_or_404(category_id)

    latest_published = (
        Post.query.filter_by(status="published")
        .order_by(Post.created_at.desc())
        .limit(2)
        .all()
    )
    latest_posts = [_serialize_post_card(p) for p in latest_published]

    cat_published = (
        Post.query
        .join(Subcategory, Post.subcategory_id == Subcategory.id)
        .filter(Subcategory.category_id == category_id, Post.status == "published")
        .order_by(Post.created_at.desc())
        .all()
    )
    cat_posts = [_serialize_post_card(p) for p in cat_published]

    return render_template(
        "user/category_posts.html",
        category=category,
        latest_posts=latest_posts,
        cat_posts=cat_posts,
    )
