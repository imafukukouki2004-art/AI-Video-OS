import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api.video_rendering import (
    FFmpegVideoRenderer,
    VideoRenderingError,
    VideoRenderRequest,
    VideoRenderResult,
)


def _request() -> VideoRenderRequest:
    return VideoRenderRequest(
        image_data=b"png-data",
        image_content_type="image/png",
        duration_seconds=2.0,
        fps=24,
        width=1280,
        height=720,
    )


def test_video_render_models_validate_inputs_and_results() -> None:
    request = _request()
    result = VideoRenderResult(video_data=b"mp4-data")

    assert request.fps == 24
    assert result.content_type == "video/mp4"
    with pytest.raises(ValidationError, match="must be an image"):
        VideoRenderRequest(image_data=b"text", image_content_type="text/plain")
    with pytest.raises(ValidationError, match="must be even"):
        VideoRenderRequest(image_data=b"png", image_content_type="image/png", width=1279)
    with pytest.raises(ValidationError, match="video/mp4"):
        VideoRenderResult(video_data=b"video", content_type="video/webm")


def test_ffmpeg_command_uses_validated_render_settings(tmp_path: Path) -> None:
    renderer = FFmpegVideoRenderer(executable="ffmpeg-custom")
    command = renderer.build_command(_request(), tmp_path / "input.png", tmp_path / "out.mp4")

    assert command[0] == "ffmpeg-custom"
    assert ["-t", "2.0"] == command[command.index("-t") : command.index("-t") + 2]
    assert ["-r", "24"] == command[command.index("-r") : command.index("-r") + 2]
    assert "scale=1280:720" in command[command.index("-vf") + 1]
    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-movflags") + 1] == "+faststart"


@pytest.mark.asyncio
async def test_ffmpeg_renderer_returns_video_and_cleans_temporary_files(monkeypatch) -> None:
    renderer = FFmpegVideoRenderer()
    temporary_paths: list[Path] = []

    def run(command):
        input_path, output_path = Path(command[command.index("-i") + 1]), Path(command[-1])
        temporary_paths.extend([input_path, output_path])
        assert input_path.read_bytes() == b"png-data"
        output_path.write_bytes(b"rendered-mp4")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(renderer, "_run_command", run)

    result = await renderer.render(_request())

    assert result.video_data == b"rendered-mp4"
    assert result.metadata["video_codec"] == "h264"
    assert all(not path.exists() for path in temporary_paths)


@pytest.mark.asyncio
async def test_ffmpeg_renderer_wraps_failure_and_cleans_temporary_files(monkeypatch) -> None:
    renderer = FFmpegVideoRenderer()
    temporary_paths: list[Path] = []

    def fail(command):
        temporary_paths.extend([Path(command[command.index("-i") + 1]), Path(command[-1])])
        return subprocess.CompletedProcess(command, 1, "", "codec unavailable")

    monkeypatch.setattr(renderer, "_run_command", fail)

    with pytest.raises(VideoRenderingError, match="codec unavailable"):
        await renderer.render(_request())
    assert all(not path.exists() for path in temporary_paths)


@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is not installed")
async def test_ffmpeg_renderer_real_backend_when_available() -> None:
    # A minimal 1x1 PNG fixture validates the installed backend boundary.
    image = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c63606060f80f0001040100b51c0c020000000049454e44ae426082"
    )
    result = await FFmpegVideoRenderer().render(
        VideoRenderRequest(
            image_data=image,
            image_content_type="image/png",
            duration_seconds=0.1,
            fps=1,
            width=2,
            height=2,
        )
    )

    assert result.video_data[4:8] == b"ftyp"
