from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from pkg import app
from pkg.blogmodel import Category, Comment, Post, Reader, Subcategory, db
from pkg.forms import ReaderLoginForm, ReaderResetPasswordForm, ReaderSignupForm, _strip_html
from pkg.limiter import limiter
from pkg.route_constants import READER_SESSION_KEY


def _format_post_date(created_at):
    if not created_at:
        return ""
    return created_at.strftime("%B %d, %Y").replace(" 0", " ")


def _get_post_category(post_obj):
    if post_obj.subcategory and post_obj.subcategory.category:
        return post_obj.subcategory.category.name
    return "General"


def _serialize_post_card(post_obj):
    excerpt_source = (post_obj.excerpt or "").strip() or _strip_html(post_obj.content)
    excerpt = excerpt_source[:180].rstrip()
    if len(excerpt_source) > 180:
        excerpt = f"{excerpt}..."

    return {
        "id": post_obj.id,
        "title": post_obj.title,
        "author": post_obj.author.name if post_obj.author else "Wakadobe",
        "date": _format_post_date(post_obj.created_at),
        "category": _get_post_category(post_obj),
        "image": post_obj.cover_image or "/static/city.jpg",
        "excerpt": excerpt,
    }


def _serialize_subcategory_option(subcategory_obj):
    if subcategory_obj.category:
        label = f"{subcategory_obj.category.name} - {subcategory_obj.name}"
    else:
        label = subcategory_obj.name
    return {
        "id": subcategory_obj.id,
        "name": subcategory_obj.name,
        "label": label,
    }


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


@app.route("/wakadobe/posts/<int:post_id>")
def post_details(post_id):
    post_obj = Post.query.filter_by(id=post_id, status="published").first()
    if post_obj is None:
        abort(404)

    related_query = Post.query.filter(Post.id != post_obj.id, Post.status == "published")
    if post_obj.subcategory_id:
        related_query = related_query.filter(Post.subcategory_id == post_obj.subcategory_id)

    related_posts = [
        _serialize_post_card(item)
        for item in related_query.order_by(Post.created_at.desc()).limit(3).all()
    ]

    approved_comments = Comment.query.filter_by(post_id=post_id, is_approved=True).order_by(Comment.created_at.desc()).all()
    comments_payload = [
        {
            "id": comment.id,
            "reader_name": comment.reader.name if comment.reader else "Anonymous",
            "content": comment.content,
            "date": _format_post_date(comment.created_at),
        }
        for comment in approved_comments
    ]

    post_payload = {
        "id": post_obj.id,
        "title": post_obj.title,
        "author": post_obj.author.name if post_obj.author else "Wakadobe",
        "date": _format_post_date(post_obj.created_at),
        "category": _get_post_category(post_obj),
        "image": post_obj.cover_image or "/static/city.jpg",
        "content_html": post_obj.content or "",
        "tags": [tag.name for tag in post_obj.tags],
    }
    reader_id = session.get(READER_SESSION_KEY)
    current_reader = Reader.query.get(reader_id) if reader_id else None
    return render_template(
        "user/post_contents.html",
        post=post_payload,
        related_posts=related_posts,
        comments=comments_payload,
        current_reader=current_reader,
    )


@app.route("/wakadobe/posts/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    post_obj = Post.query.filter_by(id=post_id, status="published").first()
    if post_obj is None:
        abort(404)

    reader_id = session.get(READER_SESSION_KEY)
    if not reader_id:
        return redirect(url_for("reader_login"))
    current_reader = Reader.query.get(reader_id)

    comment_text = request.form.get("comment", "").strip()
    if not comment_text:
        return redirect(url_for("post_details", post_id=post_id))

    new_comment = Comment(
        content=comment_text,
        post_id=post_id,
        reader_id=current_reader.id,
        is_approved=True,
    )
    db.session.add(new_comment)
    db.session.commit()

    return redirect(url_for("post_details", post_id=post_id))


@app.route("/wakadobe/about")
def about():
    return render_template("user/about.html")


@app.route("/wakadobe/readers/sign-up", methods=["GET", "POST"])
def reader_signup():
    abort(404)  # Disable public sign-up by returning 404
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
    flash("Account created successfully! Please log in.")
    return redirect(url_for("reader_login", created=1))


@app.route("/wakadobe/readers/login", methods=["GET", "POST"])
@limiter.limit(
    "5 per 10 minutes",
    methods=["POST"],
    error_message="Too many login attempts. Please try again in 10 minutes.",
)
def reader_login():
    abort(404)  # Disable public login by returning 404
    if session.get(READER_SESSION_KEY):
        return redirect(url_for("wakadobe_index"))

    form = ReaderLoginForm()
    resetform = ReaderResetPasswordForm()
    show_created = request.args.get("created") == "1"
    show_reset_success = request.args.get("reset") == "1"

    if request.method == "GET":
        return render_template(
            "user/reader_login.html",
            form=form,
            resetform=resetform,
            form_error=None,
            show_created=show_created,
            show_reset_success=show_reset_success,
        )

    if not form.validate_on_submit():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Please fix the errors and try again."
        return render_template(
            "user/reader_login.html",
            form=form,
            resetform=resetform,
            form_error=first_error,
            show_created=False,
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
            show_reset_success=False,
        )

    session[READER_SESSION_KEY] = reader_obj.id
    return redirect(url_for("wakadobe_index"))


@app.route("/wakadobe/readers/reset-password", methods=["POST"])
def reader_reset_password():
    if session.get(READER_SESSION_KEY):
        return jsonify({"success": False, "message": "Log out before resetting the password."}), 400

    resetform = ReaderResetPasswordForm()
    if not resetform.validate_on_submit():
        first_error = next(iter(resetform.errors.values()))[0] if resetform.errors else "Please fix the errors and try again."
        return jsonify({"success": False, "message": first_error}), 400

    reader_obj = Reader.query.filter(func.lower(Reader.email) == resetform.email.data).first()
    if reader_obj is None:
        return jsonify({"success": False, "message": "No reader account exists with that email."}), 404

    reader_obj.password = generate_password_hash(resetform.new_password.data)
    db.session.commit()
    return jsonify({"success": True, "redirect": url_for("reader_login", reset=1)})


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
