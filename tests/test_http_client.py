"""
Unit tests for ResilientHttpClient verifying retry mechanics, error mapping,
timeouts, and header parsing.
"""

from datetime import datetime, timedelta, timezone
import email.utils
import unittest
from unittest.mock import MagicMock
import requests

from dict_core.exceptions import (
    InvalidResponseError,
    NetworkError,
    RateLimitError,
    TimeoutError,
    WordNotFoundError,
)
from dict_core.utils.http_client import ResilientHttpClient


class TestResilientHttpClient(unittest.TestCase):
    """Tests the HTTP client's resilience, backoff, and exception mappings."""

    def setUp(self) -> None:
        self.mock_session = MagicMock(spec=requests.Session())
        self.mock_session.headers = {}
        self.sleep_calls = []

        def mock_sleeper(duration: float) -> None:
            self.sleep_calls.append(duration)

        self.client = ResilientHttpClient(
            timeout=2.0,
            max_retries=3,
            backoff_factor=0.5,
            sleeper=mock_sleeper,
            session=self.mock_session,
        )

    def test_get_json_success(self) -> None:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = '{"word": "test", "definitions": ["a procedure"]}'
        mock_response.json.return_value = {"word": "test", "definitions": ["a procedure"]}
        self.mock_session.get.return_value = mock_response

        data = self.client.get_json("https://api.example.com/lookup")
        self.assertEqual(data["word"], "test")
        self.assertEqual(len(self.sleep_calls), 0)

    def test_get_404_maps_to_word_not_found(self) -> None:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.text = '{"title": "No Definitions Found"}'
        self.mock_session.get.return_value = mock_response

        with self.assertRaises(WordNotFoundError) as ctx:
            self.client.get("https://api.example.com/words/xyz", target_word="xyz")

        self.assertEqual(ctx.exception.word, "xyz")
        self.assertEqual(len(self.sleep_calls), 0)

    def test_retry_on_server_error_and_recovery(self) -> None:
        resp_503 = MagicMock(spec=requests.Response)
        resp_503.status_code = 503
        resp_503.text = "Service Unavailable"
        resp_503.headers = {}

        resp_200 = MagicMock(spec=requests.Response)
        resp_200.status_code = 200
        resp_200.text = '{"success": true}'
        resp_200.json.return_value = {"success": True}

        self.mock_session.get.side_effect = [resp_503, resp_503, resp_200]

        data = self.client.get_json("https://api.example.com/data")
        self.assertEqual(data, {"success": True})
        self.assertEqual(self.sleep_calls, [0.5, 1.0])

    def test_server_error_exhausts_retries_raises_network_error(self) -> None:
        resp_500 = MagicMock(spec=requests.Response)
        resp_500.status_code = 500
        resp_500.text = "Internal Server Error"
        resp_500.headers = {}
        self.mock_session.get.return_value = resp_500

        with self.assertRaises(NetworkError) as ctx:
            self.client.get("https://api.example.com/fail")

        self.assertIn("Server error HTTP 500", str(ctx.exception))
        self.assertEqual(len(self.sleep_calls), 3)

    def test_timeout_retry_and_eventual_timeout_error(self) -> None:
        self.mock_session.get.side_effect = requests.exceptions.Timeout("Read timeout")

        with self.assertRaises(TimeoutError):
            self.client.get("https://api.example.com/slow")

        self.assertEqual(len(self.sleep_calls), 3)

    def test_connection_error_raises_network_error(self) -> None:
        self.mock_session.get.side_effect = requests.exceptions.ConnectionError("DNS failure")

        with self.assertRaises(NetworkError):
            self.client.get("https://api.example.com/unreachable")

        self.assertEqual(len(self.sleep_calls), 3)

    def test_rate_limit_with_retry_after_header(self) -> None:
        resp_429 = MagicMock(spec=requests.Response)
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "3"}
        resp_429.text = "Rate Limited"

        resp_200 = MagicMock(spec=requests.Response)
        resp_200.status_code = 200
        resp_200.text = '{"word": "retry_ok"}'
        resp_200.json.return_value = {"word": "retry_ok"}

        self.mock_session.get.side_effect = [resp_429, resp_200]

        data = self.client.get_json("https://api.example.com/rate")
        self.assertEqual(data["word"], "retry_ok")
        self.assertEqual(self.sleep_calls, [3.0])

    def test_rate_limit_with_rfc2822_date_retry_after(self) -> None:
        future_date = datetime.now(timezone.utc) + timedelta(seconds=5)
        date_str = email.utils.format_datetime(future_date)

        resp_429 = MagicMock(spec=requests.Response)
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": date_str}
        resp_429.text = "Rate Limited"

        resp_200 = MagicMock(spec=requests.Response)
        resp_200.status_code = 200
        resp_200.text = '{"word": "ok"}'
        resp_200.json.return_value = {"word": "ok"}

        self.mock_session.get.side_effect = [resp_429, resp_200]

        data = self.client.get_json("https://api.example.com/date_rate")
        self.assertEqual(data["word"], "ok")
        self.assertEqual(len(self.sleep_calls), 1)
        self.assertAlmostEqual(self.sleep_calls[0], 5.0, delta=1.5)

    def test_rate_limit_exhausted_raises_rate_limit_error(self) -> None:
        resp_429 = MagicMock(spec=requests.Response)
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "2"}
        resp_429.text = "Too Many Requests"
        self.mock_session.get.return_value = resp_429

        with self.assertRaises(RateLimitError):
            self.client.get("https://api.example.com/rate")

        self.assertEqual(len(self.sleep_calls), 3)

    def test_client_error_400_raises_network_error(self) -> None:
        resp_400 = MagicMock(spec=requests.Response)
        resp_400.status_code = 400
        resp_400.text = "Bad Request"
        resp_400.headers = {}
        self.mock_session.get.return_value = resp_400

        with self.assertRaises(NetworkError) as ctx:
            self.client.get("https://api.example.com/bad")
        self.assertIn("Client error HTTP 400", str(ctx.exception))

    def test_malformed_json_raises_invalid_response_error(self) -> None:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = "<html><body>502 Bad Gateway Nginx</body></html>"
        mock_response.json.side_effect = ValueError("Invalid JSON")
        self.mock_session.get.return_value = mock_response

        with self.assertRaises(InvalidResponseError):
            self.client.get_json("https://api.example.com/corrupt")

    def test_empty_response_body_raises_invalid_response_error(self) -> None:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = "   "
        self.mock_session.get.return_value = mock_response

        with self.assertRaises(InvalidResponseError):
            self.client.get_json("https://api.example.com/empty")

    def test_context_manager(self) -> None:
        with ResilientHttpClient(session=self.mock_session) as client:
            self.assertIsNotNone(client)
        self.mock_session.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
