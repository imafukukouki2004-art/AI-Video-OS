# YouTube OAuth Setup

TICKET-038 implements the Google OAuth 2.0 web-server Authorization Code Flow for one operator-level
YouTube connection. Normal tests and GitHub Actions do not contact Google.

## Google Cloud configuration

1. Enable YouTube Data API v3 in the approved Google Cloud project.
2. Configure the OAuth consent screen and create a **Web application** OAuth client.
3. Add the exact redirect URI used by the API. For local development the default is:

   `http://localhost:8000/publishing/connections/youtube/callback`

   Production web clients must use an approved HTTPS redirect URI. Google rejects a redirect URI
   that does not exactly match the configured value.
4. Supply the client ID and secret through the deployment secret mechanism:

   ```text
   YOUTUBE_CLIENT_ID
   YOUTUBE_CLIENT_SECRET
   YOUTUBE_OAUTH_REDIRECT_URI
   ```

The application requests only `https://www.googleapis.com/auth/youtube.upload`, with offline access
and explicit consent so a refresh token can be issued. Service accounts are not supported for this
operator channel flow.

## Encryption key

Generate a Fernet key outside the repository:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the output in the deployment secret manager as `YOUTUBE_CREDENTIAL_ENCRYPTION_KEY`. Never put
the value in source, `.env.example`, migrations, fixtures, tickets, PRs, screenshots, or logs. Losing
or rotating the key without re-encrypting credentials makes existing connections unreadable and
publishing fails closed.

## Connection flow

1. `POST /publishing/connections/youtube/authorize`
2. Open the returned `authorization_url` in a browser and approve the requested upload scope.
3. Google redirects to the configured callback. The API validates and consumes state, exchanges the
   authorization code, encrypts the refresh token, and returns non-secret connection metadata.
4. `GET /publishing/connections/{connection_id}` checks lifecycle status.
5. Existing Publication APIs with `provider: youtube` prefer this connected credential.

Only the most recently connected operator-level YouTube connection is active. A new successful
connection disconnects older active records and deletes their local credential ciphertext.

## Disconnect

`DELETE /publishing/connections/{connection_id}` deletes the local encrypted credential and marks
the connection DISCONNECTED. It does not call Google's revocation endpoint. An operator may revoke
the application in Google Account settings when full remote revocation is required.

## Manual private smoke test

Manual testing is optional and requires explicit CEO-approved credentials and a test/private channel.
Keep `YOUTUBE_PRIVACY_STATUS=private`, start authorization from the API, complete consent, publish an
existing Video Asset, and verify the returned canonical URL in YouTube Studio. Do not copy callback
codes or tokens into logs or issue comments.

## Known limitations

- No User/Tenant model or account-selection UI exists; this is an operator-level connection.
- Google-side revocation and token rotation/re-encryption tooling are deferred.
- The environment refresh-token fallback remains for development compatibility.
- Channel metadata is not requested because the minimal upload scope is intentionally preserved.
