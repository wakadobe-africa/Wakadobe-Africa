import os

import cloudinary
from cloudinary.uploader import upload as cloudinary_upload


def upload_image_to_cloudinary(file_obj, folder=None):
    if not file_obj or not getattr(file_obj, "filename", None):
        return None

    cloudinary.config(secure=True)

    if folder is None:
        folder = os.environ.get("CLOUDINARY_FOLDER", "wakadobe/cover_images")

    try:
        result = cloudinary_upload(
            file_obj,
            folder=folder,
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        return result.get("secure_url") or result.get("url")
    except Exception:
        return None
