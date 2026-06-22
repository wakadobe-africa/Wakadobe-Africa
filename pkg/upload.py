import os
from werkzeug.utils import secure_filename
import logging
import cloudinary
from cloudinary.uploader import upload as cloudinary_upload
import app

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

    upload_dir = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    unique_name = f"{timestamp}_{filename}"
    file_path = os.path.join(upload_dir, unique_name)
    file_obj.save(file_path)

    return f"/static/uploads/{unique_name}"

def upload_image_to_cloudinary(file_obj, folder=None):
    if not file_obj or not getattr(file_obj, "filename", None):
        return None

    cloudinary_env_url = os.environ.get("CLOUDINARY_URL")
    if cloudinary_env_url:
        cloudinary.config(cloudinary_url=cloudinary_env_url, secure=True)
    else:
        logger.error("CLOUDINARY_URL environment variable is missing!")
        return _save_uploaded_image(file_obj)

    if folder is None:
        folder = os.environ.get("CLOUDINARY_FOLDER", "wakadobe/cover_images")

    try:
        # Reset the file reader pointer to the beginning of the file stream
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        # Get folder configuration or fallback to a default path
        folder_path = os.environ.get("CLOUDINARY_FOLDER", "wakadobe/cover_images")

        # Execute upload request
        result = cloudinary_upload(
            file_obj,
            folder=folder_path,
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        
        # Return the secure HTTPS URL to be saved in your database
        return result.get("secure_url")

    except Exception as e:
        # If the upload fails, log the exact problem and fall back to local disk
        logger.error(f"Cloudinary upload failed: {str(e)}")
        
        # Reset stream pointer again before saving locally so the file isn't empty
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        return _save_uploaded_image(file_obj)

