import unittest

from pkg import app
from pkg.token import build_signed_url


class TokenUrlTests(unittest.TestCase):
    def test_build_signed_url_percent_encodes_query_token(self):
        with app.test_request_context('/'):
            url = build_signed_url('reader_reset_password', 'abc/def+ghi')

        self.assertIn('token=abc%2Fdef%2Bghi', url)

    def test_build_signed_url_uses_current_request_host(self):
        with app.test_request_context('/', base_url='http://localhost:5001/'):
            url = build_signed_url('reader_reset_password', 'abc')

        self.assertTrue(url.startswith('http://localhost:5001/'))


if __name__ == '__main__':
    unittest.main()
