"""Import the September 2026 Safety & Security audit record after source checks.

The reviewed source record contains 38 findings; finding 32 is absent. The
payload must remain reconciled to the authoritative source before import. The
source PDF SHA-256 and curated-payload SHA-256 are pinned; importing requires
separate confirmation of the checksum's authority and reconciliation of every
finding number, title, description, and reference with that PDF.
Idempotent: skips if audit_reports already contains data.

Usage:
  DEV_MODE=true AUDIT_IMPORT_ENABLED=true AUDIT_IMPORT_ATTRIBUTION_CONFIRMED=true AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED=true AUDIT_IMPORT_SOURCE_RECONCILED=true python /Users/mohamedalsayed/Projects/aviation-dms/backend/app/seed_audit_findings.py

`DMS_DB_PATH` must point to a disposable database under the system temporary
directory. This historical import preserves the source auditor attribution; it
does not create or assign an active `independent_auditor` role.
"""

import asyncio
import hashlib
import hmac
import json
import os
import stat
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import database
from app.database import get_db
from app.p3_routes import _snapshot_audit_evidence, _validated_audit_report_evidence_path

NOW = datetime.now().isoformat()

# Auditor / auditee from the report; user confirmed the source auditor spelling.
AUDITOR_ID = "u-safety/security"  # Brian Swanya performed the audit
AUDITEE_ID = "u-accountable" # Utana Kinuthia signed as auditee

AUDIT_DATA = {
    "audit_id": "AUD-SEP2026-001",
    "audit_number": "SS-KFL-SEP 2026",
    "audit_date": "2026-09-28",
    "scope": "Safety and Security",
    "regulatory_basis": "KCARs 2018, KCAA CL: O-SMS003 routine SMS assessment, AVSEC checklist",
    "evidence_file": "attachments/SAFETY AND SECURITY SEPTEMBER  2026 AUDIT REPORT.pdf",
}

# Expected SHA-256 of the reviewed source PDF. Import also requires an
# independent operator confirmation that this digest identifies the authority.
AUDIT_EVIDENCE_SHA256 = "db99508fabee281f86c52fc182c1f54926538e53a298857b0a9b2a12ad156efd"

FINDINGS = [
    # (finding_number, area, level, title, description, regulatory_reference)
    ("1", "Safety & Security", 3,
     "No evidence of periodic review of Safety and Security policy by Senior Management / Safety Review Board",
     "During the time of the Audit there was no evidence demonstrated of periodic review of the Safety and Security policy by the Senior Management and Safety Review Board.",
     "KCARs 2018 / SMS policy review"),
    ("2", "Safety & Security", 2,
     "Safety, Security and Quality policies not displayed or communicated to all workers",
     "At the time of the Audit, the Safety, Security and Quality were not displayed at the premises. It was also noted that the Safety, Security and Quality policy were not communicated to all workers throughout the organization.",
     "KCARs 2018 / SMS policy communication"),
    ("3", "Safety", 2,
     "No evidence that Safety Committee is established and functioning",
     "Evidence was not demonstrated that appropriate safety committee is established and functioning to address safety risks and compliance issues with participation by the Accountable Executive and functional heads.",
     "KCAA CL: O-SMS003"),
    ("4", "Safety", 3,
     "Emergency Response Plan does not address likely emergency/crisis scenarios",
     "Evidence was not demonstrated that the Emergency Response Plan addresses possible or likely emergency and crisis scenarios relevant to KFL's aviation services and product deliveries.",
     "KCARs 2018 / ERP"),
    ("5", "Safety", 3,
     "ERP does not address continuity of safe production/delivery during emergencies",
     "ERP provisions for continuing the safe production, delivery or support of aviation products and services during emergencies or contingencies were not demonstrated.",
     "KCARs 2018 / ERP continuity"),
    ("6", "Safety", 3,
     "No evidence of ERP drills/exercises conducted per plan with documented results",
     "Records were not demonstrated to verify that ERP drills or exercises are conducted in accordance with a plan and that results are documented.",
     "KCARs 2018 / ERP drills"),
    ("7", "Safety", 3,
     "ERP does not address coordination with external customers/subcontractors",
     "Evidence was not demonstrated that the ERP addresses relevant coordination and integration with external customers and subcontractor organizations, where applicable.",
     "KCARs 2018 / ERP coordination"),
    ("8", "Safety", 3,
     "No evidence of periodic ERP review for continued relevance and effectiveness",
     "Evidence of periodic review of the ERP to confirm continued relevance and effectiveness was not demonstrated.",
     "KCARs 2018 / ERP review"),
    ("9", "Safety", 2,
     "No systematic process for analysing safety data to identify trends",
     "Evidence was not demonstrated of a systematic process for analysing safety data and information to identify trends and produce usable management information.",
     "KCAA CL: O-SMS003 / safety data analysis"),
    ("10", "Safety", 2,
     "No documented hazard identification process; no Hazard Register",
     "Evidence of documented process was not demonstrated for identifying hazards from multiple internal and external sources using both reactive and proactive methods. At the time of the Audit there was no evidence of KFL Hazard Register.",
     "KCAA CL: O-SMS003 / hazard identification"),
    ("11", "Safety", 2,
     "Hazards/threats from investigations not transferred to hazard identification and risk assessment",
     "Evidence was not demonstrated that hazards and threats identified during incident or accident investigations are transferred into the hazard identification and risk assessment process.",
     "KCAA CL: O-SMS003 / hazard transfer"),
    ("12", "Safety", 2,
     "Safety investigations not conducted by trained personnel; no root cause analysis",
     "Evidence was not demonstrated that safety investigations are conducted by appropriately trained personnel and identify underlying root causes rather than only describing events.",
     "KCARs 2018 / safety investigation"),
    ("13", "Safety", 2,
     "No accessible mandatory incident-reporting or confidential voluntary reporting mechanism",
     "Evidence was not demonstrated of an accessible mandatory incident-reporting system and a simple, confidential voluntary reporting mechanism for errors, hazards and near misses.",
     "KCARs 2018 / occurrence reporting"),
    ("14", "Safety", 2,
     "No feedback to reporters or regulator after investigations completed",
     "Evidence was not demonstrated that the reporting process provides appropriate feedback to reporters and, where appropriate, to the regulator after investigations are completed.",
     "KCARs 2018 / reporting feedback"),
    ("15", "Safety", 2,
     "Operations/processes/facilities/equipment not progressively subjected to hazard identification and risk assessment",
     "Evidence was not demonstrated that operations, processes, facilities and equipment with aviation safety implications are progressively subjected to hazard identification and risk assessment.",
     "KCAA CL: O-SMS003 / progressive hazard identification"),
    ("16", "Safety", 2,
     "No process ensuring follow-up and implementation of risk assessment actions",
     "Evidence was not demonstrated of a process ensuring that follow-up and recommended actions from completed risk assessments are implemented and verified.",
     "KCAA CL: O-SMS003 / risk assessment follow-up"),
    ("17", "Safety", 2,
     "Completed risk assessment reports not approved by appropriate management level",
     "Evidence was not demonstrated that completed risk assessment reports receive approval from an appropriate level of management.",
     "KCARs 2018 / risk assessment approval"),
    ("18", "Safety", 2,
     "SMS safety performance indicators not developed and agreed with regulator",
     "Evidence was not demonstrated that the organization's SMS safety performance indicators have been developed and agreed with the regulator.",
     "KCAA CL: O-SMS003 / SPIs"),
    ("19", "Safety", 2,
     "SPIs linked to safety objectives not defined, promulgated, monitored, analysed for trends",
     "Evidence was not demonstrated that SPIs linked to safety objectives are defined, promulgated, monitored and analyzed for trends.",
     "KCAA CL: O-SMS003 / SPI trends"),
    ("20", "Safety", 2,
     "No alert levels or performance targets established for SPIs",
     "Evidence was not demonstrated that appropriate alert levels and/or performance targets have been established for the organization's SPIs.",
     "KCAA CL: O-SMS003 / SPI alert levels"),
    ("21", "Safety", 2,
     "No corrective/follow-up action when SPI targets not achieved or alert levels breached",
     "Evidence was not demonstrated of corrective or follow-up action when SPI targets are not achieved or alert levels are breached.",
     "KCAA CL: O-SMS003 / SPI corrective action"),
    ("22", "Safety", 2,
     "No MoC records maintained; MOC not conducted for postholder/location/equipment changes",
     "Evidence was not demonstrated that safety-related management-of-change records, including hazard identification and risk-assessment outcomes, are maintained. MOC was not conducted for the Postholder Change- Head of Operations and Chief Pilot, Location Change, New Equipment and Drone change.",
     "KCARs 2018 / management of change"),
    ("23", "Safety", 2,
     "No internal audit programme with defined schedule, procedures, reporting, follow-up, records",
     "An internal audit programme with a defined schedule and procedures for conducting audits, reporting results, follow-up and maintaining records was not demonstrated.",
     "KCARs 2018 / internal audit programme"),
    ("24", "Safety", 2,
     "No structured SMS training programme covering initial/recurrent training, duties, roles, accountabilities",
     "A structured SMS training programme covering initial and recurrent training, individual duties, roles, responsibilities, accountabilities and operation of the SMS was not demonstrated.",
     "KCARs 2018 / SMS training"),
    ("25", "Safety", 2,
     "No process for measuring SMS training effectiveness",
     "Evidence was not demonstrated of a process for measuring SMS training effectiveness and using results to improve subsequent training.",
     "KCARs 2018 / SMS training effectiveness"),
    ("26", "Safety", 2,
     "No safety publication, circular or communication channel for safety/SMS matters",
     "Evidence was not demonstrated of a safety publication, circular or communication channel through which safety and SMS matters are routinely communicated to employees.",
     "KCARs 2018 / safety communication"),
    ("27", "Safety & Security", 2,
     "AVSEC and Safety accountability not clearly demonstrated; KCAA approval letters not demonstrated",
     "AVSEC accountability and Safety accountability was not clearly demonstrated. During the time of the Audit the KCAA approval letters were not demonstrated.",
     "AVSEC checklist / accountability"),
    ("28", "Security", 2,
     "Personnel security vetting not demonstrated; no annual recurrent background checks",
     "Personnel security vetting not demonstrated. Annual recurrent background checks were not demonstrated during the time of the Audit. Personnel vetting records, criminal-record checks, contractor and temporary-worker screening, access approval records were not also demonstrated.",
     "AVSEC checklist / personnel vetting"),
    ("29", "Security", 2,
     "Secure storage and access control for UAS and associated equipment not demonstrated",
     "Secure storage and access control for UAS and associated equipment not demonstrated. It was observed the drones were easily accessible by anyone inside the premises. With the drones not under lockable and store away cabinets.",
     "AVSEC checklist / UAS storage"),
    ("30", "Security", 2,
     "Protection of UAS against tampering and unauthorized modification not demonstrated",
     "Protection of UAS against tampering and unauthorized modification not demonstrated. During the time of the Audit the following were not demonstrated; pre-deployment inspection records, tamper-evident controls where appropriate, maintenance records, firmware and configuration controls, custody records.",
     "AVSEC checklist / UAS tampering"),
    ("31", "Security", 2,
     "AVSEC training and security awareness arrangements not demonstrated",
     "AVSEC training and security awareness arrangements not demonstrated. During the time of the Audit the Auditee was unable to demonstrate Training matrix, induction records, refresher training, attendance sheets, competence assessments and contractor awareness records.",
     "AVSEC checklist / AVSEC training"),
    ("33", "Security", 2,
     "Security controls at UAS field operating sites not demonstrated",
     "Security controls at UAS field operating sites not demonstrated. At the time of Audit the Auditee was unable to demonstrate Site risk assessments, site access arrangements, launch/recovery checklists, perimeter controls, visitor management, security arrangements for temporary or remote sites.",
     "AVSEC checklist / field site security"),
    ("34", "Security", 2,
     "No procedures for reporting and responding to security threats or unlawful interference",
     "Procedures for reporting and responding to security threats or unlawful interference not demonstrated. At the time of Audit the Auditee was unable to demonstrate AVSEC incident procedure, threat escalation matrix, incident logs, notification records, emergency contact list and records of drills or exercises.",
     "AVSEC checklist / security threat response"),
    ("35", "Security", 2,
     "Controls against unauthorized operations and security-sensitive misuse not demonstrated",
     "Controls against unauthorized operations and security-sensitive misuse not demonstrated. At the time of Audit the Audit the Auditee was unable to demonstrate Operational approvals, airspace and site authorizations, mission plans, operating restrictions where applicable, payload and mission authorisation records for the new drones that have completed operations in 2026. The Drones were also not listed in the Operation Specifications.",
     "AVSEC checklist / unauthorized operations"),
    ("36", "Security", 2,
     "Unlawful-interference and security-event response arrangements not operationally validated",
     "Unlawful-interference and security-event response arrangements not operationally validated. At the time of Audit the Audit the Auditee was unable to demonstrate Response procedures, scenarios for lost control or suspected interference, coordination arrangements with KCAA, air traffic services, site security and law enforcement where appropriate, Security Exercises or Drills.",
     "AVSEC checklist / unlawful interference response"),
    ("37", "Safety", 2,
     "No master fleet record reconciling each UAS to registration, identification, owner/operator, configuration, serviceability",
     "At the time of Audit the Audit No master fleet record was provided that reconciles each UAS used or tested by KFL to its registration, displayed identification, owner/operator, configuration and serviceability status.",
     "KCARs 2018 / fleet records"),
    ("38", "Safety", 2,
     "No technical records to verify maintenance to manufacturer instructions, rectification before release, or modification assessment",
     "At the time of Audit the Audit Technical records were not provided to verify maintenance to manufacturer instructions, rectification before release, or assessment of modifications/software/configuration changes for safety and regulatory impact.",
     "KCARs 2018 / maintenance records"),
    ("39", "Safety", 2,
     "No single retrievable record set connecting each flight to aircraft, pilot, authorization, risk assessment, maintenance status, checklist, airspace coordination, payload, occurrence status and outcome",
     "At the time of Audit the Audit Evidence does not demonstrate a single retrievable record set connecting each flight to aircraft, pilot, authorization, risk assessment, maintenance status, checklist, airspace coordination, payload, occurrence status and outcome.",
     "KCARs 2018 / integrated flight records"),
]

EXPECTED_SOURCE_FINDING_NUMBERS = tuple(str(number) for number in [*range(1, 32), *range(33, 40)])
# Digest of this exact curated payload; it is not a substitute for the PDF digest.
AUDIT_FINDINGS_PAYLOAD_SHA256 = "873416db8ad22519316cb5b458957726aa1a3541db6ed8ce1efe2d9906ebe321"


import uuid

async def seed_audit_findings():
    finding_numbers = tuple(str(finding[0]) for finding in FINDINGS)
    if finding_numbers != EXPECTED_SOURCE_FINDING_NUMBERS:
        raise RuntimeError(
            "Audit seed is disabled: finding numbers must match the hash-pinned source record (1-31, 33-39). "
            "No database rows were written."
        )
    payload = json.dumps(FINDINGS, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(payload_sha256, AUDIT_FINDINGS_PAYLOAD_SHA256):
        raise RuntimeError("Audit finding content changed after source reconciliation; no database rows were written")
    enabled_values = {"1", "true", "yes"}
    if os.getenv("DEV_MODE", "").strip().lower() not in enabled_values:
        raise RuntimeError("Historical audit import is development-only; DEV_MODE must be explicitly true")
    if os.getenv("AUDIT_IMPORT_ENABLED", "").strip().lower() not in enabled_values:
        raise RuntimeError("Set AUDIT_IMPORT_ENABLED=true only for an authorized isolated development import")
    if os.getenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", "").strip().lower() not in enabled_values:
        raise RuntimeError(
            "Confirm the source auditor identity and spelling before setting AUDIT_IMPORT_ATTRIBUTION_CONFIRMED=true"
        )
    if os.getenv("AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED", "").strip().lower() not in enabled_values:
        raise RuntimeError(
            "Independently confirm AUDIT_EVIDENCE_SHA256 against the approved source before setting "
            "AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED=true"
        )
    # Text-extraction layout differs across PDF producers; require an explicit
    # operator attestation that every curated field was reconciled to this pinned source.
    if os.getenv("AUDIT_IMPORT_SOURCE_RECONCILED", "").strip().lower() not in enabled_values:
        raise RuntimeError(
            "Reconcile all finding numbers and content against the hash-pinned source PDF before setting "
            "AUDIT_IMPORT_SOURCE_RECONCILED=true"
        )
    configured_db = Path(database.DB_PATH).expanduser()
    if configured_db.is_symlink():
        raise RuntimeError("Historical audit import database path must not be a symlink")
    target_db = configured_db.resolve()
    scratch_root = Path(tempfile.gettempdir()).resolve()
    try:
        target_db.relative_to(scratch_root)
    except ValueError as exc:
        raise RuntimeError("Historical audit import target database must be inside the system temp directory") from exc
    current_uid = os.getuid() if hasattr(os, "getuid") else None
    directory_stat = target_db.parent.stat()
    directory_mode = stat.S_IMODE(directory_stat.st_mode)
    if (current_uid is not None and directory_stat.st_uid != current_uid) or directory_mode & 0o077 or not directory_mode & stat.S_IWUSR:
        raise RuntimeError("Historical audit import target must be inside a private, owner-only writable directory")
    try:
        database_stat = target_db.lstat()
    except FileNotFoundError as exc:
        raise RuntimeError("Historical audit import requires an initialized scratch database file") from exc
    if (
        not stat.S_ISREG(database_stat.st_mode)
        or (current_uid is not None and database_stat.st_uid != current_uid)
        or database_stat.st_nlink != 1
    ):
        raise RuntimeError("Historical audit import target must be an owner-held single-link regular database file")
    database.DB_PATH = str(target_db)
    evidence_path = _validated_audit_report_evidence_path(AUDIT_DATA["evidence_file"])
    if evidence_path is None:
        raise RuntimeError("The authorized audit evidence PDF must exist and validate under attachments/ before import")
    evidence_snapshot, evidence_sha256, _ = await _snapshot_audit_evidence(
        evidence_path,
        expected_sha256=AUDIT_EVIDENCE_SHA256,
    )
    evidence_snapshot.close()
    db = await get_db()
    try:
        # Idempotent: skip if audit_reports already has data
        cursor = await db.execute("SELECT COUNT(*) FROM audit_reports")
        if (await cursor.fetchone())[0] > 0:
            print("audit_reports already contains data; skipping seed.")
            return

        await db.execute("BEGIN IMMEDIATE")

        # Insert the external audit engagement; all seeded findings belong to this report.
        await db.execute(
            """INSERT INTO audit_reports
               (audit_id, audit_number, audit_date, auditor_id, auditee_id,
                scope, regulatory_basis, status, evidence_file, evidence_sha256, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                AUDIT_DATA["audit_id"],
                AUDIT_DATA["audit_number"],
                AUDIT_DATA["audit_date"],
                AUDITOR_ID,
                AUDITEE_ID,
                AUDIT_DATA["scope"],
                AUDIT_DATA["regulatory_basis"],
                "open",
                AUDIT_DATA["evidence_file"],
                evidence_sha256,
                NOW,
                NOW,
            ),
        )

        # Insert findings
        for (fnum, area, level, title, description, reg_ref) in FINDINGS:
            finding_id = f"AF-{uuid_hex()}"
            await db.execute(
                """INSERT INTO audit_findings
                   (finding_id, audit_id, finding_number, area, level, title,
                    description, regulatory_reference, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    finding_id,
                    AUDIT_DATA["audit_id"],
                    fnum,
                    area,
                    level,
                    title,
                    description,
                    reg_ref,
                    "open",
                    NOW,
                    NOW,
                ),
            )

        await db.commit()
        print(f"Audit findings seeded successfully: {len(FINDINGS)} findings under {AUDIT_DATA['audit_number']}")
    except Exception as e:
        await db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        await db.close()


def uuid_hex() -> str:
    return uuid.uuid4().hex[:8]


if __name__ == "__main__":
    asyncio.run(seed_audit_findings())
