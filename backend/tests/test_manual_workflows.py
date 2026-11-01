import pytest


class TestManualWorkflowControls:
    def test_workflow_rules_registry_exposes_manual_clauses_and_hashes(self, client, admin_headers):
        resp = client.get("/api/p1/workflow-rules", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["fleet_master_count"] == 20
        assert len(data["opspec_authorized_registrations"]) == 7
        assert data["sources"]["DOC-007"]["approval_evidence_status"] == "pending_letter"
        assert data["sources"]["DOC-004"]["parent_section_ref"] == "Part D"
        assert data["sources"]["DOC-005"]["parent_section_ref"] == "Part B"
        assert "om_flight_26" in data["risk_models"]
        assert "sms_5x5" in data["risk_models"]

    def test_dg_shipment_enforces_division_6_2_and_blocks_patch_acceptance_bypass(self, client, admin_headers):
        # Out-of-scope DG class rejected under ROC-001 (Division 6.2 only)
        bad_class = client.post("/api/p1/dg-shipments", json={
            "dg_class": "Class 1.1 Explosives",
            "proper_shipping_name": "Unauthorized explosive",
            "un_number": "UN0004",
        }, headers=admin_headers)
        assert bad_class.status_code == 400
        assert "6.2" in bad_class.json()["detail"]

        # Valid Division 6.2 shipment starts pending
        ship = client.post("/api/p1/dg-shipments", json={
            "dg_class": "Division 6.2",
            "proper_shipping_name": "Biological substance, Category B",
            "un_number": "UN3373",
            "quantity": "1.5 kg",
            "packaging_type": "Triple packaging PI650",
        }, headers=admin_headers)
        assert ship.status_code == 201
        sid = ship.json()["shipment_id"]

        # Generic PATCH cannot mark shipment accepted without acceptance check
        bypass = client.patch(f"/api/p1/dg-shipments/{sid}", json={"status": "accepted"}, headers=admin_headers)
        assert bypass.status_code == 400

        # Failing Appendix 3 check (e.g. PIC weather not confirmed) holds/rejects shipment
        fail_check = client.post("/api/p1/dg-acceptance-checks", json={
            "shipment_id": sid,
            "packaging_ok": True,
            "marking_ok": True,
            "labeling_ok": True,
            "documentation_ok": True,
            "compatibility_ok": True,
            "triple_packaging_ok": True,
            "no_leakage_visual_ok": True,
            "pic_weather_confirmed": False,
            "crew_layers_unopened_confirmed": True,
        }, headers=admin_headers)
        assert fail_check.status_code == 201
        assert fail_check.json()["result"] == "rejected"

        # Passing all Appendix 3 checks accepts shipment
        pass_check = client.post("/api/p1/dg-acceptance-checks", json={
            "shipment_id": sid,
            "packaging_ok": True,
            "marking_ok": True,
            "labeling_ok": True,
            "documentation_ok": True,
            "compatibility_ok": True,
            "triple_packaging_ok": True,
            "no_leakage_visual_ok": True,
            "pic_weather_confirmed": True,
            "crew_layers_unopened_confirmed": True,
        }, headers=admin_headers)
        assert pass_check.status_code == 201
        assert pass_check.json()["result"] == "accepted"

        # Modifying quantity after acceptance invalidates acceptance back to pending
        modified = client.patch(f"/api/p1/dg-shipments/{sid}", json={"quantity": "3.0 kg"}, headers=admin_headers)
        assert modified.status_code == 200
        assert modified.json()["status"] == "pending"

    def test_security_incident_head_security_update_and_ssi_masking(self, client):
        sec_headers = {"X-Role": "head_security", "X-Actor": "u-security"}
        non_ssi_headers = {"X-Role": "flight_ops_officer", "X-Actor": "u-flight-ops"}

        inc = client.post("/api/p1/security-incidents", json={
            "title": "Perimeter breach attempt",
            "description": "Unauthorized access attempt near hangar",
            "incident_type": "physical_security",
            "severity": "high",
        }, headers=sec_headers)
        assert inc.status_code == 201
        iid = inc.json()["incident_id"]

        # Head of Security can update incident and record SSI investigation notes
        upd = client.patch(f"/api/p1/security-incidents/{iid}", json={
            "status": "investigating",
            "investigation_notes": "SSI: Suspect vehicle plate and guard deployment details",
        }, headers=sec_headers)
        assert upd.status_code == 200
        assert "SSI: Suspect vehicle" in upd.json()["investigation_notes"]

        # Non-SSI role sees masked investigation_notes (SEC-KFL §3.10)
        masked_list = client.get("/api/p1/security-incidents", headers=non_ssi_headers)
        assert masked_list.status_code == 200
        target = next(item for item in masked_list.json() if item["incident_id"] == iid)
        assert target["investigation_notes"] == "[SSI REDACTED]"

    def test_qms_car_level_deadlines_and_independent_auditor_closure(self, client, admin_headers):
        auditor_headers = {"X-Role": "head_quality", "X-Actor": "u-quality"}
        owner_headers = {"X-Role": "head_operations", "X-Actor": "u-ops"}

        # Level 1 finding auto-computes 7-day deadline when due_date omitted (QM-KFL §2.10.2)
        car = client.post("/api/p1/corrective-actions", json={
            "title": "Level 1 regulatory non-compliance",
            "description": "Missing training currency verification",
            "finding_level": "level_1",
            "owner_id": "u-ops",
        }, headers=auditor_headers)
        assert car.status_code == 201
        car_data = car.json()
        cid = car_data["car_id"]
        assert car_data["finding_level"] == "level_1"
        assert car_data["due_date"] is not None

        # Cannot verify before root_cause and corrective_action are recorded
        premature = client.post(
            f"/api/p1/corrective-actions/{cid}/verify?verification=Checked",
            headers=auditor_headers,
        )
        assert premature.status_code == 400

        # Owner records root cause and corrective action
        client.patch(f"/api/p1/corrective-actions/{cid}", json={
            "root_cause": "Manual tracking sheet was not updated after Part D recurrent course",
            "corrective_action": "Automated Part D recurrence check before mission assignment",
        }, headers=owner_headers)

        # Owner cannot self-verify their own CAR (SoD / auditor independence per QM-KFL §2.10.6)
        self_verify = client.post(
            f"/api/p1/corrective-actions/{cid}/verify?verification=Self+checked",
            headers=owner_headers,
        )
        assert self_verify.status_code == 403

        # Independent quality/auditor verifies and closes CAR
        verified = client.post(
            f"/api/p1/corrective-actions/{cid}/verify?verification=Satisfactory+CAP+implementation+verified",
            headers=auditor_headers,
        )
        assert verified.status_code == 200
        closed = client.patch(f"/api/p1/corrective-actions/{cid}", json={"status": "closed"}, headers=auditor_headers)
        assert closed.status_code == 200
        assert closed.json()["status"] == "closed"
