# KFL Aviation DMS — User Onboarding Procedure

**Audience:** Staff members and approved contracted users who have been assigned an account.

**Purpose:** Complete first access, confirm the active role, and find the correct workspace without changing permissions or using another person's account.

## 1. Before first sign-in

- Receive your account invitation and one-time setup link through the organization-approved private channel.
- Do not forward or share an invitation link or code. If it expires, ask the system administrator to issue a replacement.
- Confirm that you were expecting an invitation, and never use a link intended for another person. On `/welcome`, compare the displayed name, canonical account ID, department, and assigned role(s) with your approved access record before continuing; if anything differs or is missing, stop and contact the administrator.
- **Contractor access is not contract-scoped in the current application.** The shared `as_contracted` role grants `document:read`, `safety:read`, `roc:read`, and `aircraft:read`; it does not enforce per-contract or per-function limits. Assign it only when that entire baseline is approved for the named person. Do not activate or use it if the baseline is broader than the approved work; request an explicit access review instead.

## 2. Set up your account

1. Open your invitation's setup link, normally `/setup/invite/<invite-code>`.
2. Enter the username from the invitation and choose your own password. Current setup rules require at least 12 characters and allow at most 72 UTF-8 bytes.
3. Keep the password private. Do not send it to the administrator, include it in a support ticket, or save it in a shared document.
4. Sign in at `/login`. If the setup link has expired or already been used, request a new invite rather than reusing it.

## 3. Confirm the welcome screen

On first sign-in, the `/welcome` page displays your name, canonical account ID, department (or a prompt to confirm it if not listed), and assigned roles. For multi-role accounts, choose the role you are working under for this session.

- Use only a role shown in your assigned-role list.
- Permissions are scoped to the active role; they are not combined across your roles.
- If the name, canonical ID, role list, or department is wrong or missing, stop and report it to the administrator before using the system.
- Select **Continue to work** after confirming the information.

## 4. Use the one-time workspace guide

After onboarding, a short **Quick workspace guide** appears in the application. It explains:

- **My workspace:** shortcuts for the active role.
- **All modules:** expands other screens already permitted to that role; it does not grant access.
- **Role switching:** changes the workspace and keeps permissions scoped to the newly active role.

The guide is shown once per canonical account in that browser profile. Selecting **Got it** dismisses it. Clearing the browser's site data or using another browser profile may show it again. The guide's local dismissal state does not change your account or permissions.

## 5. Find your role's workspace

Use **My workspace** for the role's primary screens. Select **All modules** when you need another screen already available to your active role. Notifications require `compliance:read`; `safety:read` alone does not grant access to the notification service.

| Active role | Primary landing |
|---|---|
| `system_admin` | System Observability |
| `accountable_manager` | Organization Overview |
| `librarian` | Documents |
| `head_quality` | Audit Dashboard |
| `head_safety` | Safety Actions |
| `head_security` | Security Reviews |
| `head_operations`, `chief_pilot`, `flight_ops_officer` | Missions |
| `head_training` | Training Management |
| `head_maintenance` | Maintenance Management |
| `dg_coordinator` | Dangerous Goods Shipments |
| `occurrence_reporter` | Safety Occurrences |
| `records_custodian` | Documents |
| `independent_auditor` | Audit Reports |
| `as_contracted` | Documents (only if the shared baseline permissions are approved; this role is not contract-scoped) |

### Role-specific notes

- **Accountable Manager:** Organization Overview summarizes records and provides count-based review prompts. These are not operational or regulatory approvals. The NOTAM panel currently reports that no approved feed is connected; it does not mean there are no NOTAMs. Consult the applicable approved official source.
- **Document changes:** Use a proposal workflow when your role permits `document:propose`. Saving edited document content requires `document:update`. Approval and publication are separate controlled actions; do not treat a proposal as an approved change.
- **Occurrence Reporter:** `safety:read` is retained so reporters can view the safety screens assigned to their role. Use the application only for authorized safety work.
- **Contracted users:** `as_contracted` is a shared baseline, not a contract-scoped role. Contact the administrator for an individual access review before use; do not infer permissions from your job title, contract, or another contractor's account.

## 6. Change active role or get help

If your account has multiple assigned roles, use **Active role** in the account/session panel. The primary workspace updates to the selected role. If a required screen is missing or access is denied, contact the system administrator to review the assignment; do not ask another user to sign in for you.

## 7. Protect the session and information

- Never share passwords, invitation links/codes, reset links, or session details.
- Use **Account security** to manage your password through the approved flow.
- Sign out when finished, especially on a shared workstation.
- Report unexpected access, missing role assignments, or suspicious activity to the designated administrator.
- Do not rely on a summary panel as flight release, airworthiness approval, or regulatory confirmation.

## First-use checklist

- [ ] Invitation and setup completed using your own account.
- [ ] Name, canonical account ID, department (if listed), and assigned roles confirmed against the approved access record.
- [ ] Correct active role selected for this session.
- [ ] Workspace guide reviewed or dismissed.
- [ ] Required work is visible under **My workspace** or **All modules**.
- [ ] Any identity, role, or access mismatch reported before work begins.
