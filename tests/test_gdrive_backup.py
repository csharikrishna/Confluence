"""
Unit tests for the optional Google Drive backup module (gdrive_backup.py).
No real Google credentials/API calls — is_configured() gating and
build_export() are pure/mockable; the actual upload path is exercised with
the google client libraries mocked out (import-time optional dependency).
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import gdrive_backup

try:
    import googleapiclient  # noqa: F401
    _GOOGLE_LIBS_INSTALLED = True
except ImportError:
    _GOOGLE_LIBS_INSTALLED = False


class TestIsConfigured(unittest.TestCase):
    def setUp(self):
        self._orig = (gdrive_backup.GDRIVE_ENABLED, gdrive_backup.GDRIVE_SERVICE_ACCOUNT_JSON, gdrive_backup.GDRIVE_SERVICE_ACCOUNT_FILE)

    def tearDown(self):
        gdrive_backup.GDRIVE_ENABLED, gdrive_backup.GDRIVE_SERVICE_ACCOUNT_JSON, gdrive_backup.GDRIVE_SERVICE_ACCOUNT_FILE = self._orig

    def test_disabled_by_default_is_not_configured(self):
        gdrive_backup.GDRIVE_ENABLED = False
        gdrive_backup.GDRIVE_SERVICE_ACCOUNT_JSON = '{"type": "service_account"}'
        self.assertFalse(gdrive_backup.is_configured())

    def test_enabled_without_credentials_is_not_configured(self):
        gdrive_backup.GDRIVE_ENABLED = True
        gdrive_backup.GDRIVE_SERVICE_ACCOUNT_JSON = None
        gdrive_backup.GDRIVE_SERVICE_ACCOUNT_FILE = None
        self.assertFalse(gdrive_backup.is_configured())

    def test_enabled_with_json_credentials_is_configured(self):
        gdrive_backup.GDRIVE_ENABLED = True
        gdrive_backup.GDRIVE_SERVICE_ACCOUNT_JSON = '{"type": "service_account"}'
        self.assertTrue(gdrive_backup.is_configured())

    def test_enabled_with_file_credentials_is_configured(self):
        gdrive_backup.GDRIVE_ENABLED = True
        gdrive_backup.GDRIVE_SERVICE_ACCOUNT_JSON = None
        gdrive_backup.GDRIVE_SERVICE_ACCOUNT_FILE = "/path/to/key.json"
        self.assertTrue(gdrive_backup.is_configured())


class TestBackupExportNoOp(unittest.TestCase):
    def test_backup_export_noop_when_unconfigured(self):
        with patch("gdrive_backup.is_configured", return_value=False):
            result = gdrive_backup.backup_export([{"some": "data"}])
        self.assertIsNone(result)


class TestBackupExportUpload(unittest.TestCase):
    @unittest.skipUnless(_GOOGLE_LIBS_INSTALLED, "google-api-python-client not installed (optional extra)")
    @patch("gdrive_backup.is_configured", return_value=True)
    @patch("gdrive_backup._get_drive_service")
    def test_backup_export_uploads_and_returns_file_id(self, mock_get_service, mock_configured):
        mock_service = MagicMock()
        mock_service.files.return_value.create.return_value.execute.return_value = {"id": "drive-file-123"}
        mock_get_service.return_value = mock_service

        with patch("googleapiclient.http.MediaFileUpload") as mock_media:
            mock_media.return_value = MagicMock()
            result = gdrive_backup.backup_export([{"location": "Chennai"}])
        self.assertEqual(result, "drive-file-123")

    @patch("gdrive_backup.is_configured", return_value=True)
    @patch("gdrive_backup._get_drive_service", side_effect=RuntimeError("no credentials"))
    def test_backup_export_swallows_failures_and_returns_none(self, mock_get_service, mock_configured):
        # Exercises the failure path regardless of whether the optional google
        # libraries are installed: _get_drive_service raises before MediaFileUpload
        # would ever be imported, and backup_export must swallow it either way.
        result = gdrive_backup.backup_export([{"location": "Chennai"}])
        self.assertIsNone(result)


class TestBuildExport(unittest.TestCase):
    def test_build_export_gathers_history_per_location(self):
        mock_storage = MagicMock()
        mock_storage.get_history.return_value = [{"timestamp": "2026-09-03T10:00:00Z", "data": {}}]

        locations = [{"name": "Chennai Coast", "lat": 13.08, "lon": 80.27}]
        export = gdrive_backup.build_export(locations, mock_storage, days=7)

        self.assertEqual(len(export), 1)
        self.assertEqual(export[0]["location"]["name"], "Chennai Coast")
        self.assertEqual(len(export[0]["history"]), 1)
        mock_storage.get_history.assert_called_once()

    def test_build_export_tolerates_per_location_failures(self):
        mock_storage = MagicMock()
        mock_storage.get_history.side_effect = Exception("db unreachable")

        locations = [{"name": "Chennai Coast", "lat": 13.08, "lon": 80.27}]
        export = gdrive_backup.build_export(locations, mock_storage, days=7)

        self.assertEqual(export[0]["history"], [])


if __name__ == "__main__":
    unittest.main()
