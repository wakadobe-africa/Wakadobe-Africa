import os
import re
from datetime import datetime, timedelta

from flask import current_app, render_template
from sqlalchemy import func
from werkzeug.utils import secure_filename

from pkg import app
from pkg.blogmodel import Admin, Category, Comment, Post, Subcategory, Tag, db
from pkg.forms import _strip_html
from pkg.upload import upload_image_to_cloudinary


def _format_post_date(created_at):
    if not created_at:
        return ""
    return created_at.strftime("%B %d, %Y").replace(" 0", " ")


def _get_post_category(post_obj):
    if post_obj.subcategory and post_obj.subcategory.category:
        return post_obj.subcategory.category.name
    return "General"


def _serialize_admin_user(admin_obj):
    return {
        "id": admin_obj.id,
        "name": admin_obj.name,
        "email": admin_obj.email,
        "role": (admin_obj.role or "admin").capitalize(),
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
    delete_on = comment_obj.flagged_at + timedelta(days=15) if comment_obj.flagged_at else None
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


def _upload_cover_image(file_obj):
    if not file_obj or not getattr(file_obj, "filename", None):
        return None

    cloudinary_url = upload_image_to_cloudinary(file_obj)
    if cloudinary_url:
        return cloudinary_url

    return _save_uploaded_image(file_obj)


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
        "slug": getattr(post_obj, "slug", ""),
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



