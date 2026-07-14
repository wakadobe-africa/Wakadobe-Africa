import io
import unittest
from unittest.mock import MagicMock, patch

from pkg.admin_routes import _get_cover_upload_feedback
from pkg.upload import _allowed_image, upload_image_to_cloudinary


class DummyFile:
    def __init__(self, filename):
        self.filename = filename
        self.stream = io.BytesIO(b"fake-image")

    def seek(self, offset, whence=0):
        self.stream.seek(offset, whence)

    def save(self, path):
        with open(path, "wb") as fh:
            fh.write(self.stream.getvalue())


class UploadHelperTests(unittest.TestCase):
    def test_allowed_image_accepts_common_images(self):
        self.assertTrue(_allowed_image("cover.png"))
        self.assertTrue(_allowed_image("cover.jpg"))
        self.assertTrue(_allowed_image("cover.webp"))
        self.assertFalse(_allowed_image("cover.exe"))

    def test_cloudinary_upload_uses_cloudinary_when_configured(self):
        uploaded = DummyFile("cover.png")
        mock_app = MagicMock()
        mock_app.config = {"CLOUDINARY_URL": "https://cloudinary.example.com/test", "DEBUG": True}

        with patch("pkg.upload.cloudinary.config") as mock_config, patch("pkg.upload.cloudinary_upload") as mock_upload, patch("pkg.upload.current_app", new=mock_app):
            mock_upload.return_value = {"secure_url": "https://cdn.example.com/cover.png"}
            result = upload_image_to_cloudinary(uploaded, folder="test-folder")

        self.assertEqual(result, "https://cdn.example.com/cover.png")
        mock_config.assert_called_once()
        mock_upload.assert_called_once()

    def test_cover_upload_feedback_reports_failure_message(self):
        self.assertEqual(
            _get_cover_upload_feedback("cover.png", "Cloudinary is not configured for production uploads."),
            "Cover image upload failed. The post will use the default cover image."
        )

    def test_cloudinary_upload_fails_fast_in_production_without_config(self):
        uploaded = DummyFile("cover.png")
        mock_app = MagicMock()
        mock_app.config = {"ENV": "production", "DEBUG": False}

        with patch.dict("os.environ", {}, clear=True), patch("pkg.upload.current_app", new=mock_app):
            with self.assertRaises(RuntimeError):
                upload_image_to_cloudinary(uploaded, folder="test-folder")


if __name__ == "__main__":
    unittest.main()
