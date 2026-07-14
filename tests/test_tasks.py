import os
import unittest
from unittest.mock import MagicMock, patch

from pkg.tasks import (
    enqueue_admin_otp_email,
    enqueue_verification_email,
    get_queue,
    send_verification_email,
)


class TaskQueueTests(unittest.TestCase):
    def test_get_queue_uses_redis_url_without_forcing_ssl_false(self):
        queue = MagicMock()
        with patch.dict(os.environ, {"REDIS_URL": "rediss://example.com"}, clear=False):
            with patch("pkg.tasks.Redis.from_url", return_value="redis-conn") as mock_from_url, patch(
                "pkg.tasks.Queue", return_value=queue
            ) as mock_queue:
                get_queue()

        mock_from_url.assert_called_once_with("rediss://example.com")
        mock_queue.assert_called_once_with(connection="redis-conn")

    def test_enqueue_verification_email_uses_queue_when_available(self):
        queue = MagicMock()
        with patch("pkg.tasks.get_queue", return_value=queue):
            enqueue_verification_email("reader@example.com", "https://example.com/verify")

        self.assertEqual(queue.enqueue.call_count, 1)

    def test_enqueue_admin_otp_email_uses_queue_when_available(self):
        queue = MagicMock()
        with patch("pkg.tasks.get_queue", return_value=queue):
            enqueue_admin_otp_email("admin@example.com", "123456")

        self.assertEqual(queue.enqueue.call_count, 1)

    def test_send_verification_email_uses_app_context(self):
        with patch("pkg.tasks._send_message_now") as mock_send_message:
            send_verification_email("reader@example.com", "https://example.com/verify")

        mock_send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
