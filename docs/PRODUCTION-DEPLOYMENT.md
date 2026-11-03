# Production deployment and operational release

The default Compose deployment is for local development only. Production Compose now requires explicit host, SMTP, and bootstrap-secret configuration; it terminates HTTPS with Caddy, keeps the API private to the Compose network, and does not start the unused Keycloak development server.

## Prerequisites

- A production hostname with DNS A/AAAA records pointing to this host.
- Inbound TCP 80/443 and UDP 443 allowed for ACME certificate issuance and HTTPS.
- A protected one-time bootstrap-token file on the host; do not place its contents in Git or command-line arguments. Restrict it to the deployment operator (for example, mode `0600`).
- A real SMTP service/account for password-reset and notification delivery.
- A backup location and an independently tested restore procedure before importing operational records; backups must include `/app/data/dms.db`, `/app/data/kcaa-evidence/`, and `/app/data/uploads/`.
- Approved, current source manuals, authority evidence, and named/effective delegations for each workflow that will be activated.

## Required environment

Set these in the deployment environment or an ignored root `.env` file. Use real values locally; the values below are names only.

- `DMS_RELEASE_TAG`: unique, immutable local build identifier (for example, a release version or timestamp); keep prior tags until rollback is no longer required.
- `DMS_HOSTNAME`: public HTTPS DNS name.
- `ACME_EMAIL`: certificate renewal contact address.
- `KFL_BOOTSTRAP_TOKEN_FILE`: absolute path to the protected one-time bootstrap token file.
- `SMTP_HOST`, `SMTP_USER`, `SMTP_FROM`: production mail configuration. `SMTP_PORT` defaults to 587.
- `SMTP_PASS_SECRET_FILE`: absolute host-side path to a protected file containing only the SMTP password; Compose mounts it at `/run/secrets/smtp_pass`. Do not place the production password in `.env`, shell history, or `docker-compose.yml`.
- `RATE_LIMIT_REQUESTS_PER_MIN` (default `100`), `RATE_LIMIT_WINDOW_SECONDS` (default `60`), and `RATE_LIMIT_MAX_CLIENTS` (default `10000`): per-client-IP API throttling controls; the limiter covers `/api/p0` through `/api/p3`, not `/health`. Tune only after staging load checks, especially where multiple users share a public NAT. The limiter is process-local; use a shared store or edge enforcement before adding backend workers or replicas.
- `SESSION_TTL_SECONDS` (default `28800`, sliding) and `SESSION_ABSOLUTE_MAX_SECONDS` (default `86400`): session lifetime controls. The absolute maximum prevents sliding activity from extending a session indefinitely.
- `DMS_TRUSTED_FRONTEND_IP`: exact reverse-proxy peer allowed to supply `X-Forwarded-For`; Compose sets this to `172.31.254.3` to match the frontend container.

Compose refuses to start if required values are absent. The bootstrap token and SMTP password are mounted as Docker secrets at `/run/secrets/kfl_bootstrap_token` and `/run/secrets/smtp_pass`; neither secret is passed in the backend environment. The API does not publish port 8000 to the host. `DEV_MODE` is fixed to false, the session cookie is Secure, and CORS/auth origins are restricted to the configured HTTPS host. Caddy automatically obtains and renews certificates. Backend readiness checks the database, and Compose waits for the backend and frontend health checks before starting dependent services.

## Client IP forwarding and network plan

The Compose bridge uses the fixed subnet `172.31.254.0/24`; the frontend/Nginx container is fixed at `172.31.254.3`, and Compose sets `DMS_TRUSTED_FRONTEND_IP` to that exact address. The backend honors `X-Forwarded-For` only when the TCP peer matches this environment variable, and accepts exactly one valid IP value. If the peer differs or the header is absent/malformed, it uses the peer address. Do not assign `.3` to another service or change the address without updating the frontend address, `DMS_TRUSTED_FRONTEND_IP`, and this deployment configuration together.

Caddy's `reverse_proxy` generates a sanitized `X-Forwarded-For` value by default and ignores client-supplied forwarding values unless explicitly configured with trusted proxies. Nginx passes that Caddy-generated header to the backend. The backend port remains private; do not add `ProxyHeadersMiddleware`, broaden trusted peers, or trust `X-Real-IP`/forwarding headers from other sources.

**Before creating the Compose network on OCI, explicitly verify that `172.31.254.0/24` does not overlap any IPv4 CIDR assigned to the target VCN**, including secondary VCN CIDRs. Obtain all VCN CIDRs from OCI Console → Networking → Virtual Cloud Networks → target VCN, or inspect `oci network vcn get --vcn-id "$OCI_VCN_ID"` (`data.cidr-block` and `data.cidr-blocks`). Compare every returned CIDR with `172.31.254.0/24`; stop and choose a different Compose subnet if any overlap exists. Also check the deployment host's existing Docker networks (`docker network ls` and `docker network inspect ...`); this subnet is currently separate from the local `172.17.0.0/16`, `172.18.0.0/16`, and `172.19.0.0/16` networks, but that local check does not replace the OCI VCN check.

## Zoho Mail SMTP configuration

Zoho MX records currently advertise the `.zoho.com` data center. Zoho documents `smtppro.zoho.com` on TCP 587 with TLS/STARTTLS for paid organization accounts using a domain-based mailbox; confirm the exact outgoing server in Zoho Mail's **Server Configuration Details**, because account plan and data center take precedence. The backend uses STARTTLS and SMTP authentication, so configure `SMTP_PORT=587`, `SMTP_USER` as the complete Zoho mailbox address, and `SMTP_FROM` as that mailbox or an authorized alias. If multi-factor authentication is enabled, use an app-specific password and place it only in the protected file named by `SMTP_PASS_SECRET_FILE`.

Before enabling production password resets, send and receive a test message using the staging mailbox and confirm delivery, sender alignment, and failure behavior. Public DNS currently includes Zoho SPF (`include:zohomail.com`) but no `_dmarc.kfl.ke` record was returned during preflight; DKIM depends on the selector configured in Zoho Admin Console, so verify the exact selector there rather than assuming a default. Configure and verify SPF, DKIM, and DMARC in Zoho Admin Console and DNS; do not replace existing SPF content without accounting for every authorized sender. Zoho reference: [SMTP configuration](https://www.zoho.com/mail/help/zoho-smtp.html).

After initial administrator setup, remove/rotate the bootstrap-token file and restart the deployment. Password reset links are issued only when SMTP and `PUBLIC_APP_URL` are configured; the raw reset token is sent to the user's registered email and is never returned by the API.

## Backup and restore

The persistent `/app/data` volume contains the SQLite database, KCAA evidence, and personnel uploads. Back up the complete directory as one set; do not copy only `dms.db`. For a consistent filesystem-level backup, pause backend writes:

```bash
cd /opt/aviation-dms
backup_dir="/var/backups/kfl-dms/$(date -u +%Y%m%dT%H%M%SZ)"
sudo install -d -m 700 "$backup_dir"
sudo docker compose stop backend
container_id="$(sudo docker compose ps -aq backend)"
sudo docker cp "${container_id}:/app/data/." "$backup_dir/"
sudo docker compose start backend
```

If the copy fails, start the backend immediately with `sudo docker compose start backend`. Encrypt and transfer the backup to access-controlled off-host storage. Before relying on a backup, restore the complete directory to an isolated staging volume, verify `PRAGMA integrity_check`, confirm the KCAA evidence and upload files are present, and exercise representative reads. Record the restore result and timestamp.

## Staging and deployment checks

1. Use a separate staging host, database, SMTP sandbox and bootstrap token. Do not run E2E tests against operational data.
2. Set a new, never-reused `DMS_RELEASE_TAG`; run `docker compose config --quiet`, `docker compose build backend frontend https_proxy`, then `docker compose up -d --no-build` so the running services use that built tag.
3. Confirm HTTPS redirect/certificate, security headers, successful login/profile/logout, CSRF rejection, failed-login throttling, reset-link delivery, and 401/403 behavior for every API prefix, including `/api/p3`.
4. Run the complete backend and frontend suites, role-based browser checks, schema clean-install/upgrade tests and API smoke tests against staging.
5. Verify that document rendering cannot execute stored scripts, uploads cannot cross user/path/size boundaries, and failed/partial migrations prevent startup.
6. Demonstrate backup restore, database integrity checks, audit-event retention, and service restart/recovery before production cutover.

## Operational release restrictions

HTTPS and a green test suite do not constitute aviation or regulatory approval. Keep the following controls inactive or human/manual-only until the accountable postholders have signed the source-to-rule mapping and the required evidence is linked to the exact effective source version:

- KCAA approval/publishing decisions and authority submissions.
- Mission and flight release, including current ROC/OpSpec coverage, aircraft configuration/checklists, crew qualifications, insurance and validated risk acceptance.
- Return-to-service and maintenance sign-off where aircraft-specific controlled sources are not linked.
- DG acceptance until the controlling checklist and approval evidence are reconciled.
- FDTL thresholds while their source and authority interpretation remain provisional.

Keep the 20-aircraft master fleet separate from the seven registrations shown on the current OpSpec; block operations without current aircraft-specific authorization evidence. The DGM issue-date/approval-letter discrepancy, missing aircraft-specific sources, and unnamed/unsigned postholder delegations remain explicit release blockers until resolved by the responsible owners.

## Rollback

Before each release, choose a new `DMS_RELEASE_TAG` and never reuse it; build once, record the backend/frontend image IDs and digests, and retain the previous tagged images. Roll back by restoring the prior tag in the ignored deployment `.env` and running `docker compose up -d --no-build`. Roll back the application image only when the schema remains backward compatible. For a migration that cannot be reversed safely, restore the verified pre-release backup and follow the controlled recovery procedure; never delete or rewrite audit history to make rollback appear clean.
