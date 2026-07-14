import unittest
from unittest.mock import patch

from pkg import app
from pkg.token import build_signed_url, send_admin_otp_email, send_email


class TokenUrlTests(unittest.TestCase):
    def test_build_signed_url_percent_encodes_query_token(self):
        with app.test_request_context('/'):
            url = build_signed_url('reader_reset_password', 'abc/def+ghi')

        self.assertIn('token=abc%2Fdef%2Bghi', url)

    def test_build_signed_url_uses_current_request_host(self):
        with app.test_request_context('/', base_url='http://localhost:5001/'):
            url = build_signed_url('reader_reset_password', 'abc')

        self.assertTrue(url.startswith('http://localhost:5001/'))

    def test_send_email_uses_enqueue_function(self):
        with patch('pkg.token.enqueue_verification_email') as mock_enqueue:
            send_email('reader@example.com', 'https://example.com/verify')

        mock_enqueue.assert_called_once_with('reader@example.com', 'https://example.com/verify')

    def test_send_admin_otp_email_uses_enqueue_function(self):
        with patch('pkg.token.enqueue_admin_otp_email') as mock_enqueue:
            send_admin_otp_email('admin@example.com', '123456')

        mock_enqueue.assert_called_once_with('admin@example.com', '123456')


if __name__ == '__main__':
    unittest.main()
