# Publishing Domain & Provider Foundation

TICKET-036 established the Publishing boundary. TICKET-037 adds YouTube as the first real platform
adapter while keeping platform SDK and OAuth material inside that boundary. Automatic posting, a
queue, scheduling, and a user-facing OAuth system remain excluded.

TICKET-038 adds an operator-level OAuth connection foundation. The project does not yet contain a
User, Workspace, Tenant, or Account identity model, so exactly one most-recent CONNECTED YouTube
connection is treated as the operator connection. Multi-user account selection is intentionally
deferred rather than approximated inside Publication or WorkflowRuntime.

## Architecture boundary

```text
WorkflowRuntime -> final Video Asset
                         |
                         v
Create Publication -> PublishingService -> PublishingProvider
                              |                    |
                              v                    v
                   PublicationRepository   Mock / YouTube provider
```

`WorkflowRuntime` remains responsible for content generation through the final Asset and
WorkflowArtifact. Publishing starts only from an existing Asset ID and neither duplicates the
Asset nor imports generation behavior.

## Publication record

A Publication stores the Asset reference, provider name, lifecycle status, title, optional
description, external ID and URL, provider metadata, safe error information, and timestamps.
Credentials are deliberately absent. Provider configuration and tokens belong to future provider
configuration, never to Publication data.

Only non-empty stored video Assets are publishable in this foundation. The service checks that the
Asset exists, has a `video/*` content type, has a non-empty object key, and has a positive size.

## Lifecycle

```text
pending -> publishing -> published
                   \-> failed
```

Only a pending Publication can be executed. The service persists `publishing` before invoking the
provider. A successful normalized response persists the external ID, URL, metadata, and
`published_at`. Provider exceptions or invalid responses persist `failed` plus a stable error code
and safe message; raw provider exception text is not persisted or exposed.

Retry and reset transitions are intentionally undefined in TICKET-036.

## Provider contract

`PublishingProvider.publish` receives an existing Asset plus publication text and returns a
`PublishingResponse` containing:

- `external_id`
- `external_url`
- provider-specific non-secret `metadata`

`PublishingProviderResolver` resolves `mock` and `youtube`. The Mock provider remains deterministic
and network-free. `YouTubePublishingProvider` uses the same interface, downloads the existing
Asset through ObjectStorage, constructs the YouTube upload within the adapter, and normalizes the
SDK result to the provider-neutral response. SDK response objects never reach Service or API code.

The YouTube provider now asks `YouTubeCredentialResolver` for the active connected credential at
publication time. A connected credential takes priority. The environment refresh token remains a
temporary development/backward-compatible fallback when no connected credential exists.

## OAuth connection boundary

```text
OAuth API
  -> YouTubeConnectionService
  -> Connection / OAuth State / Credential repositories
  -> CredentialCipher

PublishingService
  -> YouTubePublishingProvider
  -> YouTubeCredentialResolver
  -> decrypted refresh token (in-memory only)
  -> Google client
```

`WorkflowRuntime`, Worker, Asset, WorkflowArtifact, and Publication do not own OAuth credentials.
Connection metadata, credential ciphertext, and OAuth state are separate database records.

The connection lifecycle is deliberately small:

```text
PENDING -> CONNECTED
PENDING -> FAILED
CONNECTED -> DISCONNECTED
```

The authorization endpoint generates a random state and persists only its SHA-256 digest. State
expires after ten minutes by default and is consumed atomically once under a row lock. Callback
processing rejects missing, mismatched, expired, and reused state before exchanging a code.

Refresh tokens are encrypted using Fernet authenticated encryption from `cryptography`. The key is
provided only by `YOUTUBE_CREDENTIAL_ENCRYPTION_KEY`; missing or invalid configuration fails closed.
The database stores ciphertext, never the plaintext token or encryption key. Access tokens are not
persisted. Uvicorn's query-string access logger is disabled because callbacks contain authorization
codes; the existing middleware continues to emit path-only structured access events.

Disconnect deletes local credential ciphertext and marks the connection DISCONNECTED. Google-side
revocation is deferred because Google documents that revocation can remove every scope granted to
the project, not just the local connection record.

## YouTube upload and credentials

YouTube video upload requires OAuth 2.0 user authorization; service accounts cannot own or act as
a YouTube channel. This foundation accepts a pre-authorized client ID, client secret, and refresh
token from environment settings:

```text
YOUTUBE_CLIENT_ID
YOUTUBE_CLIENT_SECRET
YOUTUBE_REFRESH_TOKEN
YOUTUBE_PRIVACY_STATUS=private
```

The refresh token must carry the minimum
`https://www.googleapis.com/auth/youtube.upload` scope. These values are Pydantic `SecretStr`
settings and are used only to create the Provider's Google credentials. They are never stored in a
Publication, returned by an API, or logged. Account connection, consent UI, multi-account storage,
and refresh-token lifecycle management remain separate future work.

The Provider maps Publication `title` and `description` to the YouTube video snippet and uses
`private` as the default `privacyStatus`. It disables subscriber notification for this explicit
foundation upload. A successful `videos.insert` response becomes:

```text
external_id  = YouTube Video ID
external_url = https://www.youtube.com/watch?v={Video ID}
```

The existing ObjectStorage adapter supplies the video bytes. The Provider uses a seekable in-memory
stream for the official Google media upload and closes it in a `finally` block. It neither calls
S3/MinIO directly, duplicates the Asset, nor creates a persistent local file.

Configuration, Asset retrieval, invalid media, upload, and malformed response failures have stable
YouTube-specific codes. The PublishingService persists only each code and its safe message before
returning the existing safe API error contract.

## API foundation

```text
POST /publications
GET  /publications/{publication_id}
GET  /assets/{asset_id}/publications
POST /publications/{publication_id}/publish
```

Creation validates the existing Asset and provider. Execution is synchronous for this foundation.
Queueing, scheduling, automatic Workflow-to-Publishing integration, and actual social API posting
outside the explicit YouTube Provider call remain out of scope.

## Manual private upload verification

Manual verification is opt-in and is not part of pytest or GitHub Actions:

1. Enable YouTube Data API v3 in a Google Cloud project and authorize the target channel with the
   `youtube.upload` scope.
2. Supply the OAuth client ID, client secret, and refresh token through the local environment or a
   secret manager. Never commit a credentials JSON or `.env` file.
3. Leave `YOUTUBE_PRIVACY_STATUS=private` unless the CEO explicitly approves another visibility.
4. Start the normal API and create a Publication with `provider: youtube` for an existing Video
   Asset.
5. Call `POST /publications/{publication_id}/publish`, then verify the returned canonical URL in
   YouTube Studio before changing visibility.

No manual real-API upload was performed for TICKET-037 implementation. All required tests replace
the SDK client and prohibit external YouTube communication.

No manual real OAuth exchange was performed for TICKET-038. See the dedicated setup guide for the
explicit opt-in procedure.

## Security rules

- Publication schemas contain no credential or token fields.
- API responses never expose provider configuration.
- Raw provider exception messages are not persisted or returned.
- Mock fixtures contain no API keys.
- Publishing remains separate from generation and storage adapters.
- YouTube OAuth values are SecretStr environment configuration only.
- Upload visibility defaults to private and subscriber notification is disabled.
- Refresh tokens are authenticated-encrypted at rest and are never returned through connection APIs.
- OAuth state is expiring, single-use, and stored only as a digest.
