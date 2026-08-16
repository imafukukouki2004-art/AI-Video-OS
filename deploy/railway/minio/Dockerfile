FROM minio/minio:RELEASE.2025-04-22T22-12-26Z

EXPOSE 9000

ENTRYPOINT ["minio"]
CMD ["server", "/data", "--address", ":9000", "--console-address", ":9001"]
