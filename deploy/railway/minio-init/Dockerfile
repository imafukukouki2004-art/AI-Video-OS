FROM minio/mc:RELEASE.2025-04-16T18-13-26Z

ENTRYPOINT ["/bin/sh", "-c"]
CMD ["until mc alias set local \"$STORAGE_ENDPOINT_URL\" \"$STORAGE_ACCESS_KEY\" \"$STORAGE_SECRET_KEY\"; do sleep 2; done; mc mb --ignore-existing \"local/$STORAGE_BUCKET\""]
