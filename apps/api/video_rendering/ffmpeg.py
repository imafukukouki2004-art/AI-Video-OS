"""FFmpeg implementation of the video renderer boundary."""

import asyncio
import subprocess  # nosec B404 - command is fixed and uses validated numeric values
import tempfile
from collections.abc import Sequence
from pathlib import Path

from apps.api.video_rendering.base import VideoRenderingError
from apps.api.video_rendering.models import VideoRenderRequest, VideoRenderResult


class FFmpegVideoRenderer:
    """Render one image into an H.264 MP4 using an isolated temporary directory."""

    def __init__(self, executable: str = "ffmpeg") -> None:
        self.executable = executable

    def build_command(
        self, request: VideoRenderRequest, input_path: Path, output_path: Path
    ) -> list[str]:
        """Build the deterministic FFmpeg command without executing it."""
        return [
            self.executable,
            "-y",
            "-loop",
            "1",
            "-i",
            str(input_path),
            "-t",
            str(request.duration_seconds),
            "-r",
            str(request.fps),
            "-vf",
            (
                f"scale={request.width}:{request.height}:force_original_aspect_ratio=decrease,"
                f"pad={request.width}:{request.height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
            ),
            "-c:v",
            "libx264",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    async def render(self, request: VideoRenderRequest) -> VideoRenderResult:
        """Render and return MP4 bytes; temporary files are always cleaned up."""
        suffix = self._image_suffix(request.image_content_type)
        with tempfile.TemporaryDirectory(prefix="ai-video-os-render-") as directory:
            temp_dir = Path(directory)
            input_path = temp_dir / f"input{suffix}"
            output_path = temp_dir / "output.mp4"
            input_path.write_bytes(request.image_data)
            command = self.build_command(request, input_path, output_path)

            try:
                completed = await asyncio.to_thread(self._run_command, command)
            except (OSError, subprocess.SubprocessError) as error:
                raise VideoRenderingError("FFmpeg execution failed") from error

            if completed.returncode != 0:
                message = completed.stderr.strip() or "unknown FFmpeg error"
                raise VideoRenderingError(f"FFmpeg rendering failed: {message}")
            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise VideoRenderingError("FFmpeg produced an empty video")

            return VideoRenderResult(
                video_data=output_path.read_bytes(),
                metadata={
                    "renderer": "ffmpeg",
                    "video_codec": "h264",
                    "duration_seconds": request.duration_seconds,
                    "fps": request.fps,
                    "width": request.width,
                    "height": request.height,
                },
            )

    @staticmethod
    def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - fixed executable and validated arguments
            command,
            check=False,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _image_suffix(content_type: str) -> str:
        suffixes = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
        try:
            return suffixes[content_type]
        except KeyError as error:
            raise VideoRenderingError(f"Unsupported input image type: {content_type}") from error
