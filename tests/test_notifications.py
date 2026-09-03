"""
Unit tests for the optional alert webhook (notifications.py). Verifies it's
fully inert when unconfigured, posts a combined Slack+Discord-compatible
payload when configured, never raises on failure, and only fires on newly
logged (non-deduped) alerts.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import storage
import notifications


class TestNotifications(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._tmp_path = path
        self._orig_db_path = storage.DB_PATH
        storage.DB_PATH = path
        storage.init_db()
        self._orig_webhook = notifications.WEBHOOK_URL

    def tearDown(self):
        storage.DB_PATH = self._orig_db_path
        notifications.WEBHOOK_URL = self._orig_webhook
        try:
            os.remove(self._tmp_path)
        except OSError:
            pass

    def _alert(self, alert_id="pm25_unhealthy"):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"id": alert_id, "severity": "high", "message": "Test alert message", "triggered_at": now, "value": 60.0}

    @patch("notifications.requests.post")
    def test_notify_alert_noop_when_unconfigured(self, mock_post):
        notifications.WEBHOOK_URL = None
        notifications.notify_alert(self._alert(), {"name": "Chennai Coast"})
        mock_post.assert_not_called()

    @patch("notifications.requests.post")
    def test_notify_alert_posts_combined_payload_when_configured(self, mock_post):
        notifications.WEBHOOK_URL = "https://hooks.example.com/webhook"
        notifications.notify_alert(self._alert(), {"name": "Chennai Coast"})

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertIn("text", payload)
        self.assertIn("content", payload)
        self.assertEqual(payload["text"], payload["content"])
        self.assertIn("Chennai Coast", payload["text"])
        self.assertIn("HIGH", payload["text"])

    @patch("notifications.requests.post", side_effect=Exception("network down"))
    def test_notify_alert_swallows_delivery_failures(self, mock_post):
        notifications.WEBHOOK_URL = "https://hooks.example.com/webhook"
        # Must not raise.
        notifications.notify_alert(self._alert(), {"name": "Chennai Coast"})

    @patch("notifications.notify_alert")
    def test_log_and_notify_fires_on_first_occurrence(self, mock_notify):
        result = notifications.log_and_notify(13.08, 80.27, self._alert(), {"name": "Chennai Coast"})
        self.assertTrue(result)
        mock_notify.assert_called_once()

    @patch("notifications.notify_alert")
    def test_log_and_notify_skips_on_cooldown_duplicate(self, mock_notify):
        alert = self._alert()
        notifications.log_and_notify(13.08, 80.27, alert, {"name": "Chennai Coast"})
        mock_notify.reset_mock()

        result = notifications.log_and_notify(13.08, 80.27, alert, {"name": "Chennai Coast"})
        self.assertFalse(result)
        mock_notify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
