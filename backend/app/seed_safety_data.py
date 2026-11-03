"""
Seed realistic safety management data for E2E and manual testing.

Seeds the following tables with aviation-realistic data:
  - occurrences (Safety Occurrence Reports / MOR)
  - hazards (Hazard Register)
  - risk_assessments (SMS 5x5 + OM flight risk tool)
  - safety_actions (Corrective / preventive actions)
  - safety_kpis (Monthly/quarterly safety metrics)
  - missions (Flight missions)

All foreign keys reference existing seed data:
  - users: u-safety, u-reporter, u-ops, u-chief-pilot, u-flight-ops, u-maintenance, u-quality, u-accountable
  - aircraft: 20 master-fleet registrations; OpSpec authorization remains a separate 7-aircraft subset
  - roc_register: ROC-001

Usage:
  DEV_MODE=true python /Users/mohamedalsayed/Projects/aviation-dms/backend/app/seed_safety_data.py
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timedelta
import bcrypt

# Ensure the backend app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db

NOW = datetime.now()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def seed_safety_data():
    if os.getenv("DEV_MODE", "false").lower() != "true":
        raise RuntimeError("Safety test data seeding is development-only")
    e2e_password = os.getenv("DMS_E2E_SEED_PASSWORD", "")
    if e2e_password and (len(e2e_password.encode("utf-8")) < 12 or len(e2e_password.encode("utf-8")) > 72):
        raise RuntimeError("DMS_E2E_SEED_PASSWORD must be between 12 and 72 UTF-8 bytes")
    e2e_password_hash = bcrypt.hashpw(e2e_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode() if e2e_password else None
    db = await get_db()
    try:
        # Guard: only seed if tables are empty (idempotent)
        for table in ("occurrences", "hazards", "risk_assessments", "safety_actions", "safety_kpis", "missions"):
            cur = await db.execute(f"SELECT COUNT(*) FROM {table}")
            if (await cur.fetchone())[0] > 0:
                print(f"{table} already contains data; skipping seed.")
                return

        await db.execute("BEGIN IMMEDIATE")

        # ------------------------------------------------------------------
        # 1. OCCURRENCES (Safety Occurrence Reports / MOR)
        # ------------------------------------------------------------------
        base = NOW - timedelta(days=180)
        occurrences = [
            # (occurrence_id, serial_number, title, description, occurrence_type, severity,
            #  status, reporter_id, reporter_confidential, location, occurred_at, reported_at,
            #  acknowledged_at, acknowledged_by, mor_required, mor_deadline, mor_submitted_at,
            #  investigation_id, created_at, updated_at, created_by, updated_by)
            (
                "OCC-SEED-001", "MOR-2026-014", "Unplanned battery depletion during survey flight",
                "Battery level dropped to 12% sooner than expected during a mapping survey over "
                "Eastleigh. Aircraft returned to base safely with 8% remaining. Cause attributed to "
                "cold temperature reducing battery efficiency.",
                "technical_fault", "major", "closed", "u-reporter", 0,
                "Wilson Airport, Hangar 4",
                _iso(base + timedelta(days=10)), _iso(base + timedelta(days=10, hours=1)),
                _iso(base + timedelta(days=11)), "u-safety", 1,
                _iso(base + timedelta(days=15)), _iso(base + timedelta(days=16)),
                None, _iso(base + timedelta(days=10)), _iso(base + timedelta(days=16)),
                "u-safety", "u-safety",
            ),
            (
                "OCC-SEED-002", "MOR-2026-022", "GPS signal loss near controlled airspace boundary",
                "Temporary loss of GPS lock for ~45 seconds while operating near the edge of "
                "Nairobi FSS controlled airspace. Pilot switched to ATTI mode and maintained VLOS. "
                "No airspace penetration occurred.",
                "operational_deviation", "serious", "closed", "u-flight-ops", 0,
                "Kahawa West, near C52 boundary",
                _iso(base + timedelta(days=35)), _iso(base + timedelta(days=35, hours=2)),
                _iso(base + timedelta(days=36)), "u-safety", 1,
                _iso(base + timedelta(days=40)), _iso(base + timedelta(days=41)),
                "INV-SEED-001", _iso(base + timedelta(days=35)), _iso(base + timedelta(days=41)),
                "u-safety", "u-safety",
            ),
            (
                "OCC-SEED-003", "MOR-2026-031", "Bird strike during final approach",
                "Small bird struck the propeller of AC-019 during final approach to Wilson Airport. "
                "Minor propeller damage noted post-flight. No injury or third-party impact.",
                "weather_incident", "medium", "closed", "u-chief-pilot", 0,
                "Wilson Airport Runway 04",
                _iso(base + timedelta(days=52)), _iso(base + timedelta(days=52, hours=1)),
                _iso(base + timedelta(days=53)), "u-safety", 1,
                _iso(base + timedelta(days=55)), _iso(base + timedelta(days=56)),
                None, _iso(base + timedelta(days=52)), _iso(base + timedelta(days=56)),
                "u-safety", "u-safety",
            ),
            (
                "OCC-SEED-004", "MOR-2026-047", "Unauthorized person within 50m of launch site",
                "A member of the public entered the established safety perimeter during pre-flight "
                "checks for a delivery mission. Launch was aborted until the area was cleared.",
                "security_concern", "serious", "acknowledged", "u-ops", 0,
                "Industrial Area, Mombasa Road",
                _iso(base + timedelta(days=78)), _iso(base + timedelta(days=78, hours=3)),
                _iso(base + timedelta(days=79)), "u-security", 0,
                None, None,
                None, _iso(base + timedelta(days=78)), _iso(base + timedelta(days=79)),
                "u-ops", "u-ops",
            ),
            (
                "OCC-SEED-005", "MOR-2026-053", "Payload camera gimbal failure mid-flight",
                "Gimbal motors stalled during aerial photography mission. Pilot executed return-to-home "
                "manually. Aircraft recovered with no damage beyond the gimbal assembly.",
                "technical_fault", "major", "investigating", "u-reporter", 0,
                "Karen, Nairobi",
                _iso(base + timedelta(days=95)), _iso(base + timedelta(days=95, hours=1)),
                None, None, 0,
                None, None,
                "INV-SEED-002", _iso(base + timedelta(days=95)), _iso(base + timedelta(days=95)),
                "u-safety", "u-safety",
            ),
            (
                "OCC-SEED-006", "MOR-2026-061", "Strong wind encounter beyond forecast",
                "Wind gusts of 22 kt encountered at 120 ft AGL, exceeding the 15 kt operational limit "
                "for AC-005. Pilot initiated immediate landing. No damage.",
                "weather_incident", "medium", "acknowledged", "u-flight-ops", 0,
                "Kajiado, Magadi Road",
                _iso(base + timedelta(days=112)), _iso(base + timedelta(days=112, hours=1)),
                _iso(base + timedelta(days=113)), "u-safety", 0,
                None, None,
                None, _iso(base + timedelta(days=112)), _iso(base + timedelta(days=113)),
                "u-ops", "u-ops",
            ),
            (
                "OCC-SEED-007", "MOR-2026-074", "Loss of video downlink during BVLOS segment",
                "Video feed lost for 90 seconds during EVLOS segment under approved waiver. Telemetry "
                "and C2 link remained intact. Flight continued under pilot telemetry monitoring.",
                "technical_fault", "minor", "closed", "u-flight-ops", 0,
                "Konza Technopolis",
                _iso(base + timedelta(days=130)), _iso(base + timedelta(days=130, hours=2)),
                _iso(base + timedelta(days=131)), "u-safety", 1,
                _iso(base + timedelta(days=135)), _iso(base + timedelta(days=136)),
                None, _iso(base + timedelta(days=130)), _iso(base + timedelta(days=136)),
                "u-safety", "u-safety",
            ),
            (
                "OCC-SEED-008", "MOR-2026-089", "Near-miss with manned helicopter",
                "Visual sighting of a police helicopter at approximately 200 ft horizontal separation "
                "during a survey flight at Wilson Airport. Aircraft immediately descended and cleared "
                "the area. KCAA notified per MOR procedures.",
                "operational_deviation", "catastrophic", "closed", "u-chief-pilot", 1,
                "Wilson Airport, CTR",
                _iso(base + timedelta(days=150)), _iso(base + timedelta(days=150, hours=1)),
                _iso(base + timedelta(days=151)), "u-safety", 1,
                _iso(base + timedelta(days=155)), _iso(base + timedelta(days=156)),
                "INV-SEED-003", _iso(base + timedelta(days=150)), _iso(base + timedelta(days=156)),
                "u-accountable", "u-accountable",
            ),
            (
                "OCC-SEED-009", "MOR-2026-102", "Pre-flight inspection found cracked propeller blade",
                "During pre-flight checks, a hairline crack was discovered on one propeller blade of "
                "AC-012. Aircraft tagged out of service and blade replaced before next flight.",
                "technical_fault", "medium", "closed", "u-maintenance", 0,
                "Wilson Airport Maintenance Hangar",
                _iso(base + timedelta(days=168)), _iso(base + timedelta(days=168, hours=1)),
                _iso(base + timedelta(days=169)), "u-safety", 0,
                None, None,
                None, _iso(base + timedelta(days=168)), _iso(base + timedelta(days=169)),
                "u-maintenance", "u-maintenance",
            ),
            (
                "OCC-SEED-010", "MOR-2026-115", "Radio interference during flight near broadcast tower",
                "Intermittent RC signal degradation observed when operating within 1 km of a commercial "
                "broadcast transmitter on Kangundo Road. Pilot maintained VLOS and returned home.",
                "technical_fault", "minor", "reported", "u-reporter", 0,
                "Kangundo Road, Nairobi",
                _iso(base + timedelta(days=175)), _iso(base + timedelta(days=175, hours=1)),
                None, None, 0,
                None, None,
                None, _iso(base + timedelta(days=175)), _iso(base + timedelta(days=175)),
                "u-reporter", "u-reporter",
            ),
            (
                "OCC-SEED-011", "MOR-2026-128", "Incorrect battery installed (mismatched capacity)",
                "Ground crew installed a 4200 mAh battery instead of the specified 5200 mAh unit for "
                "a mapping mission. Flight time reduced by ~25%. Mission completed but landed early.",
                "human_factor", "minor", "closed", "u-maintenance", 0,
                "Wilson Airport",
                _iso(base + timedelta(days=178)), _iso(base + timedelta(days=178, hours=1)),
                _iso(base + timedelta(days=179)), "u-safety", 0,
                None, None,
                None, _iso(base + timedelta(days=178)), _iso(base + timedelta(days=179)),
                "u-maintenance", "u-maintenance",
            ),
            (
                "OCC-SEED-012", "MOR-2026-133", "Emergency response drill - simulated crash",
                "Quarterly emergency response drill simulating a crash landing at Dagoretti Corner. "
                "Response time, cordon establishment, and KCAA notification tested. All objectives met.",
                "emergency_response", "minor", "closed", "u-security", 0,
                "Dagoretti Corner, Nairobi",
                _iso(base + timedelta(days=179)), _iso(base + timedelta(days=179, hours=1)),
                _iso(base + timedelta(days=180)), "u-safety", 0,
                None, None,
                None, _iso(base + timedelta(days=179)), _iso(base + timedelta(days=180)),
                "u-security", "u-security",
            ),
        ]
        for o in occurrences:
            await db.execute(
                """INSERT INTO occurrences
                   (occurrence_id, serial_number, title, description, occurrence_type, severity,
                    status, reporter_id, reporter_confidential, location, occurred_at, reported_at,
                    acknowledged_at, acknowledged_by, mor_required, mor_deadline, mor_submitted_at,
                    investigation_id, created_at, updated_at, created_by, updated_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                o,
            )

        # ------------------------------------------------------------------
        # 2. HAZARDS (Hazard Register)
        # ------------------------------------------------------------------
        hazards = [
            # (hazard_id, title, description, category, status, risk_level, likelihood, severity,
            #  mitigation, owner_id, identified_by, identified_at, created_at, updated_at)
            (
                "HAZ-SEED-001", "Battery performance degradation in cold weather",
                "LiPo batteries lose up to 30% capacity below 10°C, reducing endurance and increasing "
                "risk of unplanned low-battery returns during early-morning operations.",
                "environmental", "mitigated", "high", "possible", "major",
                "Implement pre-flight battery warming procedure; abort mission if temperature < 5°C; "
                "log battery temperature in flight records.",
                "u-maintenance", "u-safety", _iso(NOW - timedelta(days=160)),
                _iso(NOW - timedelta(days=160)), _iso(NOW - timedelta(days=160)),
            ),
            (
                "HAZ-SEED-002", "GPS multipath errors in urban canyon",
                "Nairobi's high-rise areas (Upper Hill, Westlands) cause GPS signal reflections and "
                "position drift, risking loss of position hold near buildings.",
                "technical", "identified", "high", "occasional", "major",
                "Restrict operations in urban canyon areas to VLOS only; require pilot to monitor "
                "HDOP values and abort if drift exceeds 5 m.",
                "u-flight-ops", "u-flight-ops", _iso(NOW - timedelta(days=145)),
                _iso(NOW - timedelta(days=145)), _iso(NOW - timedelta(days=145)),
            ),
            (
                "HAZ-SEED-003", "Unauthorized public access to launch sites",
                "Members of the public frequently enter launch/landing perimeters during operations "
                "in Industrial Area and Dagoretti, creating collision and distraction risk.",
                "security", "identified", "serious", "probable", "moderate",
                "Establish 50 m cordon with marshalling personnel; abort launch if perimeter breached.",
                "u-security", "u-ops", _iso(NOW - timedelta(days=130)),
                _iso(NOW - timedelta(days=130)), _iso(NOW - timedelta(days=130)),
            ),
            (
                "HAZ-SEED-004", "Propeller strike during hand launch",
                "Hand-launching fixed-wing aircraft (Ebee X) creates risk of propeller strike to "
                "launcher's hand or face.",
                "human_factor", "mitigated", "medium", "remote", "major",
                "Use mechanical launcher or assisted takeoff from cleared surface; mandatory gloves "
                "and face shield for hand launches.",
                "u-training", "u-chief-pilot", _iso(NOW - timedelta(days=110)),
                _iso(NOW - timedelta(days=110)), _iso(NOW - timedelta(days=110)),
            ),
            (
                "HAZ-SEED-005", "RF interference from broadcast transmitters",
                "Commercial FM/TV transmitters along Kangundo Road and Ngong Road cause intermittent "
                "RC downlink degradation.",
                "technical", "identified", "medium", "occasional", "minor",
                "Maintain 1 km separation from known high-power transmitters; monitor RSSI; abort if "
                "signal drops below threshold.",
                "u-flight-ops", "u-reporter", _iso(NOW - timedelta(days=100)),
                _iso(NOW - timedelta(days=100)), _iso(NOW - timedelta(days=100)),
            ),
            (
                "HAZ-SEED-006", "Manned aircraft conflict in Wilson Airport CTR",
                "Frequent helicopter and fixed-wing traffic in the Wilson Airport control zone creates "
                "collision exposure during survey flights.",
                "operational", "identified", "critical", "remote", "catastrophic",
                "Require ATC coordination for all CTR operations; file NOTAM; maintain continuous "
                "VLOS and scanning; descend immediately on traffic sighting.",
                "u-chief-pilot", "u-chief-pilot", _iso(NOW - timedelta(days=155)),
                _iso(NOW - timedelta(days=155)), _iso(NOW - timedelta(days=155)),
            ),
            (
                "HAZ-SEED-007", "Insufficient crew rest / fatigue",
                "Back-to-back mission scheduling without mandatory rest intervals increases pilot "
                "fatigue and error probability.",
                "human_factor", "identified", "medium", "occasional", "moderate",
                "Enforce FDTL limits (14 h duty, 12 h block, 10 h rest); log crew duty times in "
                "duty management module.",
                "u-ops", "u-accountable", _iso(NOW - timedelta(days=90)),
                _iso(NOW - timedelta(days=90)), _iso(NOW - timedelta(days=90)),
            ),
            (
                "HAZ-SEED-008", "Bird activity near water bodies",
                "High bird concentration near dams and ponds (e.g., Ngong Road forest dams) increases "
                "bird strike risk during low-altitude flights.",
                "environmental", "identified", "medium", "occasional", "moderate",
                "Avoid flying within 200 m of standing water during dawn/dusk peak bird activity; "
                "abort if bird flocks observed.",
                "u-safety", "u-reporter", _iso(NOW - timedelta(days=80)),
                _iso(NOW - timedelta(days=80)), _iso(NOW - timedelta(days=80)),
            ),
            (
                "HAZ-SEED-009", "Gimbal motor overload in high-temperature conditions",
                "Camera gimbal motors overheat during extended photography sessions above 30°C ambient.",
                "technical", "mitigated", "low", "remote", "minor",
                "Limit continuous gimbal operation to 20 minutes in temperatures > 30°C; allow "
                "cool-down periods between missions.",
                "u-maintenance", "u-maintenance", _iso(NOW - timedelta(days=60)),
                _iso(NOW - timedelta(days=60)), _iso(NOW - timedelta(days=60)),
            ),
            (
                "HAZ-SEED-010", "Incorrect battery capacity installed by ground crew",
                "Mismatched battery installation (lower-than-specified capacity) reduces mission "
                "endurance and can cause unplanned early landing.",
                "human_factor", "mitigated", "low", "unlikely", "minor",
                "Implement battery capacity verification checklist during pre-flight; label batteries "
                "with capacity and serial number.",
                "u-maintenance", "u-maintenance", _iso(NOW - timedelta(days=45)),
                _iso(NOW - timedelta(days=45)), _iso(NOW - timedelta(days=45)),
            ),
        ]
        for h in hazards:
            await db.execute(
                """INSERT INTO hazards
                   (hazard_id, title, description, category, status, risk_level, likelihood, severity,
                    mitigation, owner_id, identified_by, identified_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                h,
            )

        # ------------------------------------------------------------------
        # 3. RISK ASSESSMENTS (SMS 5x5 + OM flight risk tool)
        # ------------------------------------------------------------------
        risk_assessments = [
            # (assessment_id, hazard_ids (JSON list), occurrence_id, mission_id, title, description,
            #  likelihood, severity, risk_level, risk_model, exposure, risk_score,
            #  scrutiny_required, flight_cancelled, mitigation_measures, residual_risk,
            #  assessor_id, assessed_at, status, created_at, updated_at)
            (
                "RA-SEED-001", '["HAZ-SEED-001", "HAZ-SEED-005"]', None, None,
                "Cold-weather battery endurance risk for early-morning survey",
                "Assessed combined risk of battery capacity loss in temperatures below 10°C and RF "
                "interference near Kangundo Road transmitter for planned mapping mission.",
                "possible", "major", "high", "sms_5x5", None, 12, 0, 0,
                "Pre-warm batteries to > 15°C; carry spare warm batteries; maintain 1 km separation "
                "from transmitter; monitor RSSI continuously.",
                "Medium with mitigations; abort if battery temp < 5°C or RSSI degrades.",
                "u-safety", _iso(NOW - timedelta(days=155)), "approved",
                _iso(NOW - timedelta(days=155)), _iso(NOW - timedelta(days=155)),
            ),
            (
                "RA-SEED-002", '["HAZ-SEED-006"]', "OCC-SEED-008", None,
                "Wilson Airport CTR helicopter conflict risk",
                "Post-incident risk assessment following near-miss with police helicopter (OCC-SEED-008).",
                "remote", "catastrophic", "high", "sms_5x5", None, 5, 0, 0,
                "Mandatory ATC coordination and NOTAM filing for all CTR operations; continuous "
                "scanning; immediate descent on any traffic sighting.",
                "Low with ATC coordination; solo CTR flights prohibited without prior approval.",
                "u-chief-pilot", _iso(NOW - timedelta(days=152)), "approved",
                _iso(NOW - timedelta(days=152)), _iso(NOW - timedelta(days=152)),
            ),
            (
                "RA-SEED-003", '["HAZ-SEED-003"]', None, None,
                "Public perimeter breach risk at Industrial Area launch site",
                "Risk of unauthorized persons entering the 50 m safety perimeter during delivery "
                "mission launch/landing.",
                "probable", "moderate", "high", "sms_5x5", None, 12, 0, 0,
                "Two marshalling personnel with high-vis vests; radio abort command; physical cones "
                "and tape; abort launch if any person inside cordon.",
                "Medium; no launch until perimeter clear.",
                "u-security", _iso(NOW - timedelta(days=132)), "approved",
                _iso(NOW - timedelta(days=132)), _iso(NOW - timedelta(days=132)),
            ),
            (
                "RA-SEED-004", '["HAZ-SEED-002"]', None, None,
                "GPS multipath in Nairobi urban canyon survey",
                "Position drift risk during high-rise survey missions in Upper Hill and Westlands.",
                "occasional", "major", "high", "sms_5x5", None, 12, 0, 0,
                "VLOS-only operations in urban canyon; pilot monitors HDOP and aborts if drift > 5 m; "
                "pre-flight compass calibration.",
                "Medium; mission aborted if position hold cannot be maintained.",
                "u-flight-ops", _iso(NOW - timedelta(days=147)), "under_review",
                _iso(NOW - timedelta(days=147)), _iso(NOW - timedelta(days=147)),
            ),
            (
                "RA-SEED-005", '["HAZ-SEED-007"]', None, None,
                "Crew fatigue risk from back-to-back mission scheduling",
                "Fatigue-related error risk when pilots fly multiple missions without mandatory rest.",
                "occasional", "moderate", "medium", "sms_5x5", None, 9, 0, 0,
                "Enforce FDTL limits; duty-time logging; mandatory 10 h rest between duty periods.",
                "Low; monitored via duty-time tracking module.",
                "u-ops", _iso(NOW - timedelta(days=92)), "approved",
                _iso(NOW - timedelta(days=92)), _iso(NOW - timedelta(days=92)),
            ),
            (
                "RA-SEED-006", '["HAZ-SEED-001"]', None, None,
                "Low-temperature battery endurance assessment",
                "Standalone assessment of battery capacity loss below 10°C for winter morning ops.",
                "possible", "major", "high", "sms_5x5", None, 12, 0, 0,
                "Battery pre-warming; abort if ambient < 5°C; log temperatures in flight records.",
                "Medium; acceptable with pre-warm procedure.",
                "u-maintenance", _iso(NOW - timedelta(days=162)), "implemented",
                _iso(NOW - timedelta(days=162)), _iso(NOW - timedelta(days=162)),
            ),
            (
                "RA-SEED-007", '["HAZ-SEED-004", "HAZ-SEED-008"]', None, None,
                "Fixed-wing hand launch and bird strike combined risk",
                "Combined assessment for Ebee X fixed-wing operations near Ngong Road dams.",
                "remote", "moderate", "low", "sms_5x5", None, 3, 0, 0,
                "Mechanical launcher; gloves and face shield; avoid water bodies at dawn/dusk.",
                "Low; controls effective.",
                "u-chief-pilot", _iso(NOW - timedelta(days=112)), "implemented",
                _iso(NOW - timedelta(days=112)), _iso(NOW - timedelta(days=112)),
            ),
            (
                "RA-SEED-008", '["HAZ-SEED-009"]', None, None,
                "Gimbal overheating in high-temperature photography",
                "Risk of gimbal motor stall during extended photo sessions above 30°C.",
                "remote", "minor", "low", "sms_5x5", None, 2, 0, 0,
                "20-minute continuous operation limit; cool-down between missions; monitor motor temp.",
                "Low; acceptable.",
                "u-maintenance", _iso(NOW - timedelta(days=62)), "implemented",
                _iso(NOW - timedelta(days=62)), _iso(NOW - timedelta(days=62)),
            ),
            (
                "RA-SEED-009", '["HAZ-SEED-010"]', None, None,
                "Battery capacity mismatch risk",
                "Risk of ground crew installing lower-capacity batteries reducing mission endurance.",
                "unlikely", "minor", "low", "sms_5x5", None, 2, 0, 0,
                "Pre-flight battery capacity verification; capacity labels on all batteries.",
                "Low; checklist in place.",
                "u-maintenance", _iso(NOW - timedelta(days=47)), "implemented",
                _iso(NOW - timedelta(days=47)), _iso(NOW - timedelta(days=47)),
            ),
            (
                "RA-SEED-010", '["HAZ-SEED-005", "HAZ-SEED-002"]', None, None,
                "Combined RF interference and GPS drift in urban operations",
                "Joint risk of RC downlink degradation and GPS position drift during Westlands survey.",
                "occasional", "moderate", "medium", "sms_5x5", None, 9, 0, 0,
                "1 km separation from transmitters; VLOS only; HDOP monitoring; RSSI threshold abort.",
                "Medium; mission aborted if either parameter breached.",
                "u-flight-ops", _iso(NOW - timedelta(days=138)), "draft",
                _iso(NOW - timedelta(days=138)), _iso(NOW - timedelta(days=138)),
            ),
        ]
        for ra in risk_assessments:
            await db.execute(
                """INSERT INTO risk_assessments
                   (assessment_id, hazard_id, occurrence_id, mission_id, title, description,
                    likelihood, severity, risk_level, risk_model, exposure, risk_score,
                    scrutiny_required, flight_cancelled, mitigation_measures, residual_risk,
                    assessor_id, assessed_at, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ra[0], None, ra[2], ra[3], ra[4], ra[5], ra[6], ra[7], ra[8], ra[9], ra[10], ra[11],
                 ra[12], ra[13], ra[14], ra[15], ra[16], ra[17], ra[18], ra[19], ra[20]),
            )
            # Link hazards via junction table
            hazard_ids = json.loads(ra[1])
            for hid in hazard_ids:
                await db.execute(
                    "INSERT OR IGNORE INTO risk_assessment_hazards (assessment_id, hazard_id) VALUES (?, ?)",
                    (ra[0], hid),
                )
            # Keep legacy hazard_id column synced to first hazard
            if hazard_ids:
                await db.execute(
                    "UPDATE risk_assessments SET hazard_id = ? WHERE assessment_id = ?",
                    (hazard_ids[0], ra[0]),
                )

        # ------------------------------------------------------------------
        # 4. SAFETY ACTIONS (Corrective / preventive actions)
        # ------------------------------------------------------------------
        safety_actions = [
            # (action_id, occurrence_id, hazard_id, investigation_id, title, description,
            #  action_type, owner_id, due_date, status, created_at, updated_at)
            (
                "SA-SEED-001", "OCC-SEED-001", None, None,
                "Implement battery pre-warming procedure",
                "Create and publish pre-flight battery warming SOP for operations below 10°C ambient. "
                "Include temperature logging in flight records.",
                "corrective", "u-maintenance", _iso(NOW - timedelta(days=20)), "closed",
                _iso(NOW - timedelta(days=160)), _iso(NOW - timedelta(days=20)),
            ),
            (
                "SA-SEED-002", "OCC-SEED-008", None, "INV-SEED-003",
                "Establish CTR ATC coordination protocol",
                "Draft SOP for ATC coordination and NOTAM filing before any Wilson Airport CTR "
                "operation. Brief all remote pilots.",
                "corrective", "u-chief-pilot", _iso(NOW - timedelta(days=15)), "closed",
                _iso(NOW - timedelta(days=152)), _iso(NOW - timedelta(days=15)),
            ),
            (
                "SA-SEED-003", None, "HAZ-SEED-003", None,
                "Deploy perimeter marshalling kit",
                "Procure high-vis vests, cones, barrier tape, and radios for perimeter marshalling at "
                "Industrial Area and Dagoretti launch sites.",
                "preventive", "u-security", _iso(NOW - timedelta(days=10)), "in_progress",
                _iso(NOW - timedelta(days=130)), _iso(NOW - timedelta(days=25)),
            ),
            (
                "SA-SEED-004", None, "HAZ-SEED-002", None,
                "Urban canyon GPS operating limits",
                "Define maximum HDOP and position-drift thresholds; brief pilots on urban canyon "
                "VLOS-only restrictions.",
                "preventive", "u-flight-ops", _iso(NOW - timedelta(days=5)), "open",
                _iso(NOW - timedelta(days=147)), _iso(NOW - timedelta(days=147)),
            ),
            (
                "SA-SEED-005", "OCC-SEED-005", None, "INV-SEED-002",
                "Gimbal motor inspection and root cause",
                "Inspect AC-019 gimbal assembly; determine stall root cause; replace or repair as "
                "needed; update pre-flight gimbal check.",
                "corrective", "u-maintenance", _iso(NOW - timedelta(days=40)), "in_progress",
                _iso(NOW - timedelta(days=97)), _iso(NOW - timedelta(days=40)),
            ),
            (
                "SA-SEED-006", None, "HAZ-SEED-007", None,
                "FDTL duty-time logging enforcement",
                "Configure duty-time tracking module to flag approaching FDTL limits and block "
                "scheduling beyond 14 h duty / 12 h block.",
                "preventive", "u-ops", _iso(NOW - timedelta(days=30)), "open",
                _iso(NOW - timedelta(days=92)), _iso(NOW - timedelta(days=92)),
            ),
            (
                "SA-SEED-007", None, "HAZ-SEED-006", None,
                "ATC coordination briefing for all pilots",
                "Conduct safety briefing on CTR operations, ATC contact procedures, and NOTAM "
                "requirements for all remote pilots.",
                "preventive", "u-chief-pilot", _iso(NOW - timedelta(days=20)), "closed",
                _iso(NOW - timedelta(days=157)), _iso(NOW - timedelta(days=20)),
            ),
            (
                "SA-SEED-008", None, "HAZ-SEED-010", None,
                "Battery capacity labeling and verification",
                "Label all batteries with capacity rating; add capacity verification step to "
                "pre-flight checklist.",
                "preventive", "u-maintenance", _iso(NOW - timedelta(days=15)), "closed",
                _iso(NOW - timedelta(days=49)), _iso(NOW - timedelta(days=15)),
            ),
            (
                "SA-SEED-009", "OCC-SEED-004", None, None,
                "Public perimeter breach response review",
                "Review and update launch-site security procedures following unauthorized person "
                "incident; retrain marshalling staff.",
                "corrective", "u-security", _iso(NOW - timedelta(days=60)), "open",
                _iso(NOW - timedelta(days=80)), _iso(NOW - timedelta(days=80)),
            ),
            (
                "SA-SEED-010", None, "HAZ-SEED-005", None,
                "Transmitter proximity mapping",
                "Identify and map all high-power RF transmitters within 2 km of regular operating "
                "areas; publish to pilots as no-fly proximity zones.",
                "preventive", "u-flight-ops", _iso(NOW - timedelta(days=45)), "open",
                _iso(NOW - timedelta(days=102)), _iso(NOW - timedelta(days=102)),
            ),
        ]
        for sa in safety_actions:
            await db.execute(
                """INSERT INTO safety_actions
                   (action_id, occurrence_id, hazard_id, investigation_id, title, description,
                    action_type, owner_id, due_date, status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                sa,
            )

        # ------------------------------------------------------------------
        # 5. SAFETY KPIs
        # ------------------------------------------------------------------
        safety_kpis = [
            # (kpi_id, kpi_name, definition, target, period, current_value, evidence_source,
            #  trend, status, created_at, updated_at, created_by, updated_by)
            (
                "KPI-SEED-001", "MOR reporting rate",
                "Number of mandatory occurrence reports filed per month",
                "100%", "monthly", "100%", "Occurrence register",
                "stable", "on_track", _iso(NOW - timedelta(days=30)),
                _iso(NOW - timedelta(days=30)), "u-safety", "u-safety",
            ),
            (
                "KPI-SEED-002", "Average occurrence acknowledgment time",
                "Average hours from occurrence report to safety team acknowledgment",
                "<= 24 h", "monthly", "18 h", "Occurrence audit trail",
                "improving", "on_track", _iso(NOW - timedelta(days=30)),
                _iso(NOW - timedelta(days=30)), "u-safety", "u-safety",
            ),
            (
                "KPI-SEED-003", "Open safety actions",
                "Count of corrective/preventive actions not yet closed",
                "<= 5", "monthly", "3", "Safety action register",
                "improving", "on_track", _iso(NOW - timedelta(days=30)),
                _iso(NOW - timedelta(days=30)), "u-safety", "u-safety",
            ),
            (
                "KPI-SEED-004", "Hazard closure rate",
                "Percentage of identified hazards mitigated or closed within 30 days",
                ">= 80%", "quarterly", "85%", "Hazard register",
                "stable", "on_track", _iso(NOW - timedelta(days=90)),
                _iso(NOW - timedelta(days=90)), "u-safety", "u-safety",
            ),
            (
                "KPI-SEED-005", "Flight hours without incident",
                "Total UAS flight hours since last reportable occurrence",
                ">= 250 h", "quarterly", "312 h", "Mission flight logs",
                "improving", "on_track", _iso(NOW - timedelta(days=90)),
                _iso(NOW - timedelta(days=90)), "u-ops", "u-ops",
            ),
            (
                "KPI-SEED-006", "FDTL compliance rate",
                "Percentage of duty periods within 14 h duty / 12 h block limits",
                "100%", "monthly", "100%", "Duty-time tracking module",
                "stable", "on_track", _iso(NOW - timedelta(days=30)),
                _iso(NOW - timedelta(days=30)), "u-ops", "u-ops",
            ),
            (
                "KPI-SEED-007", "Risk assessment review timeliness",
                "Percentage of draft risk assessments reviewed within 7 days",
                ">= 90%", "monthly", "75%", "Risk assessment register",
                "declining", "at_risk", _iso(NOW - timedelta(days=30)),
                _iso(NOW - timedelta(days=30)), "u-quality", "u-quality",
            ),
            (
                "KPI-SEED-008", "MOR submission timeliness",
                "Percentage of MORs submitted to KCAA within regulatory deadline",
                "100%", "quarterly", "100%", "KCAA submission log",
                "stable", "on_track", _iso(NOW - timedelta(days=90)),
                _iso(NOW - timedelta(days=90)), "u-safety", "u-safety",
            ),
        ]
        for k in safety_kpis:
            await db.execute(
                """INSERT INTO safety_kpis
                   (kpi_id, kpi_name, definition, target, period, current_value, evidence_source,
                    trend, status, created_at, updated_at, created_by, updated_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                k,
            )

        # ------------------------------------------------------------------
        # 6. MISSIONS
        # ------------------------------------------------------------------
        aircraft_ids = ["AC-001", "AC-002", "AC-003", "AC-004", "AC-005", "AC-006",
                        "AC-007", "AC-008", "AC-009", "AC-010", "AC-019"]
        mission_types = ["survey", "inspection", "photography", "delivery", "training"]
        statuses = ["planned", "completed", "cancelled"]
        locations = [
            "Karen, Nairobi", "Westlands, Nairobi", "Industrial Area, Nairobi",
            "Kajiado, Magadi Road", "Konza Technopolis", "Wilson Airport",
            "Ngong Road forest", "Dagoretti Corner", "Eastleigh",
            "Thika Road, Nairobi", "Machakos Road"
        ]
        missions = []
        for i in range(1, 16):
            mission_id = f"MSN-SEED-{i:03d}"
            mtype = mission_types[(i - 1) % len(mission_types)]
            status = statuses[(i - 1) % len(statuses)]
            ac = aircraft_ids[(i - 1) % len(aircraft_ids)]
            planned = NOW - timedelta(days=170 - i * 10)
            pilot = "u-chief-pilot" if i % 2 == 1 else "u-flight-ops"
            ra_id = f"RA-SEED-{(i % 9) + 1:03d}" if i % 3 == 0 else None
            missions.append((
                mission_id,
                f"KFL {mtype.title()} mission {i}",
                f"Routine {mtype} operation over {locations[(i - 1) % len(locations)]}",
                mtype,
                status,
                "routine" if status != "cancelled" else "routine",
                _iso(planned),
                locations[(i - 1) % len(locations)],
                ac,
                "ROC-001",
                pilot,
                None,
                None,
                400,
                False,
                False,
                ra_id,
                None,
                None,
                None,
                _iso(planned),
                _iso(planned),
                pilot,
                pilot,
            ))
        for m in missions:
            await db.execute(
                """INSERT INTO missions
                   (mission_id, title, description, mission_type, status, priority,
                    planned_date, location, aircraft_id, roc_id, rpas_pilot_id,
                    visual_observer_id, dg_category, max_altitude_agl, bvlos_required,
                    night_required, risk_assessment_id, flight_plan_id, release_id,
                    post_flight_report_id, created_at, updated_at, created_by, updated_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                m,
            )

        await db.commit()
        print("Safety data seeded successfully")
        print(f"  occurrences: {len(occurrences)}")
        print(f"  hazards: {len(hazards)}")
        print(f"  risk_assessments: {len(risk_assessments)}")
        print(f"  safety_actions: {len(safety_actions)}")
        print(f"  safety_kpis: {len(safety_kpis)}")
        print(f"  missions: {len(missions)}")

        # Optional E2E credentials are injected by an isolated test harness only.
        # Never set shared passwords from a seed script by default.
        if e2e_password_hash:
            test_accounts = [
                "u-safety", "u-ops", "u-admin", "u-chief-pilot", "u-flight-ops",
                "u-maintenance", "u-quality", "u-reporter", "u-accountable", "u-lib",
            ]
            for uid in test_accounts:
                await db.execute(
                    "UPDATE users SET password_hash = ? WHERE user_id = ?",
                    (e2e_password_hash, uid),
                )
                await db.execute(
                    "UPDATE users SET onboarding_completed = 1 WHERE user_id = ?",
                    (uid,),
                )
            await db.commit()
            print(f"  E2E password configured for {len(test_accounts)} test accounts")
    except Exception as e:
        await db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(seed_safety_data())
