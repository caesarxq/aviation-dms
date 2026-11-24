# Pilot Onboarding Procedure — Technical

## Purpose

Step-by-step procedure for standing up the pilot environment, creating the first `independent_auditor` account, and validating end-to-end upload flow. For system administrator and backend/IT use during the restricted onboarding pilot.

## Prerequisites

- All items in `ONBOARDING-READINESS-CHECKLIST.md` verified
- `docker-compose.yml` and environment variables configured
- Approved `DMS_RELEASE_TAG`, `DMS_HOSTNAME`, `SMTP_*`, `ACME_EMAIL`, `KFL_BOOTSTRAP_TOKEN_FILE`, `SMTP_PASS_SECRET_FILE`

## Step 1: Validate Configuration

```bash
cd /Users/mohamedalsayed/Projects/aviation-dms
export DMS_RELEASE_TAG=<approved-tag>
export DMS_HOSTNAME=<public-https-hostname>
export SMTP_HOST=<smtp-host>
export SMTP_USER=<smtp-user>
export SMTP_FROM=<smtp-from>
export ACME_EMAIL=<acme-email>
export KFL_BOOTSTRAP_TOKEN_FILE=/path/to/bootstrap-token
export SMTP_PASS_SECRET_FILE=/path/to/smtp-password

docker compose config --quiet
```

Expected: exit 0, no output. Missing required variables cause failure.

## Step 2: Build Services

```bash
docker compose build backend frontend upload-validator clamd
```

Expected: all services build without error.

## Step 3: Start Services

```bash
docker compose up -d backend frontend upload-validator clamd
```

Wait for health checks:

```bash
docker compose ps
```

All four services must show `healthy`.

## Step 4: Verify Parser Isolation

Confirm `upload-validator` container properties:

```bash
docker inspect aviation-dms-upload-validator-1 --format 'User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} CapDrop={{.HostConfig.CapDrop}} SecurityOpt={{.HostConfig.SecurityOpt}} Memory={{.HostConfig.Memory}} PidsLimit={{.HostConfig.PidsLimit}}'
```

Expected:
- User=10002:10002
- ReadonlyRootfs=true
- CapDrop=[ALL]
- SecurityOpt=[no-new-privileges:true]
- Memory=1073741824
- PidsLimit=32

## Step 5: Verify ClamAV

Confirm `clamd` is healthy and accepting INSTREAM:

```bash
docker inspect aviation-dms-clamd-1 --format '{{.State.Health.Status}}'
```

Expected: `healthy`

Test clean file:

```bash
python3 -c "
import socket, struct
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect(('127.0.0.1', 3310))
sock.sendall(b'zINSTREAM\x00')
content = b'clean test content'
sock.sendall(struct.pack('!I', len(content)))
sock.sendall(content)
sock.sendall(struct.pack('!I', 0))
response = b''
while not response.endswith(b'\x00'):
    response += sock.recv(1024)
print(response.decode().strip())
sock.close()
"
```

Expected: `stream: OK`

## Step 6: Create Independent Auditor Account

System administrator creates the `independent_auditor` account through user management:
- Account must be named and roster-verified
- Assigned `independent_auditor` role
- Distinct from any source auditor, auditee, or import operator

## Step 7: Validate End-to-End Upload Flow

1. System administrator stages a historical audit import via `/api/p3/audit-report-imports`
2. Independent auditor verifies via `/api/p3/audit-report-imports/{import_id}/verify`
3. Confirm audit report and findings created in one transaction
4. Confirm backdated audit report creation is rejected via `/api/p3/audit-reports`

## Step 8: Validate Personnel Upload Flow

1. Upload credential document via `/api/p2/personnel/uploads/file`
2. Verify via `/api/p2/personnel/uploads/{upload_id}/verify` as distinct reviewer
3. Confirm verification status changes

## Rollback

If any step fails:

```bash
docker compose down
```

Do not proceed until current step passes. Do not commit or push without explicit authorization.

## Open Items (Do Not Block Pilot, Block Go/No-Go)

- Off-host restore target not yet provided
- Source-manual DG Appendix 3 mapping discrepancy not reconciled
- Reverse-proxy body limits not validated under load
