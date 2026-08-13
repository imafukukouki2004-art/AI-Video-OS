# Publishing Domain & Provider Foundation

TICKET-036 establishes a boundary between generated Assets and future external distribution
platforms. It does not add social credentials, platform SDKs, automatic posting, a queue, or
scheduling.

## Architecture boundary

```text
WorkflowRuntime -> final Video Asset
                         |
                         v
Create Publication -> PublishingService -> PublishingProvider
                              |                    |
                              v                    v
                   PublicationRepository   Mock provider only
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

`PublishingProviderResolver` currently resolves only `mock`. The Mock provider is deterministic
and does not make a network request. Future YouTube, TikTok, and Instagram adapters can implement
the same interface without changing WorkflowRuntime or the Publication lifecycle.

## API foundation

```text
POST /publications
GET  /publications/{publication_id}
GET  /assets/{asset_id}/publications
POST /publications/{publication_id}/publish
```

Creation validates the existing Asset and provider. Execution is synchronous for this foundation.
Queueing, scheduling, automatic Workflow-to-Publishing integration, and actual social API posting
remain out of scope.

## Security rules

- Publication schemas contain no credential or token fields.
- API responses never expose provider configuration.
- Raw provider exception messages are not persisted or returned.
- Mock fixtures contain no API keys.
- Publishing remains separate from generation and storage adapters.
