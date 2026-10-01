# Nightly backup job: pg_dump | age → Cloudflare R2. Build from the repo root:
#   docker build -f infra/backup/Dockerfile infra/backup
FROM mirror.gcr.io/library/alpine:3.22
RUN apk add --no-cache bash postgresql17-client age rclone coreutils \
    && adduser -D -u 10001 backup
COPY backup.sh /usr/local/bin/backup.sh
USER backup
ENTRYPOINT ["/usr/local/bin/backup.sh"]
