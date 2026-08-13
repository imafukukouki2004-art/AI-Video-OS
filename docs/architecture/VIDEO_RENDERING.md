# Video Rendering Foundation

TICKET-034 adds a non-AI rendering operation to the existing Workflow Runtime. Rendering remains
separate from `AIProvider` and uses the same API and Celery worker runtime path.

## Architecture

```text
WorkflowRuntime
    -> VideoRenderer
    -> FFmpegVideoRenderer
    -> ObjectStorage
    -> Asset
    -> WorkflowArtifact
    -> WorkflowContext
```

`VideoRenderRequest` and `VideoRenderResult` are immutable, validated boundary models. Runtime
resolves and downloads the input Asset, while the renderer owns FFmpeg command construction and
temporary files. Runtime never imports or invokes the FFmpeg process directly.

## Workflow step

The initial operation renders one stored image as a fixed-duration H.264 MP4:

```json
{
  "name": "RenderVideo",
  "step_type": "render",
  "order": 3,
  "config": {
    "operation": "video_render",
    "input_asset": "{{GenerateImage.asset}}",
    "duration": 3,
    "fps": 30,
    "width": 1280,
    "height": 720
  }
}
```

`input_asset` is required and must resolve to an existing image Asset ID. Defaults are 3 seconds,
30 fps, and 1280×720. Duration is limited to 60 seconds, fps to 60, and dimensions must be even.
The first backend accepts PNG, JPEG, and WebP and produces `video/mp4` with H.264/yuv420p and
fast-start metadata for common browser and SNS playback.

## Registration and publication order

1. Resolve the input Asset reference.
2. Load Asset metadata and download image bytes from Object Storage.
3. Validate `VideoRenderRequest`.
4. Render and validate `VideoRenderResult`.
5. Upload MP4 bytes to the existing Object Storage.
6. Register a `video/mp4` Asset.
7. Register a `video` WorkflowArtifact linked to the execution, step, and Asset.
8. Generate the stored video reference and publish Context values.
9. Persist Job and Step completion through the existing runtime flow.

The Asset model remains storage metadata only. The WorkflowArtifact is the existing entity that
associates the rendered video with its WorkflowExecution and WorkflowStep.

## Context specification

After every persistence operation succeeds, both the step name and ID expose:

- `{{RenderVideo.video}}` — presigned MP4 download URL
- `{{RenderVideo.asset}}` — rendered video Asset ID
- `{{RenderVideo.artifact}}` — video WorkflowArtifact ID
- `{{RenderVideo.output}}` — structured runtime result

No values are published for a failed render. Existing output, image, asset, and artifact syntax is
unchanged; no new expression language is introduced.

## Temporary files and failures

`FFmpegVideoRenderer` creates a unique operating-system temporary directory per call. Input and
output paths live only within that directory, and Python removes the directory after success or
exception. Generated files never use repository or shared fixed paths.

Backend failures become `VideoRenderingError` and flow through the existing runtime failure path:
the active Job and Execution fail, WorkflowExecutionError and History are recorded, count and
duration Metrics are emitted, the next step is not selected, and video Context remains unpublished.

The current repositories do not provide a cross-storage/database transaction. If upload succeeds
but a later Asset or WorkflowArtifact write fails, the completed write may remain for operational
reconciliation; it is never exposed through Context or reported as a completed step. This preserves
the existing persistence boundaries without introducing a TICKET-034-specific transaction system.

## Development environment

FFmpeg is installed explicitly in the API and Celery worker container images. For host execution,
install an FFmpeg build that provides `libx264` and ensure `ffmpeg` is on `PATH`:

```bash
ffmpeg -version
ffmpeg -encoders | grep libx264
```

Deterministic tests mock the renderer/process boundary. A real backend test also runs automatically
where FFmpeg is available and otherwise reports a skip.

## Boundaries

This foundation intentionally excludes audio, subtitles, transitions, timelines, multi-track or
parallel/GPU rendering, video templates, text-to-video providers, social publishing, scheduling,
UI, analytics, retries, and provider failover.
