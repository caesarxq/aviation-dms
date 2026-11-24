# Incident & Escalation Contacts — Aviation DMS Pilot

## Purpose

Contact and escalation guidance for operational incidents during the restricted onboarding pilot. Not a credential file; no secrets or passwords are included here.

## Incident Categories

| Category | Examples | Primary Contact | Escalation |
|----------|----------|-----------------|------------|
| Scanner outage | ClamAV unavailable, infected file detected, scan timeout | Backend/IT Lead | Accountable Manager |
| Quota exhaustion | Storage quota approaching or exceeded | Backend/IT Lead | Records Custodian |
| Upload failure | Malware detected, malformed file, validation failure | Backend/IT Lead | System Administrator |
| Retention/disposition | Legal hold, file disposition, orphan classification | Records Custodian | Accountable Manager |
| Restore drill failure | Backup candidate validation failure, restore test failure | Accountable Manager | Backend/IT Lead |
| Source-manual discrepancy | DG Appendix 3 mapping, manual version conflict | Responsible Postholders | Accountable Manager |
| Account/role issue | Invite failure, role assignment, activation | System Administrator | Accountable Manager |
| Reverse-proxy issue | Caddy routing, body limit, header problem | Backend/IT Lead | System Administrator |

## Incident Response Steps

### 1. Detect

Identify the incident category from the table above. Gather:
- Time of occurrence
- Affected endpoint or service
- Error message or symptom
- User or account involved (if any)

### 2. Contain

- For scanner outage: uploads fail closed automatically; no new uploads accepted
- For quota exhaustion: uploads fail closed automatically; no new uploads accepted
- For malware detection: file is rejected; no persistence attempted
- For account issue: do not activate or invite accounts without authorization

### 3. Notify

Contact the Primary Contact for the category. If unavailable, contact the Escalation contact.

### 4. Resolve

Work with the Primary Contact to restore service. Do not bypass fail-closed safeguards (scanner, quota, body limits) to restore service faster.

### 5. Document

Record the incident in the operational log:
- What happened
- When it started and ended
- What was impacted
- What was done to resolve
- What follow-up actions are needed

## Do Not

- Do not share credentials, tokens, or private keys
- Do not bypass scanner or quota fail-closed behavior
- Do not deploy or promote without explicit authorization
- Do not access staging without explicit authorization
- Do not commit or push repository changes without explicit authorization
- Do not delete or repair orphan files without Records Custodian approval

## Maintenance Windows

Scanner signature database freshness must be monitored outside the DMS. Backup signature updates do not require DMS downtime but should be scheduled to avoid peak upload periods.

## Revision History

| Version | Date | Change | Author |
|---------|------|--------|--------|
| 1.0 | 2026-11-08 | Initial draft | Chief of Staff |
