"""Public legal pages required by external service integrations."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["legal"])

_PAGE_STYLES = """
    :root { color-scheme: light; font-family: system-ui, -apple-system, sans-serif; }
    body { margin: 0; background: #f7f8fa; color: #18202a; line-height: 1.6; }
    main { max-width: 760px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
    article { background: #fff; border-radius: 12px; padding: clamp(1.25rem, 4vw, 2.5rem); }
    h1 { margin-top: 0; line-height: 1.2; }
    h2 { margin-top: 2rem; font-size: 1.2rem; }
    a { color: #155eef; overflow-wrap: anywhere; }
"""


def _page(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | AI Video OS</title>
  <style>{_PAGE_STYLES}</style>
</head>
<body>
  <main><article><h1>{title}</h1>{content}</article></main>
</body>
</html>"""


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy() -> HTMLResponse:
    """Describe how AI Video OS handles OAuth authorization data."""

    content = """
    <p>AI Video OS is an AI-assisted video generation and publishing workflow service.</p>
    <h2>Google OAuth usage</h2>
    <p>Google OAuth is used to connect YouTube accounts that users authorize. Access is used
    only for publishing actions initiated and authorized by the user.</p>
    <h2>Data handling</h2>
    <p>OAuth authorization data is handled securely. Credentials are encrypted when stored and
    are not exposed through public pages.</p>
    <h2>User control</h2>
    <p>Users may disconnect their YouTube authorization from the service.</p>
    <h2>Contact</h2>
    <p>Questions may be sent to
    <a href="mailto:hello.koki.design@gmail.com">hello.koki.design@gmail.com</a>.</p>
    """
    return HTMLResponse(_page("Privacy Policy", content))


@router.get("/terms", response_class=HTMLResponse)
async def terms_of_service() -> HTMLResponse:
    """Describe the terms governing use of AI Video OS."""

    content = """
    <p>AI Video OS provides AI-assisted video generation and publishing workflow tools.</p>
    <h2>User responsibility</h2>
    <p>Users are responsible for the content they create, the instructions they provide, and
    compliance with applicable laws and platform policies.</p>
    <h2>Authorized account usage</h2>
    <p>Users may connect and publish only through accounts they own or are authorized to use.</p>
    <h2>Prohibited misuse</h2>
    <p>Users must not use the service for unlawful activity, unauthorized access, deceptive
    content, abuse, or infringement of third-party rights.</p>
    <h2>Availability</h2>
    <p>The service may change, be interrupted, or become unavailable, and uninterrupted operation
    is not guaranteed.</p>
    <h2>Contact</h2>
    <p>Questions may be sent to
    <a href="mailto:hello.koki.design@gmail.com">hello.koki.design@gmail.com</a>.</p>
    """
    return HTMLResponse(_page("Terms of Service", content))
