import os
from datetime import datetime 
from werkzeug.utils import secure_filename
from flask import current_app
import logging
import cloudinary
from cloudinary.uploader import upload as cloudinary_upload

logger = logging.getLogger(__name__)

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

    upload_dir = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    unique_name = f"{timestamp}_{filename}"
    file_path = os.path.join(upload_dir, unique_name)
    file_obj.save(file_path)

    return f"/static/uploads/{unique_name}"

def upload_image_to_cloudinary(file_obj, folder=None):
    if not file_obj or not getattr(file_obj, "filename", None):
        return None

    app_config = getattr(current_app, "config", {})
    cloudinary_url = (
        app_config.get("CLOUDINARY_URL")
        or app_config.get("cloudinary_url")
        or os.environ.get("CLOUDINARY_URL")
    )

    env_name = str(app_config.get("ENV") or os.environ.get("ENV") or "").strip().lower()
    is_production = env_name in {"production", "prod", "live"} or app_config.get("DEBUG") is False

    if not cloudinary_url:
        if is_production:
            logger.error("Cloudinary upload requested in production but CLOUDINARY_URL is not configured.")
            raise RuntimeError("Cloudinary is not configured for production uploads.")
        logger.warning("Cloudinary URL is missing; falling back to local disk for development uploads.")
        return _save_uploaded_image(file_obj)

    cloudinary.config(cloudinary_url=cloudinary_url, secure=True)

    if folder is None:
        folder = app_config.get("CLOUDINARY_FOLDER") or os.environ.get("CLOUDINARY_FOLDER", "wakadobe/cover_images")

    try:
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        result = cloudinary_upload(
            file_obj,
            folder=folder,
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        return result.get("secure_url")

    except Exception:
        logger.exception("Cloudinary upload failed")
        if is_production:
            raise
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        return _save_uploaded_image(file_obj)

