"""Google OAuth 2.0 web-server adapter for YouTube publishing."""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from pydantic import SecretStr

from apps.api.publishing.youtube import YOUTUBE_TOKEN_URI, YOUTUBE_UPLOAD_SCOPE

GOOGLE_AUTHORIZATION_URI = "https://accounts.google.com/o/oauth2/v2/auth"


class OAuthConfigurationError(Exception):
    """Required OAuth client configuration is unavailable."""


class OAuthTokenExchangeError(Exception):
    """Authorization code exchange failed without exposing provider details."""


class OAuthRefreshTokenMissingError(Exception):
    """Google did not issue the offline refresh token required by publishing."""


@dataclass(frozen=True, slots=True)
class OAuthTokenResult:
    refresh_token: SecretStr
    scopes: tuple[str, ...]


class GoogleYouTubeOAuthClient:
    """Build authorization requests and exchange authorization codes."""

    def __init__(
        self,
        client_id: SecretStr,
        client_secret: SecretStr,
        redirect_uri: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http_client = http_client

    def ensure_configured(self) -> None:
        if not all(
            (
                self._client_id.get_secret_value(),
                self._client_secret.get_secret_value(),
                self._redirect_uri,
            )
        ):
            raise OAuthConfigurationError

    def authorization_url(self, state: str) -> str:
        self.ensure_configured()
        query = urlencode(
            {
                "client_id": self._client_id.get_secret_value(),
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "scope": YOUTUBE_UPLOAD_SCOPE,
                "state": state,
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
            }
        )
        return f"{GOOGLE_AUTHORIZATION_URI}?{query}"

    async def exchange_code(self, code: SecretStr) -> OAuthTokenResult:
        self.ensure_configured()
        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.post(
                YOUTUBE_TOKEN_URI,
                data={
                    "client_id": self._client_id.get_secret_value(),
                    "client_secret": self._client_secret.get_secret_value(),
                    "code": code.get_secret_value(),
                    "grant_type": "authorization_code",
                    "redirect_uri": self._redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise OAuthTokenExchangeError from error
        finally:
            if owns_client:
                await client.aclose()

        refresh_token = payload.get("refresh_token") if isinstance(payload, dict) else None
        if not isinstance(refresh_token, str) or not refresh_token:
            raise OAuthRefreshTokenMissingError
        scope_value = payload.get("scope", YOUTUBE_UPLOAD_SCOPE)
        scopes = tuple(str(scope_value).split())
        if YOUTUBE_UPLOAD_SCOPE not in scopes:
            raise OAuthTokenExchangeError
        return OAuthTokenResult(refresh_token=SecretStr(refresh_token), scopes=scopes)
