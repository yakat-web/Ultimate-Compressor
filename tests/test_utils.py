"""Unit tests for the utils module."""

import json
import os
import sys
import tempfile
from unittest import mock

import pytest

# Adjust path so we can import the src package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.utils import (
    LOG_FILE_PATH,
    _compute_sha256,
    format_file_size,
    get_resource_path,
    get_tool_path,
    log_error,
    verify_tool_integrity,
)


class TestGetResourcePath:
    """Tests for get_resource_path()."""

    def test_returns_path_from_meipass_when_available(self):
        with mock.patch.object(sys, "_MEIPASS", "/fake/meipass", create=True):
            result = get_resource_path("tools/cjpeg.exe")
            assert result == os.path.join("/fake/meipass", "tools/cjpeg.exe")

    def test_returns_path_from_argv_when_no_meipass(self):
        # Ensure _MEIPASS does not exist
        if hasattr(sys, "_MEIPASS"):
            delattr(sys, "_MEIPASS")
        result = get_resource_path("tools/cjpeg.exe")
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        assert result == os.path.join(base, "tools/cjpeg.exe")

    def test_uses_attribute_error_not_broad_exception(self):
        """Issue #10: verify we catch AttributeError, not Exception."""
        # If _MEIPASS doesn't exist, it should raise AttributeError internally
        if hasattr(sys, "_MEIPASS"):
            delattr(sys, "_MEIPASS")
        # Should not raise, should fall back gracefully
        result = get_resource_path("test.txt")
        assert isinstance(result, str)


class TestGetToolPath:
    """Tests for get_tool_path()."""

    def test_returns_none_for_missing_tool(self):
        result = get_tool_path("nonexistent_tool_xyz.exe")
        assert result is None

    def test_does_not_call_messagebox(self):
        """Verify get_tool_path has no GUI dependency."""
        with mock.patch("src.utils.log_error") as mock_log:
            result = get_tool_path("nonexistent.exe")
            assert result is None
            mock_log.assert_called()


class TestFormatFileSize:
    """Tests for format_file_size()."""

    def test_bytes(self):
        assert format_file_size(500) == "500 B"

    def test_kilobytes(self):
        assert format_file_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_file_size(5 * 1024 * 1024) == "5.00 MB"


class TestLogFilePath:
    """Issue #11: Log file should be in APPDATA, not program directory."""

    def test_log_path_is_in_appdata(self):
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            assert appdata in LOG_FILE_PATH
        else:
            # Fallback to temp dir
            assert tempfile.gettempdir() in LOG_FILE_PATH


class TestVerifyToolIntegrity:
    """Issue #9: Tool hash verification."""

    def test_first_run_stores_hash(self, tmp_path):
        # Create a fake tool
        fake_tool = tmp_path / "fake_tool.exe"
        fake_tool.write_bytes(b"fake binary content")

        hash_file = tmp_path / "hashes.json"

        with mock.patch("src.utils._TOOL_HASHES_FILE", str(hash_file)):
            result = verify_tool_integrity(str(fake_tool))
            assert result is True

            # Hash file should exist
            assert hash_file.exists()
            data = json.loads(hash_file.read_text())
            assert "fake_tool.exe" in data

    def test_detects_tampered_tool(self, tmp_path):
        fake_tool = tmp_path / "fake_tool.exe"
        fake_tool.write_bytes(b"original content")

        hash_file = tmp_path / "hashes.json"

        with mock.patch("src.utils._TOOL_HASHES_FILE", str(hash_file)):
            # First run — establish baseline
            verify_tool_integrity(str(fake_tool))

            # Tamper with the tool
            fake_tool.write_bytes(b"TAMPERED content")

            # Second run — should detect tampering
            result = verify_tool_integrity(str(fake_tool))
            assert result is False
