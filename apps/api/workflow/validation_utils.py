import logging
import os
import subprocess

logger = logging.getLogger(__name__)


class VisualValidator:
    """Utility for visual validation of generated video files."""

    @staticmethod
    def extract_frame(video_path: str, output_image_path: str, timestamp: str = "00:00:01") -> bool:
        """Extract a single frame from a video file using ffmpeg."""
        try:
            # Extract one frame at the specified timestamp
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                timestamp,
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-f",
                "image2",
                output_image_path,
            ]
            subprocess.run(cmd, check=True, capture_output=True, shell=False)  # noqa: S603
            return os.path.exists(output_image_path)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to extract frame: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during frame extraction: {e!s}")
            return False

    @staticmethod
    def is_not_black_or_blank(image_path: str, threshold: float = 0.01) -> tuple[bool, str]:
        """
        Check if an image is not completely black or blank.
        Uses ffmpeg's 'blackdetect' or basic statistics if possible.
        For simplicity here, we use ffprobe to get image statistics.
        """
        try:
            # Use ffprobe to get pixel statistics
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "frame=pkt_size,width,height",
                "-select_streams",
                "v",
                "-of",
                "csv=p=0",
                image_path,
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, shell=False)  # noqa: S603
            if not result.stdout.strip():
                return False, "Empty image data"

            # Check for blackness using ffmpeg's signalstats or similar if available
            # A simpler way: use ffmpeg to output pixel values and check mean
            # Here we'll use a more robust check: ffmpeg blackdetect filter
            cmd = [
                "ffmpeg",
                "-i",
                image_path,
                "-vf",
                "blackdetect=d=0.1:pix_th=0.1",
                "-f",
                "null",
                "-",
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, shell=False)  # noqa: S603
            # If blackdetect finds black, it will output it in stderr
            if "black_start" in result.stderr:
                return False, "Detected completely black frame"

            return True, "Frame appears valid"
        except Exception as e:
            logger.error(f"Error during visual validation: {e!s}")
            return False, f"Validation error: {e!s}"
