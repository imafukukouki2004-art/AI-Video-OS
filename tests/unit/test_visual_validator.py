from unittest.mock import patch

from apps.api.workflow.validation_utils import VisualValidator


def test_visual_validator_extract_frame_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = None
        with patch("os.path.exists", return_value=True):
            success = VisualValidator.extract_frame("dummy.mp4", "dummy.png")
            assert success is True


def test_visual_validator_extract_frame_failure():
    with patch("subprocess.run", side_effect=Exception("FFmpeg missing")):
        success = VisualValidator.extract_frame("dummy.mp4", "dummy.png")
        assert success is False


def test_visual_validator_is_not_black_or_blank_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "100,640,480"
        mock_run.return_value.stderr = ""
        valid, reason = VisualValidator.is_not_black_or_blank("dummy.png")
        assert valid is True
        assert "valid" in reason.lower()


def test_visual_validator_is_not_black_or_blank_failure():
    with patch("subprocess.run", side_effect=Exception("FFprobe missing")):
        valid, reason = VisualValidator.is_not_black_or_blank("dummy.png")
        assert valid is False
        assert "Validation error" in reason
