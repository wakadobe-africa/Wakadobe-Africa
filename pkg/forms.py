import re
from html import unescape

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from sqlalchemy import func
from wtforms import HiddenField, PasswordField, SelectField, SelectMultipleField, StringField, TextAreaField
from wtforms.validators import AnyOf, DataRequired, EqualTo, Length, Optional, ValidationError

from pkg.blogmodel import Admin, Category, Reader, Tag


MAX_CONTENT_HTML_LENGTH = 100_000
MAX_UPLOAD_IMAGE_BYTES = 5 * 1024 * 1024


def _looks_like_email(value):
    email = (value or "").strip()
    # Accept standard email formats and local development domains.
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def _strip_html(value):
    cleaned = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(cleaned)).strip()


def _get_file_size_bytes(file_storage):
    stream = getattr(file_storage, "stream", None)
    if stream is None:
        return 0

    current_pos = stream.tell()
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(current_pos)
    return size


class CreatePostForm(FlaskForm):
    draft_id = HiddenField("Draft ID", validators=[Optional()])
    title = StringField("Post Title", validators=[DataRequired(message="Post title is required.")])
    excerpt = TextAreaField("Short Description", validators=[Optional()])
    cover_image = FileField(
        "Cover Image",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "gif", "webp"], "Invalid image file.")],
    )
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    tag_ids = SelectMultipleField("Tags", coerce=int, validators=[Optional()])
    new_tags = StringField("Add New Tags", validators=[Optional()])
    post_status = HiddenField(
        "Post Status",
        default="published",
        validators=[AnyOf(["published", "draft"], message="Invalid post status.")],
    )
    content_html = HiddenField("Post Content", validators=[DataRequired(message="Post content is required.")])

    def validate_content_html(self, field):
        if not field.data or _strip_html(field.data) == "":
            raise ValidationError("Post content is required.")
        if len(field.data) > MAX_CONTENT_HTML_LENGTH:
            raise ValidationError("Post content is too long.")

    def validate_cover_image(self, field):
        if not field.data:
            return
        if _get_file_size_bytes(field.data) > MAX_UPLOAD_IMAGE_BYTES:
            raise ValidationError("Cover image is too large. Max allowed is 5MB.")

    def validate_category_id(self, field):
        if field.data is None:
            return

        category_obj = Category.query.get(field.data)
        if category_obj is None:
            raise ValidationError("Invalid category selected.")

        self.valid_category = category_obj

    def validate_tag_ids(self, field):
        if not field.data:
            self.valid_tag_ids = []
            return

        unique_ids = sorted(set(field.data))
        found_tags = Tag.query.filter(Tag.id.in_(unique_ids)).all()
        found_ids = {tag.id for tag in found_tags}
        invalid_ids = [tag_id for tag_id in unique_ids if tag_id not in found_ids]

        if invalid_ids:
            raise ValidationError("One or more selected tags are invalid.")

        self.valid_tag_ids = unique_ids

    def validate_new_tags(self, field):
        if not field.data:
            self.normalized_new_tags = []
            return

        parsed = []
        seen = set()
        for raw_name in field.data.split(","):
            clean_name = raw_name.strip()
            if not clean_name:
                continue

            key = clean_name.lower()
            if key in seen:
                continue
            seen.add(key)
            parsed.append(clean_name)

        self.normalized_new_tags = parsed


class UpdateProfileForm(FlaskForm):
    name = StringField(
        "Admin Name",
        validators=[
            DataRequired(message="Admin name is required."),
            Length(max=100, message="Admin name cannot exceed 100 characters."),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Length(max=120, message="Email cannot exceed 120 characters."),
        ],
    )
    password = PasswordField(
        "New Password",
        validators=[
            Optional(),
            Length(min=8, max=255, message="Password must be between 8 and 255 characters."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            Optional(),
            EqualTo("password", message="Password confirmation must match the new password."),
        ],
    )

    def __init__(self, current_admin_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_admin_id = current_admin_id

    def validate_email(self, field):
        normalized_email = (field.data or "").strip().lower()
        if not normalized_email:
            raise ValidationError("Email is required.")
        if not _looks_like_email(normalized_email):
            raise ValidationError("Enter a valid email address.")

        existing = Admin.query.filter(func.lower(Admin.email) == normalized_email).first()
        if existing and existing.id != self.current_admin_id:
            raise ValidationError("Another admin already uses this email.")

        field.data = normalized_email


class CreateAdminAccountForm(FlaskForm):
    name = StringField(
        "Admin Name",
        validators=[
            DataRequired(message="Admin name is required."),
            Length(min=2, max=100, message="Admin name must be between 2 and 100 characters."),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Length(max=120, message="Email cannot exceed 120 characters."),
        ],
    )
    role = SelectField(
        "Role",
        choices=[
            ("admin", "Admin"),
            ("author", "Author"),
            ("contributor", "Contributor"),
            ("reader", "Reader"),
        ],
        validators=[DataRequired(message="Role is required.")],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, max=255, message="Password must be between 8 and 255 characters."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm the password."),
            EqualTo("password", message="Password confirmation must match the password."),
        ],
    )

    def validate_email(self, field):
        normalized_email = (field.data or "").strip().lower()
        if not normalized_email:
            raise ValidationError("Email is required.")
        if not _looks_like_email(normalized_email):
            raise ValidationError("Enter a valid email address.")

        existing = Admin.query.filter(func.lower(Admin.email) == normalized_email).first()
        if existing:
            raise ValidationError("An admin account with this email already exists.")

        field.data = normalized_email

    def validate_role(self, field):
        allowed_roles = {"admin", "author", "contributor", "reader"}
        selected = (field.data or "").strip().lower()
        if selected not in allowed_roles:
            raise ValidationError("Select a valid role.")
        field.data = selected


class AdminLoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Length(max=120, message="Email cannot exceed 120 characters."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
    )

    def validate_email(self, field):
        normalized_email = (field.data or "").strip().lower()
        if not _looks_like_email(normalized_email):
            raise ValidationError("Enter a valid email address.")
        field.data = normalized_email


class ReaderSignupForm(FlaskForm):
    name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Name is required."),
            Length(min=2, max=100, message="Name must be between 2 and 100 characters."),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Length(max=120, message="Email cannot exceed 120 characters."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, max=255, message="Password must be between 8 and 255 characters."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Password confirmation must match the password."),
        ],
    )

    def validate_email(self, field):
        normalized_email = (field.data or "").strip().lower()
        if not normalized_email:
            raise ValidationError("Email is required.")
        if not _looks_like_email(normalized_email):
            raise ValidationError("Enter a valid email address.")

        existing = Reader.query.filter(func.lower(Reader.email) == normalized_email).first()
        if existing:
            raise ValidationError("A reader account with this email already exists.")

        field.data = normalized_email


class ReaderLoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Length(max=120, message="Email cannot exceed 120 characters."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
    )

    def validate_email(self, field):
        normalized_email = (field.data or "").strip().lower()
        if not _looks_like_email(normalized_email):
            raise ValidationError("Enter a valid email address.")
        field.data = normalized_email


class ReaderResetPasswordForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Length(max=120, message="Email cannot exceed 120 characters."),
        ],
    )
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(message="New password is required."),
            Length(min=8, max=255, message="Password must be between 8 and 255 characters."),
        ],
    )
    confirm_new_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your new password."),
            EqualTo("new_password", message="Password confirmation must match the new password."),
        ],
    )

    def validate_email(self, field):
        normalized_email = (field.data or "").strip().lower()
        if not _looks_like_email(normalized_email):
            raise ValidationError("Enter a valid email address.")
        field.data = normalized_email
