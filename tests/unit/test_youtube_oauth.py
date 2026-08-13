"""Unit tests for Google OAuth request and token exchange boundaries."""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from pydantic import SecretStr

from apps.api.publishing.oauth import (
    GoogleYouTubeOAuthClient,
    OAuthConfigurationError,
    OAuthRefreshTokenMissingError,
    OAuthTokenExchangeError,
)
from apps.api.publishing.youtube import YOUTUBE_TOKEN_URI, YOUTUBE_UPLOAD_SCOPE


def oauth_client() -> GoogleYouTubeOAuthClient:
    return GoogleYouTubeOAuthClient(
        SecretStr("client-fixture"),
        SecretStr("secret-fixture"),
        "https://app.example.test/publishing/connections/youtube/callback",
    )


def test_authorization_url_requests_offline_upload_access_with_state() -> None:
    url = oauth_client().authorization_url("state-fixture")
    query = parse_qs(urlparse(url).query)

    assert query["scope"] == [YOUTUBE_UPLOAD_SCOPE]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["response_type"] == ["code"]
    assert query["state"] == ["state-fixture"]
    assert query["redirect_uri"] == [
        "https://app.example.test/publishing/connections/youtube/callback"
    ]
    assert "client_secret" not in query


def test_missing_configuration_fails_closed() -> None:
    client = GoogleYouTubeOAuthClient(SecretStr(""), SecretStr(""), "")

    with pytest.raises(OAuthConfigurationError):
        client.authorization_url("state")


@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_returns_refresh_token_and_validates_scope() -> None:
    route = respx.post(YOUTUBE_TOKEN_URI).mock(
        return_value=httpx.Response(
            200,
            json={"refresh_token": "refresh-fixture", "scope": YOUTUBE_UPLOAD_SCOPE},
        )
    )

    result = await oauth_client().exchange_code(SecretStr("code-fixture"))

    assert result.refresh_token.get_secret_value() == "refresh-fixture"
    assert result.scopes == (YOUTUBE_UPLOAD_SCOPE,)
    request_body = route.calls[0].request.content.decode()
    assert "grant_type=authorization_code" in request_body
    assert "code=code-fixture" in request_body


@pytest.mark.asyncio
@respx.mock
async def test_exchange_failures_are_normalized_without_secret_details() -> None:
    respx.post(YOUTUBE_TOKEN_URI).mock(
        return_value=httpx.Response(400, json={"error": "code-fixture-sensitive"})
    )

    with pytest.raises(OAuthTokenExchangeError) as raised:
        await oauth_client().exchange_code(SecretStr("code-fixture-sensitive"))

    assert "sensitive" not in str(raised.value)


@pytest.mark.asyncio
@respx.mock
async def test_exchange_requires_refresh_token_and_upload_scope() -> None:
    route = respx.post(YOUTUBE_TOKEN_URI)
    route.mock(return_value=httpx.Response(200, json={"scope": YOUTUBE_UPLOAD_SCOPE}))
    with pytest.raises(OAuthRefreshTokenMissingError):
        await oauth_client().exchange_code(SecretStr("code"))

    route.mock(
        return_value=httpx.Response(200, json={"refresh_token": "fixture", "scope": "other"})
    )
    with pytest.raises(OAuthTokenExchangeError):
        await oauth_client().exchange_code(SecretStr("code"))
