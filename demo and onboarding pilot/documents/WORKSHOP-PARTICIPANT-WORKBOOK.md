# Pre-Onboarding Workshop — Participant Workbook

## Purpose

Workbook for pilot participants. Covers role responsibilities, approval checkpoints, and what each person signs off on. Complete during and after the workshop.

## Participant Roles

| Role | Responsibility in Pilot | Approval Checkpoints |
|------|------------------------|----------------------|
| Records Custodian | Retention/legal-hold basis, hold release, disposition process; classify missing/unmatched files | Retention values (36 months general / lifetime metadata), file disposition classification |
| Accountable Manager | Recovery objectives, final go/no-go, off-host destination authorization | Off-host restore target, RPO/RTO, go/no-go decision |
| Backend/IT | Scanner provisioning, quota configuration, reverse-proxy validation, memory bounds | Scanner endpoint, quota value, body limits under load |
| System Administrator | Roster/invitations, account activation, environment standup | First independent_auditor account creation |
| Responsible Postholders | Source-to-rule mappings, delegations, checklists, relevant limits | DG Appendix 3 reconciliation, manual version validation |
| Independent Auditor | Provenance verification of historical audit imports | First import verification, checksum attestation |

## Your Pre-Workshop Preparation

### All Participants

- [ ] Read the Pilot Scope & Constraints document
- [ ] Read the Onboarding Readiness Checklist
- [ ] Come prepared to confirm or object to each gate item

### Records Custodian

- [ ] Review retention rule RR-023 (36 months general operational records)
- [ ] Review retention rule RR-025 (lifetime metadata records)
- [ ] Identify local missing/unmatched file findings needing classification
- [ ] Confirm no automatic disposition will be implemented without your approval

### Accountable Manager

- [ ] Identify authorized off-host restore destination
- [ ] Define RPO (Recovery Point Objective) and RTO (Recovery Time Objective)
- [ ] Define acceptance criteria for restore drill
- [ ] Prepare final go/no-go decision criteria

### Backend/IT Lead

- [ ] Confirm scanner endpoint `clamd:3310` is operational
- [ ] Confirm quota 30 GB is configured
- [ ] Confirm P3 limits (10 MiB evidence, 5 MiB import body)
- [ ] Prepare reverse-proxy body limit validation plan

### System Administrator

- [ ] Confirm roster-verified independent_auditor candidate
- [ ] Prepare account creation procedure
- [ ] Confirm no unauthorized account activation

### Responsible Postholders

- [ ] Review DG Appendix 3 discrepancy (five named checks vs "10 Appendix 3 checks")
- [ ] Prepare source-to-rule mapping positions
- [ ] Identify delegation and checklist items needing sign-off

### Independent Auditor

- [ ] Confirm readiness to verify provenance of historical audit imports
- [ ] Understand source auditor, auditee, importer, and verifier must be distinct principals
- [ ] Review verification attestation requirements (checksum + findings reconciliation, 20+ char notes)

## Workshop Notes

Use this space to capture notes during each section:

### Readiness Gate Review

| Gate Item | Confirmed? | Open Item? | Owner |
|-----------|------------|------------|-------|
| Quota 30 GB | | | |
| Scanner clamd:3310 | | | |
| Validator isolation | | | |
| Backdated report rejection | | | |
| Provenance verification | | | |
| Personnel upload flow | | | |
| Retention 36mo / lifetime | | | |
| Flight release disabled | | | |

### Pilot Scope and Constraints

| In-Scope Item | Confirmed? |
|---------------|------------|
| independent_auditor pilot account | |
| Provenance import workflow | |
| Personnel uploads | |
| Audit reports listing | |
| Backup validation | |

| Out-of-Scope Item | Acknowledged? |
|-------------------|---------------|
| Flight release | |
| Staging access | |
| Source-PDF upload through UI | |
| Automatic disposition | |
| Commit/push | |
| Account invitation beyond pilot | |
| Real audit import | |
| Off-host restore drill | |

### Retention Policy

| Rule | Value | Confirmed? |
|------|-------|------------|
| RR-023 General operational records | 36 months | |
| RR-025 Metadata records | Lifetime | |

### Off-Host Restore

| Item | Value | Owner | Due Date |
|------|-------|-------|----------|
| Destination | | | |
| RPO | | | |
| RTO | | | |
| Acceptance criteria | | | |

### Source-Manual Reconciliation

| Item | Owner | Due Date |
|------|-------|----------|
| DG Appendix 3 mapping | | |
| Manual version validation | | |
| Delegation sign-off | | |

## Action Items Assigned to Me

| Action | Due Date | Status |
|--------|----------|--------|
| | | |
| | | |

## Go/No-Go Criteria

| Criterion | Met? |
|-----------|------|
| All readiness gates confirmed | |
| Off-host restore target identified | |
| Source-manual reconciliation path forward | |
| Accountable Manager go/no-go | |

## Sign-off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| | | | |
