"""Unit tests for the ImageProcessor class."""

import os
import re
import shutil
import sys
import tempfile
from unittest import mock

import pytest
from PIL import Image

# Adjust path so we can import the src package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.processor import ImageProcessor


@pytest.fixture
def processor():
    """Create a fresh ImageProcessor for each test."""
    return ImageProcessor()


@pytest.fixture
def sample_jpeg(tmp_path):
    """Create a small RGB JPEG image for testing."""
    path = tmp_path / "sample.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(str(path), format="JPEG", quality=95)
    return str(path)


@pytest.fixture
def sample_png(tmp_path):
    """Create a small RGBA PNG image for testing."""
    path = tmp_path / "sample.png"
    img = Image.new("RGBA", (100, 100), color=(0, 255, 0, 255))
    img.save(str(path), format="PNG")
    return str(path)


@pytest.fixture
def cmyk_jpeg(tmp_path):
    """Create a CMYK image to test normalization."""
    path = tmp_path / "cmyk.jpg"
    img = Image.new("CMYK", (100, 100), color=(0, 100, 200, 50))
    img.save(str(path))
    return str(path)


@pytest.fixture
def palette_png(tmp_path):
    """Create a palette-mode PNG."""
    path = tmp_path / "palette.png"
    img = Image.new("P", (100, 100))
    img.save(str(path), format="PNG")
    return str(path)


class TestImageProcessorBasics:
    """Basic processor functionality."""

    def test_init_with_callback(self):
        calls = []
        proc = ImageProcessor(status_callback=calls.append)
        proc._update_status("test")
        assert calls == ["test"]

    def test_init_without_callback(self):
        proc = ImageProcessor()
        # Should not raise
        proc._update_status("test")


class TestTransparencyCheck:
    """Tests for is_png_fully_opaque()."""

    def test_opaque_png(self, processor, tmp_path):
        path = tmp_path / "opaque.png"
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        img.save(str(path))
        assert processor.is_png_fully_opaque(str(path)) is True

    def test_transparent_png(self, processor, tmp_path):
        path = tmp_path / "transparent.png"
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 128))
        img.save(str(path))
        assert processor.is_png_fully_opaque(str(path)) is False

    def test_rgb_png_is_opaque(self, processor, tmp_path):
        path = tmp_path / "rgb.png"
        img = Image.new("RGB", (10, 10), "blue")
        img.save(str(path))
        assert processor.is_png_fully_opaque(str(path)) is True


class TestNormalization:
    """Tests for _normalize_image() — Issue #15."""

    def test_cmyk_to_rgb(self, processor, cmyk_jpeg):
        normalized, temp = processor._normalize_image(cmyk_jpeg, "jpeg")
        assert temp is not None  # normalization happened
        with Image.open(normalized) as img:
            assert img.mode == "RGB"
        # Cleanup
        if temp and os.path.exists(temp):
            os.remove(temp)

    def test_rgba_to_rgb_for_jpeg(self, processor, tmp_path):
        path = tmp_path / "rgba.png"
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        img.save(str(path))
        normalized, temp = processor._normalize_image(str(path), "jpeg")
        assert temp is not None
        with Image.open(normalized) as img:
            assert img.mode == "RGB"
        if temp and os.path.exists(temp):
            os.remove(temp)

    def test_palette_to_rgb_for_jpeg(self, processor, palette_png):
        normalized, temp = processor._normalize_image(palette_png, "jpeg")
        assert temp is not None
        with Image.open(normalized) as img:
            assert img.mode == "RGB"
        if temp and os.path.exists(temp):
            os.remove(temp)

    def test_no_normalization_for_rgb_jpeg(self, processor, sample_jpeg):
        normalized, temp = processor._normalize_image(sample_jpeg, "jpeg")
        assert temp is None  # no normalization needed
        assert normalized == sample_jpeg


class TestSafeCopy:
    """Tests for _safe_copy_for_processing()."""

    def test_ascii_filename_no_copy(self, processor, sample_jpeg):
        path, temp = processor._safe_copy_for_processing(sample_jpeg)
        assert path == sample_jpeg
        assert temp is None

    def test_unicode_filename_copies(self, processor, tmp_path):
        unicode_path = tmp_path / "تصویر.jpg"
        img = Image.new("RGB", (10, 10), "red")
        img.save(str(unicode_path))
        path, temp = processor._safe_copy_for_processing(str(unicode_path))
        assert path != str(unicode_path)
        assert temp is not None
        assert os.path.exists(path)
        # Cleanup
        if temp and os.path.exists(temp):
            os.remove(temp)


class TestFormatConversion:
    """Tests for _convert_image()."""

    def test_png_to_jpeg(self, processor, sample_png):
        result = processor._convert_image(sample_png, "jpeg")
        assert os.path.exists(result)
        with Image.open(result) as img:
            assert img.format == "JPEG"
        os.remove(result)


class TestProcessFile:
    """Integration tests for process_file()."""

    def test_unsupported_format(self, processor, sample_jpeg):
        options = {
            "mode": "quality",
            "quality": 75,
            "resize_enabled": False,
            "output_dir": tempfile.gettempdir(),
            "suffix": "-test",
            "format": "Keep Original",
            "overwrite": False,
            "max_png": False,
            "auto_convert_png": False,
        }
        # Rename to an unsupported extension
        unsupported = sample_jpeg.replace(".jpg", ".xyz")
        shutil.copy(sample_jpeg, unsupported)

        # Modify the ext in the path to trigger unsupported
        success, msg = processor.process_file(unsupported, {
            **options, "format": "Keep Original"
        })
        # xyz is unsupported
        assert success is False

    def test_overwrite_with_format_change_fails(self, processor, sample_jpeg):
        options = {
            "mode": "quality",
            "quality": 75,
            "resize_enabled": False,
            "output_dir": tempfile.gettempdir(),
            "suffix": "-test",
            "format": "PNG",
            "overwrite": True,
            "max_png": False,
            "auto_convert_png": False,
        }
        success, msg = processor.process_file(sample_jpeg, options)
        assert success is False
        assert "overwrite" in msg.lower() or "Cannot" in msg


class TestSuffixValidation:
    """Issue #21: Suffix validation."""

    def test_valid_suffixes(self):
        from src.gui import _validate_suffix
        assert _validate_suffix("-tiny") is True
        assert _validate_suffix("_compressed") is True
        assert _validate_suffix("v2") is True
        assert _validate_suffix("") is True

    def test_invalid_suffixes(self):
        from src.gui import _validate_suffix
        assert _validate_suffix("فارسی") is False
        assert _validate_suffix("hello world") is False
        assert _validate_suffix("file@name") is False


class TestQualityClamping:
    """Issue #22: Quality range validation."""

    def test_clamp_quality(self):
        from src.gui import _clamp_quality
        assert _clamp_quality(0) == 1
        assert _clamp_quality(-5) == 1
        assert _clamp_quality(50) == 50
        assert _clamp_quality(100) == 100
        assert _clamp_quality(150) == 100
