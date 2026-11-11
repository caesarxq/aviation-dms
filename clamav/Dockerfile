# Custom clamav image with fresh virus definitions baked in at build time
# Uses Alpine for ARM64 (aarch64) compatibility
FROM alpine:latest

# Install clamav and freshclam from Alpine repositories
RUN apk add --no-cache clamav clamav-libunrar

# Run freshclam at build time to download current virus definitions
# The filesystem is writable during build, so this succeeds
RUN freshclam

# Run clamd as root with security restrictions at runtime
USER root
CMD ["clamd", "--foreground", "--config-file=/etc/clamav/clamd.conf"]
