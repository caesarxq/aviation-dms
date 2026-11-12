# Production deployment and operational release

Local development should use the backend and Vite commands in the README. The root Compose file is production-shaped; its `https_proxy` service is an optional `local-https` profile. OCI terminates HTTPS on bastion Caddy and uses private application ports on the staging/production hosts. The Compose deployment requires explicit host, SMTP, and bootstrap-secret configuration and does not start the unused Keycloak development server.

## Prerequisites

- A production hostname with DNS A/AAAA records pointing to this host.
- Inbound TCP 80/443 and UDP 443 allowed for ACME certificate issuance and HTTPS.
- Store the bootstrap token and SMTP password in separate protected files outside the repository; never print them into shell logs, put them in command-line arguments, or commit them. The backend container runs as UID/GID `10001:10001`, and file-backed Compose secrets are bind mounts: the host files must be readable by that identity. Use a root-owned secret directory and files owned by `root:10001` with mode `0440` (or an equivalent ACL). Do not use root-only mode `0600`, which prevents the backend from reading the mounted secret. Verify access with a disposable container before startup.
- A real SMTP service/account for password-reset and notification delivery.
- A backup location and an independently tested restore procedure before importing operational records; backups must include `/app/data/dms.db`, `/app/data/kcaa-evidence/`, `/app/data/attachments/`, and `/app/data/uploads/`.
- An approved retention/legal-hold policy, system storage-quota scope/value, and scanner service before uploads are enabled. The API keeps the existing 10 MiB per-file limits; uploads now fail closed unless the approved quota settings and an internal ClamAV-compatible scanner endpoint are configured. Compose defaults those settings to empty. A read-only reconciliation CLI reports missing/unmatched file references but never deletes or repairs files; do not dispose of files without a documented DB/path cross-check and Records Custodian approval.
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
- `DMS_UPLOAD_QUOTA_SCOPE` and `DMS_UPLOAD_STORAGE_QUOTA_BYTES`: both are required before either file-upload endpoint accepts data. The only implemented scope is `system`; it counts bytes under `UPLOAD_DIR`, `KCAA_EVIDENCE_DIR`, and `AUDIT_REPORT_EVIDENCE_DIR`. Leave both unset until the Records Custodian approves the scope and limit. No numeric quota is approved by this guide.
- `DMS_CLAMD_HOST`, `DMS_CLAMD_PORT`, `DMS_CLAMD_TIMEOUT_SECONDS`, and `DMS_CLAMD_MAX_TIMEOUT_SECONDS`: an internal ClamAV-compatible `clamd` INSTREAM endpoint plus a finite scan timeout no greater than the explicitly approved maximum. Compose runs `clamd` as a service on the default network at `clamd:3310`; the backend connects to it via `DMS_CLAMD_HOST=clamd` / `DMS_CLAMD_PORT=3310`. The clamd container runs with dropped Linux capabilities, `no-new-privileges`, resource limits (1 GiB memory, 1 CPU, 64 PIDs), and no host port publishing. Virus definition updates are performed by running `freshclam` against the clamd container; the database volume (`clamd_data`) persists definitions across restarts. Missing/invalid configuration, an infected result, timeout, malformed response, or scanner outage blocks the upload. Maintain and monitor signature-database freshness outside the DMS.
- `DMS_UPLOAD_VALIDATOR_URL`: Compose pins this to the internal `upload-validator` service on the isolated `upload_validator` network. Do not override it to a public or untrusted endpoint; the backend accepts only the fixed internal hostname in production.
- `DMS_AUDIT_EVIDENCE_MAX_BYTES`: a positive, explicitly approved per-file limit for pre-retained P3 audit evidence. Compose defaults it to empty; P3 evidence reads/references fail closed until it is set. No size value is approved by this guide.
- `DMS_P3_IMPORT_BODY_MAX_BYTES`: a positive maximum for JSON provenance-import requests. Compose defaults it to empty; import requests return HTTP 503 until Backend/IT approves/configures a bounded value. A 128 KiB ASGI limit covers other P3 mutation bodies; both limits are enforced before FastAPI/Pydantic buffers and parses request bodies, with admission shared across the API's per-process request semaphore.
- `DMS_TRUSTED_FRONTEND_IP`: exact reverse-proxy peer allowed to supply `X-Forwarded-For`; Compose sets this to `172.31.254.3` to match the frontend container.
- `FLIGHT_RELEASE_ENABLED` (default `false`): leave disabled until accountable postholders sign the controlled source-to-rule mapping and required evidence is linked to exact effective sources. This controls only the flight-release API; it does not make mission planning or risk assessment operationally approved.

Compose refuses to start if required values are absent. The bootstrap token and SMTP password are mounted as Docker secrets at `/run/secrets/kfl_bootstrap_token` and `/run/secrets/smtp_pass`; neither secret is passed in the backend environment. The API does not publish port 8000 to the host. `DEV_MODE` is fixed to false, the session cookie is Secure, and CORS/auth origins are restricted to the configured HTTPS host. Caddy automatically obtains and renews certificates. Backend readiness checks the database, and Compose waits for the backend and frontend health checks before starting dependent services.

## Upload safeguards and remaining gates

- Personnel credentials and KCAA approval evidence are scanned before they are persisted; a clean result is mandatory. The quota check is serialized across local workers and counts the configured upload, KCAA-evidence, and audit-attachment roots. Quota and scanner settings are runtime gates; their Compose defaults are empty, so upload requests return HTTP 503 until the authorized settings and scanner service are supplied.
- `DMS_UPLOAD_QUOTA_SCOPE=system` is the only scope currently implemented. The code does not choose a storage limit; Records Custodian approval is required before configuration. If a different scope is approved, implement and test that scope before setting the environment.
- Personnel and KCAA evidence files retain their existing 10 MiB per-file limits and format-specific validation. A shared two-request semaphore bounds admitted request bodies per backend process, including P3 mutations before Pydantic parsing; non-import P3 mutations have a 128 KiB body cap and import creation requires explicitly configured `DMS_P3_IMPORT_BODY_MAX_BYTES`. The validator client is asynchronous and cancellation closes its connection under a seven-second total deadline, so it does not retain a background thread after request cancellation. Budget up to two API payload buffers per backend worker plus two validator-service buffers per service instance, then multiply by worker/replica count; enforce reverse-proxy request-body limits before enabling uploads. PDF/image parsing runs in a separate restricted validator container and a killable child process with a five-second timeout, bounded concurrency, CPU/file-size/file-descriptor/core limits, and Linux resource restrictions. KCAA evidence is served only when the stored size and SHA-256 still match the same bounded byte snapshot. P3 audit evidence remains pre-retained under `attachments/` and is not uploaded by its API; references are size-bounded by `DMS_AUDIT_EVIDENCE_MAX_BYTES`, malware-scanned, and structurally parsed in the validator service before use. Compose runs that service as UID/GID 10002 on an internal-only network, with no DMS data volume or Docker secrets, a read-only root filesystem, dropped Linux capabilities, `no-new-privileges`, and CPU/memory/process/file-descriptor limits. In production, the backend accepts only the fixed internal validator URL; missing/unreachable service fails closed. This Compose isolation has not been exercised in a running Docker deployment, so Backend/IT must verify the actual network and mount isolation before enabling uploads.
- Retention and legal-hold tables (`retention_rules`, `legal_holds`) are implemented and seeded. RR-023 sets 36 months (3 years) retention for general operational records; RR-025 sets lifetime retention for metadata records. Tables are **not connected to automatic file disposition** — do not automatically purge rejected, pending, or legacy files. File writes and SQLite commits are still separate operations; interruptions can leave unmatched files or rows. The report-only inventory command is:

  ```bash
  (cd backend && python -m app.upload_reconciliation \
    --db "$RESTORE_CANDIDATE/dms.db" \
    --uploads-root "$RESTORE_CANDIDATE/uploads" \
    --kcaa-root "$RESTORE_CANDIDATE/kcaa-evidence" \
    --attachments-root "$RESTORE_CANDIDATE/attachments" \
    --verify-hashes)
  ```

  It opens SQLite read-only and compares row paths/sizes with filesystem entries. `--verify-hashes` additionally reads retained file bytes and compares them with stored SHA-256 values. It never deletes, restores, or repairs anything. Run only against an explicitly selected isolated candidate. Review unmatched/missing entries with the Records Custodian; do not automate disposition until the policy and grace period are approved.

## Client IP forwarding and network plan

The Compose bridge uses the fixed subnet `172.31.254.0/24`; the frontend/Nginx container is fixed at `172.31.254.3`, and Compose sets `DMS_TRUSTED_FRONTEND_IP` to that exact address. The backend honors `X-Forwarded-For` only when the TCP peer matches this environment variable, and accepts exactly one valid IP value. If the peer differs or the header is absent/malformed, it uses the peer address. Do not assign `.3` to another service or change the address without updating the frontend address, `DMS_TRUSTED_FRONTEND_IP`, and this deployment configuration together.

Caddy's `reverse_proxy` generates a sanitized `X-Forwarded-For` value by default and ignores client-supplied forwarding values unless explicitly configured with trusted proxies. Nginx passes that Caddy-generated header to the backend. The backend port remains private; do not add `ProxyHeadersMiddleware`, broaden trusted peers, or trust `X-Real-IP`/forwarding headers from other sources.

**Before creating the Compose network on OCI, explicitly verify that `172.31.254.0/24` does not overlap any IPv4 CIDR assigned to the target VCN**, including secondary VCN CIDRs. Obtain all VCN CIDRs from OCI Console → Networking → Virtual Cloud Networks → target VCN, or inspect `oci network vcn get --vcn-id "$OCI_VCN_ID"` (`data.cidr-block` and `data.cidr-blocks`). Compare every returned CIDR with `172.31.254.0/24`; stop and choose a different Compose subnet if any overlap exists. Also check the deployment host's existing Docker networks (`docker network ls` and `docker network inspect ...`); this subnet is currently separate from the local `172.17.0.0/16`, `172.18.0.0/16`, and `172.19.0.0/16` networks, but that local check does not replace the OCI VCN check.

## Zoho Mail SMTP configuration

Zoho MX records currently advertise the `.zoho.com` data center. Zoho documents `smtppro.zoho.com` on TCP 587 with TLS/STARTTLS for paid organization accounts using a domain-based mailbox; confirm the exact outgoing server in Zoho Mail's **Server Configuration Details**, because account plan and data center take precedence. The backend uses STARTTLS and SMTP authentication, so configure `SMTP_PORT=587`, `SMTP_USER` as the complete Zoho mailbox address, and `SMTP_FROM` as that mailbox or an authorized alias. If multi-factor authentication is enabled, use an app-specific password and place it only in the protected file named by `SMTP_PASS_SECRET_FILE`.

Before enabling production password resets, send and receive a test message using the staging mailbox and confirm delivery, sender alignment, and failure behavior. Public DNS currently includes Zoho SPF (`include:zohomail.com`) but no `_dmarc.kfl.ke` record was returned during preflight; DKIM depends on the selector configured in Zoho Admin Console, so verify the exact selector there rather than assuming a default. Configure and verify SPF, DKIM, and DMARC in Zoho Admin Console and DNS; do not replace existing SPF content without accounting for every authorized sender. Zoho reference: [SMTP configuration](https://www.zoho.com/mail/help/zoho-smtp.html).

After initial administrator setup, remove/rotate the bootstrap-token file and restart the deployment. Password reset links are issued only when SMTP and `PUBLIC_APP_URL` are configured; the raw reset token is sent to the user's registered email and is never returned by the API.

## Backup and restore

### Current production-host status (read-only inspection)

The production backend uses the persistent Docker volume `kfl-aviation-dms-prod_dms_data`, mounted at `/app/data`. On the production host I found no production-specific DMS backup helper, generic DMS backup script, DMS cron entry in the root or `ubuntu` crontab, or local DMS backup artifact in the checked paths. The only matching systemd timer was `dpkg-db-backup.timer`, which backs up the OS package database, not Aviation DMS. A persistent Docker volume is not a backup. OCI-managed volume policies and off-host backup candidates were not independently inspected.

The owner reports a successful off-host restore drill; `docs/OFF-HOST-RESTORE-DRILL-REPORT.md` records that supplied evidence. I could not tie that drill to the current production volume. Production deployment remains blocked until a production-specific backup and restore path is installed and verified.

The persistent `/app/data` volume contains the SQLite database, KCAA evidence, audit attachments, and personnel uploads. Back up the complete directory as one set; do not copy only `dms.db`. For a consistent filesystem-level backup, pause backend writes:

Audit-report evidence is stored under `/app/data/attachments/` by default; the backend image does not package controlled audit PDFs. Provision each evidence file from an authorized, verified source before setting its `evidence_file` record or enabling its download link. Before P3 evidence is referenced or served, the API enforces the explicitly configured `DMS_AUDIT_EVIDENCE_MAX_BYTES`, scans the bounded snapshot, validates PDF structure in the killable child worker, and verifies/records SHA-256 as applicable. Missing size, quota, or scanner configuration fails closed. The P2 personnel-verification and P3 provenance-verification routes currently validate retained evidence while holding SQLite write transactions; refactor them to validate before acquiring write locks and recheck the candidate state/digest under a short transaction before operational use. Normal in-app report creation rejects audit dates earlier than the current UTC date; historical source reports must use the provenance-import workflow, and responsible postholders must confirm this UTC cutoff before operational use. Existing report rows with a null digest fail closed with HTTP 409 until controlled, documented revalidation is completed; do not silently calculate a replacement digest for legacy evidence. A digest detects later byte changes but does not establish source authenticity, approval, or immutable custody. Maintain an independently controlled provenance record and do not replace files in place.

The historical audit seeder is not a deployment or recovery command. It requires a disposable private scratch database and explicit development/import flags; it also verifies the pinned source-PDF digest and curated-payload digest. `AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED=true` and `AUDIT_IMPORT_SOURCE_RECONCILED=true` are operator attestations: set them only after independently confirming the approved source checksum and comparing every finding number and content field against that source. No audit import is authorized by these code gates alone.

On upgrade, existing personnel-upload rows with a null `file_sha256` fail closed for download and verification. Inventory and re-upload or complete an authorized, documented revalidation before relying on those legacy files; do not establish a new checksum silently for an unverified file.

```bash
cd /opt/kfl-aviation-dms-prod
backup_dir="/var/backups/kfl-dms/$(date -u +%Y%m%dT%H%M%SZ)"
sudo install -d -m 700 "$backup_dir"
compose=(sudo docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml)
"${compose[@]}" stop backend
container_id="$("${compose[@]}" ps -aq backend)"
sudo docker cp "${container_id}:/app/data/." "$backup_dir/"
"${compose[@]}" start backend
```

If the copy fails, run `"${compose[@]}" start backend` immediately. Encrypt and transfer the backup to access-controlled off-host storage. Before relying on a backup, restore the complete directory to an isolated staging volume, verify `PRAGMA integrity_check`, confirm the KCAA evidence and upload files are present, and exercise representative reads. Record the restore result and timestamp.

### Isolated backup candidate validation

The repository provides a local validator for a **stopped, isolated backup copy or restored candidate**. It does not connect to OCI/Object Storage, copy data, start the application, run migrations, or modify the candidate. Never run it against the live `/app/data` volume. It refuses the repository's active `backend/data` directory and requires an explicit isolated-candidate confirmation.

Create a SHA-256 manifest on the captured backup copy **before off-host transfer**:

```bash
(cd backend && python -m app.backup_validation create-manifest \
  --data-root "$BACKUP_COPY" --confirm-isolated-candidate)
```

After restoring that backup into a new, isolated candidate directory, verify it read-only:

```bash
(cd backend && python -m app.backup_validation verify \
  --data-root "$RESTORE_CANDIDATE" --confirm-isolated-candidate)
```

The verifier checks the manifest against every file, runs SQLite quick/integrity/foreign-key checks, requires all tables declared by the current application schema plus critical columns for identity, document, audit, and evidence tables, inventories referenced files, and verifies stored file hashes. A pre-migration or truncated database is blocked; the validator does not run migrations. Exit `0` means these data-integrity checks passed; exit `2` means a blocker was found. The manifest is a transfer-integrity aid, not a digital signature or proof of source authenticity. Generating a manifest only after downloading an unmanifested backup does not prove that the remote copy matches the source. The result does not establish RPO/RTO, off-host custody, service recovery, or operational/regulatory readiness.

The generic acceptance criteria above should be evidenced for the production source and target before claiming production recovery readiness. The owner-reported drill is not independently verified as a restore of this production volume. Keep staging unchanged unless separately authorized.

## Staging and deployment checks

1. Use a separate staging host, database, SMTP sandbox and bootstrap token. Do not run E2E tests against operational data.
2. Use the CI-built, never-reused `DMS_RELEASE_TAG`; validate Compose and the exact environment port mappings, then use the explicitly authorized workflow dispatch. OCI deployment pulls the CI images with `--no-build`; do not start the optional `https_proxy` profile on OCI.
3. Confirm HTTPS redirect/certificate, security headers, successful login/profile/logout, CSRF rejection, failed-login throttling, reset-link delivery, and 401/403 behavior for every API prefix, including `/api/p3`.
4. Run the complete backend and frontend suites, role-based browser checks, schema clean-install/upgrade tests and API smoke tests against staging.
5. Verify that document rendering cannot execute stored scripts, uploads cannot cross user/path/size boundaries, and failed/partial migrations prevent startup.
6. Demonstrate backup restore, database integrity checks, audit-event retention, and service restart/recovery before production cutover.

## Operational release restrictions

HTTPS and a green test suite do not constitute aviation or regulatory approval. Keep the following controls inactive or human/manual-only until the accountable postholders have signed the source-to-rule mapping and the required evidence is linked to the exact effective source version:

- KCAA approval/publishing decisions and authority submissions.
- Mission and flight release, including current ROC/OpSpec coverage, aircraft configuration/checklists, crew qualifications, insurance and validated risk acceptance. Release requires both mission and approved-plan altitudes to be present and equal. `FLIGHT_RELEASE_ENABLED` remains false until sign-off; aircraft registration/configuration/ROC changes revoke the seeded OpSpec flag, and reauthorization must follow controlled evidence review. Post-flight completion requires the mission to be `in_progress` and at least one substantive report detail; the exact required evidence-field set still needs postholder approval.
- Return-to-service and maintenance sign-off where aircraft-specific controlled sources are not linked.
- DG acceptance until the controlling checklist and approval evidence are reconciled.
- FDTL thresholds while their source and authority interpretation remain provisional.

Keep the 20-aircraft master fleet separate from the seven registrations shown on the current OpSpec; block operations without current aircraft-specific authorization evidence. The DGM issue-date/approval-letter discrepancy, missing aircraft-specific sources, and unnamed/unsigned postholder delegations remain explicit release blockers until resolved by the responsible owners.

## Rollback

Before each release, choose a new `DMS_RELEASE_TAG` and never reuse it; build once, record the backend/frontend image IDs and digests, and retain the previous tagged images. Roll back by restoring the prior tag in the ignored deployment `.env` and running `docker compose up -d --no-build`. Roll back the application image only when the schema remains backward compatible. For a migration that cannot be reversed safely, restore the verified pre-release backup and follow the controlled recovery procedure; never delete or rewrite audit history to make rollback appear clean.
