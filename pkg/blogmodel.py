# flask sqlachemy models for a blogging platform with users, posts, categories, subcategories, comments, and tags.
import re

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
db = SQLAlchemy()

class Admin(db.Model):
    __tablename__ = "admin"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=True)
    role = db.Column(db.String(20), default="admin")  # admin, author, contributor

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    posts = db.relationship("Post", foreign_keys='Post.admin_id', backref="author", lazy="select")
    reviewed_posts = db.relationship("Post", foreign_keys='Post.reviewed_by', lazy="select")

post_tags = db.Table(
    "post_tags",
    db.Column("post_id", db.Integer, db.ForeignKey("post.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)

class Post(db.Model):
    __tablename__ = "post"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    excerpt = db.Column(db.Text, nullable=True)
    cover_image = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)
    slug = db.Column(db.String(250), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Foreign Keys
    admin_id = db.Column(db.Integer, db.ForeignKey("admin.id"), nullable=False, index=True)
    subcategory_id = db.Column(db.Integer, db.ForeignKey("subcategory.id"), nullable=True, index=True)

    reviewed_by = db.Column(db.Integer, db.ForeignKey("admin.id"), nullable=True)

    # Publishing system
    status = db.Column(db.String(20), default="draft", index=True)
    is_oped = db.Column(db.Boolean, default=False)

    # Relationships
    tags = db.relationship(
        "Tag",
        secondary=post_tags,
        backref=db.backref("posts", lazy="dynamic")
    )

    comments = db.relationship("Comment", backref="post", lazy="select")

    @staticmethod
    def slugify(value):
        normalized = re.sub(r"[^\w\s-]", "", (value or "").strip().lower())
        normalized = re.sub(r"[-\s]+", "-", normalized)
        return normalized[:250] or "post"


@db.event.listens_for(Post, "before_insert")
def _set_post_slug(mapper, connection, target):
    if target.title and not target.slug:
        target.slug = Post.slugify(target.title)


@db.event.listens_for(Post, "before_update")
def _update_post_slug(mapper, connection, target):
    if target.title:
        slug = Post.slugify(target.title)
        if target.slug != slug:
            target.slug = slug

class Category(db.Model):
    __tablename__ = "category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    subcategories = db.relationship("Subcategory", backref="category", lazy="select")

class Subcategory(db.Model):
    __tablename__ = "subcategory"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False, index=True)

    posts = db.relationship("Post", backref="subcategory", lazy="select")



class Tag(db.Model):
    __tablename__ = "tag"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)



class Reader(db.Model):
    __tablename__ = "reader"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=True)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    comments = db.relationship("Comment", backref="reader", lazy="select")

class Comment(db.Model):
    __tablename__ = "comment"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey('comment.id', ondelete='CASCADE'), # deleting a parent deletes replies
        nullable=True    # null = top-level comment, not a reply
    )
    replies = db.relationship(
        'Comment',
        backref=db.backref('parent', remote_side='Comment.id'),
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    flagged_at = db.Column(db.DateTime, nullable=True, index=True)
    reader_id = db.Column(db.Integer, db.ForeignKey("reader.id"), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False, index=True)

