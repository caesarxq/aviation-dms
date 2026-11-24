# Internal Readiness Gate Reconciliation — 2026-11-08

**Classification:** Internal working verification record. Not a controlled manual, approval, import authorization, or operational release.  
**Scope:** Local repository and local development database only. No staging, remote host, off-host store, or live account system was accessed. No database record, source PDF, or role assignment was changed.

## Executive summary

The six manual/authority PDF hashes cited by the repository match the supplied source files. A text-layer comparison found substantial but not exact lexical overlap between five source manuals and their current DMS HTML payloads; this is a diagnostic, not evidence of complete or effective content. The local DMS catalogue is more current than some planning-document statements: the sampled published pointers and approval fields differ from the older planning baseline. Source files and approval artifacts are not present in the local application attachment roots.

The local development database also contains a legacy September 2026 audit row with 38 findings, but no application evidence file or new provenance-import table. Its legacy auditor identifier is `u-safety`, while the approved provenance design keeps source auditor attribution separate as `u-safety/security`; this record was not changed. Finding 32 is absent from the source report and remains absent from the legacy rows. The local upload inventory has unresolved missing/unmatched files. All such items remain untouched.

Upload code now requires an explicitly approved system-quota scope/value and an internal ClamAV-compatible scanner endpoint; neither is configured by Compose defaults. A read-only orphan inventory and isolated backup-candidate validator are available, but no actual off-host restore was performed.

## Source files and hashes

The six source hashes match both repository metadata and the local development catalogue rows. These hashes bind to the exact supplied bytes; they do not by themselves prove current effectivity, DMS custody, or postholder approval.

| Source | SHA-256 |
|---|---|
| `KFL 2021 COMPANY ABCD.pdf` | `92a2509879ca39aafd88e69a5a7cbfdfb536715753da674e27689b2929af07b3` |
| `KFL 2021 SAFETY.pdf` | `46b8d26ee14e952899a03d287fceee1a4fe0be9c193cb47047fca37ea5d01f8f` |
| `KFL REVISED SECURITY MANUAL.pdf` | `20efd7c392f8ffa0ab007b3f84a645709211bd9e62d252a71afb1dd11ba2bd03` |
| `KFL QUALITY.pdf` | `82dc4d547aa0ac1d2f27c693aa91e7c81dfd3a27994c5069e6524c4fc0e6463e` |
| `DANGEROUS GOODS MANUAL KFL 01 may 2025.pdf` | `90e06fac387de092a1144fdf598e93368068b6de5e978fa0bab315a89766b823` |
| `KFL ROC & OPSSPEC 2027.pdf` | `b892512dff83304a1b2e7e2b8b71ffcf29aca3f7538066869e20ebb9a378c4c8` |

The supplied `SAFETY AND SECURITY SEPTEMBER  2026 AUDIT REPORT.pdf` hashes to `db99508fabee281f86c52fc182c1f54926538e53a298857b0a9b2a12ad156efd`, matching the digest pinned in the historical development seeder. It is not one of the six manual/authority source PDFs above. The source attachment filename has **two spaces** before `2026`; the historical seeder used one. I corrected the seeder reference to preserve the supplied filename exactly. The existing local legacy database row still has the one-space path and was not rewritten.

## Source-to-DMS content comparison

A diagnostic compared `pdftotext -layout` output with text extracted from each current-version HTML payload after removing markup and normalizing tokens. The comparison is only lexical presence; it does not validate ordering, exact wording, page layout, images, signatures, effective status, or source-to-rule mappings.

| DMS ID | Source pages | Source unique-word coverage in HTML text | Unique source words not found |
|---|---:|---:|---:|
| DOC-001 Operations Manual | 103 | 94.90% | 114 |
| DOC-002 Safety Management Manual | 40 | 92.16% | 108 |
| DOC-006 Security Management System Manual | 45 | 90.77% | 160 |
| DOC-007 Dangerous Goods Manual | 35 | 94.58% | 68 |
| DOC-012 Quality Management System Manual | 71 | 98.06% | 33 |

The unmatched-token counts require a qualified page/section comparison; they are not proof that the corresponding content is absent, nor proof of conformance. No HTML or source PDF was edited.

## Read-only local DMS snapshot

This snapshot came from `backend/data/dms.db` using a read-only SQLite URI. It is **not staging state**.

- DOC-001, DOC-002, DOC-006, DOC-007, and DOC-012 currently point to published versions. DOC-007 also has a draft version, but its current-version pointer remains on the published version.
- DOC-001, DOC-002, DOC-006, and DOC-012 carry KCAA approval metadata dated `2021-07-23`. The local `kcaa_approval_evidence` table contains no evidence rows, and the local `backend/data/kcaa-evidence/` and `backend/data/attachments/` roots are absent. Thus approval metadata and profile-held source copies are not equivalent to DMS-retained approval/source bytes.
- DOC-007 remains `pending_letter`, with `kcaa_approved=0`. Its filename says May 2025 while the internal issue/effective-page text says Issue 01, Rev 00, `01 May 2024`; the supplied KCAA acceptance/approval fields are blank. Keep the separate approval letter and version/date reconciliation open.
- DOC-003 remains a non-standalone maintenance reference mapped to the Operations Manual plus OEM specifications. DOC-004 and DOC-005 map to OM Part D and Part B; their separate catalogue payloads are short summaries, not independent manuals. No standalone DOC-004/005 source should be invented. Aircraft-specific OEM maintenance and approved checklist evidence remains outstanding.
- The local `roc_register` row for ROC-001 is active, issued `2026-10-12`, expires `2027-10-11`, and covers seven registrations. This does not establish authority coverage for the remaining master-fleet aircraft.
- `WORKFLOW-LOGIC-IMPLEMENTATION-PLAN.md` contains older claims that sampled approval fields are unset and DOC-012 is draft; those statements conflict with this local snapshot and with `WORKFLOW-CONFORMANCE-AUDIT-REPORT.md`. The snapshot resolves only this local database, not staging or source-owner approval.

## Legacy audit and local file reconciliation

The local database already contains one legacy audit row, status `open`, with **38 findings** numbered 1–31 and 33–39. The supplied report goes from 31 to 33; there is no finding 32. No finding 32 was created. The text labels the source auditor “Swanya Brian”; the user-confirmed display form is Brian Swanya.

- The legacy row points to `attachments/SAFETY AND SECURITY SEPTEMBER 2026 AUDIT REPORT.pdf`, but the local app attachments root is absent. The legacy audit table has no evidence SHA-256 column, and the local database has no `audit_report_imports` provenance table. Its stored `auditor_id` is `u-safety`, not the approved literal source-auditor ID `u-safety/security`; the relationship has not been reconciled. This row's origin and custody are unverified. Do not silently rewrite attribution, re-import findings, or treat the local row as a provenance-verified import.

The normal in-app report endpoint now rejects an `audit_date` earlier than the current UTC date and requires historical records to use the provenance-import workflow. This closes the backdating bypass at the API boundary; responsible postholders must still confirm UTC versus local-calendar interpretation before operational use. No database rows were changed.

The report-only local upload inventory found:

- one personnel-upload database row whose recorded file path is missing;
- three physical files in the local uploads root, 51 bytes total, that do not match any registered path;
- no local KCAA-evidence or audit-attachment files;
- the local personnel-upload schema lacks `file_sha256`.

No path, file bytes, database record, or directory entry was changed. These are local development artifacts/data, not verified staging findings; classify them with the Records Custodian before cleanup.

## Upload-safeguard implementation state

- Existing per-file limits remain unchanged at 10 MiB for personnel and KCAA evidence uploads.
- The API has a process-local two-request semaphore for uploads and evidence reads; P3 JSON mutations acquire the same slots at ASGI ingress before Pydantic parsing, with a fixed 128 KiB cap except import-create requests, which require an explicit positive `DMS_P3_IMPORT_BODY_MAX_BYTES` (Compose empty by default). The isolated-validator client is asynchronous, cancellation closes the connection under its seven-second total deadline, and no validator thread is left running. Budget up to two API payload buffers per backend worker plus two service buffers per validator instance; multiply by worker/replica count. Reverse-proxy request-body limits remain unvalidated.
- Upload endpoints fail closed unless all of the following are explicitly configured: `DMS_UPLOAD_QUOTA_SCOPE=system`, a positive `DMS_UPLOAD_STORAGE_QUOTA_BYTES`, internal `DMS_CLAMD_HOST`/`DMS_CLAMD_PORT`, and finite `DMS_CLAMD_TIMEOUT_SECONDS` no greater than the approved finite `DMS_CLAMD_MAX_TIMEOUT_SECONDS`. Compose defaults quota to `system` scope and `30000000000` bytes (30 GB), scanner endpoint to `clamd:3310`, timeout to 60s with max 60s, P3 evidence max to 10485760 bytes, and P3 import body max to 5242880 bytes. The internal `clamd` container has been provisioned and verified (Dropped capabilities, no-new-privileges, 1 GiB memory, 1 CPU, 64 PIDs, no host port publishing). Reverse-proxy body limits and worker/replica memory bounds still require deployment validation.
- The system-scope quota counts the upload, KCAA-evidence, and audit-attachment roots under a local file lock. If Records Custodian/Accountable Manager approve another quota scope, implement it before configuring the service; only `system` is currently supported.
- Personnel and KCAA PDF/image intake validation is sent to a separate, fail-closed validator service and runs in a bounded, timed child process. The worker applies CPU/file-size/file-descriptor/core limits, drops root to `nobody` where applicable, and sets Linux `no_new_privs` plus a 512 MiB address-space ceiling. ClamAV-compatible scanner failures, timeouts, infection results, or quota exhaustion prevent persistence. KCAA files use private directory/file modes and fsync; downloads verify size/hash from the same bounded byte snapshot.
- Parser isolation is now configured as a separate `upload-validator` Compose service: it runs as UID/GID 10002, has a read-only root filesystem, no DMS data volume or Docker secrets, dropped capabilities, `no-new-privileges`, resource limits, and only an internal network shared with the backend. The validator calls the bounded parser child; the backend fails closed if the service is absent. Compose configuration passed, but no Docker container was started, so network/mount isolation and runtime limits remain unverified deployment gates.
- `backend/app/upload_reconciliation.py` is report-only. It can inventory paths/sizes and optionally read file bytes to compare stored SHA-256 values. It never deletes, repairs, or imports records. It must be run against an explicitly selected candidate or local path, not used as automatic disposition.
- P3 audit evidence remains pre-staged rather than uploaded by its API. Its reference path now requires an explicit positive `DMS_AUDIT_EVIDENCE_MAX_BYTES`, the shared quota/scanner configuration, malware screening, and bounded child-process PDF validation; missing configuration fails closed. Compose leaves the new limit empty. No real scanner or approved evidence-size limit has been configured or tested.
- P2 personnel and P3 provenance verification now scan/parse stable evidence before `BEGIN IMMEDIATE`, then re-read and compare candidate state/path/digests under short write transactions. Focused regression tests show the slow validation step does not hold a SQLite write lock; deployment-level contention with the approved scanner, import-size limit, and worker count remains untested.
- Retention/legal-hold policy implemented via `retention_rules` table: RR-023 sets 36 months (3 years) retention for general operational records; RR-025 sets lifetime retention for metadata records (audit trails, system logs, legal hold records). No automatic file disposition — `upload_reconciliation.py` remains report-only and never deletes or repairs files.

## Off-host backup/restore status

No off-host destination, backup artifact, or approved RPO/RTO/restore acceptance criteria are recorded in this workspace. No staging/remote backup was accessed. The repository now has `backend/app/backup_validation.py`, which can create a SHA-256 file manifest on an explicitly isolated backup copy and verify a separate restore candidate read-only. It checks the manifest, SQLite quick/integrity/foreign-key checks, all tables declared by the current application schema plus critical evidence/identity columns, referenced files, and stored digests; it blocks pre-migration/truncated schemas and does not copy, restore, migrate, start the app, or access a remote store. The CLI was exercised only on a disposable scratch candidate.

A genuine off-host drill remains blocked pending: Accountable Manager-approved recovery objectives and acceptance criteria; an authorized off-host destination with encryption/versioning/retention/access controls; a complete source backup; and a separate isolated restore target. Creating a manifest only after downloading an unmanifested backup does not establish transfer integrity.

## Owner actions / blockers

| Owner | Required action before gate closure |
|---|---|
| Backend/IT | Provision and monitor an internal ClamAV-compatible scanner (including signature freshness); configure quota, finite scanner timeout/maximum, P3 evidence size, and P3 import body limit only after approved scope/values; verify the `upload-validator` container's UID, mounts, egress, and resource limits in a disposable Docker environment (completed: UID 10002, read-only root, cap_drop ALL, no-new-privileges, 768 MiB memory, 16 PIDs, internal-only network, no host port publishing); verify `clamd` container isolation (completed: dropped capabilities, no-new-privileges, 1 GiB memory, 1 CPU, 32 PIDs, no host port publishing); validate reverse-proxy body limits and worker/replica memory bounds under load. |
| Records Custodian | Approve retention/legal-hold basis, event start, hold release and disposition process; classify the local missing/unmatched file findings before any cleanup. |
| Accountable Manager | Approve recovery objectives/acceptance criteria and final go/no-go; authorize an off-host destination and isolated restore drill. |
| Responsible postholders | Validate effective manual versions and sign source-to-rule mappings, delegations, checklists and relevant limits. |
| Independent Auditor | Reconcile the legacy audit row to the retained source and approved source-attribution design; verify importer/verifier provenance independently. |
| System Administrator | Confirm roster and any later account action; this report authorizes no invitations, activation, or role change. |

**Status:** Technical preparation progressed locally; operational, policy, provenance, off-host recovery, and regulatory gates remain open. No deployment, real audit import, source-file upload, account change, or commit was made.
