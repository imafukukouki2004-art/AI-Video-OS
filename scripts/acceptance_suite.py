"""Development-environment acceptance for API, storage, queue, and worker."""

from __future__ import annotations

import time

import httpx

API_BASE_URL = "http://127.0.0.1:8000"


def require_success(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Acceptance endpoint returned an unexpected response.")
    return payload


def main() -> None:
    with httpx.Client(base_url=API_BASE_URL, timeout=10) as client:
        require_success(client.get("/health"))
        require_success(client.get("/ready"))
        asset = require_success(
            client.post(
                "/assets",
                files={"file": ("acceptance.mp4", b"mock-video", "video/mp4")},
            )
        )
        publication = require_success(
            client.post(
                "/publications",
                json={
                    "asset_id": asset["id"],
                    "provider": "mock",
                    "title": "Publishing queue acceptance",
                },
            )
        )
        queued = require_success(client.post(f"/publications/{publication['id']}/enqueue"))
        if queued.get("status") != "queued" or not queued.get("task_id"):
            raise RuntimeError("Publication was not queued with a task ID.")

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            current = require_success(client.get(f"/publications/{publication['id']}"))
            if current.get("status") == "published":
                if not current.get("external_id") or not current.get("external_url"):
                    raise RuntimeError("Published result is missing external references.")
                return
            if current.get("status") == "failed":
                raise RuntimeError("Publishing worker reported a safe terminal failure.")
            time.sleep(0.5)

    raise RuntimeError("Timed out waiting for the publishing worker.")


if __name__ == "__main__":
    main()
