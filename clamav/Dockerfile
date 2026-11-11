# Custom clamav image with fresh virus definitions baked in at build time
FROM docker.io/clamav/clamav:latest

# Run freshclam at build time to download current virus definitions
# The filesystem is writable during build, so this succeeds
RUN freshclam --config-file=/etc/clamav/freshclam.conf

# Run clamd as root with security restrictions at runtime
USER root
CMD ["clamd", "--foreground", "--config-file=/etc/clamav/clamd.conf"]
