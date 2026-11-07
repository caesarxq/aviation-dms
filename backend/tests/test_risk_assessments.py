import asyncio

import pytest

from app.database import get_db


def _create_hazard(client, headers, title="Test hazard"):
    resp = client.post("/api/p1/hazards", json={
        "title": title,
        "description": "Test hazard for risk assessment linking",
        "category": "operational",
        "risk_level": "medium",
    }, headers=headers)
    assert resp.status_code == 201, f"Failed to create hazard: {resp.text}"
    return resp.json()["hazard_id"]


class TestRiskAssessments:
    def test_create_risk_assessment(self, client, safety_headers):
        h1 = _create_hazard(client, safety_headers, "Runway excursion hazard 1")
        h2 = _create_hazard(client, safety_headers, "Runway excursion hazard 2")
        resp = client.post("/api/p1/risk-assessments", json={
            "title": "Runway excursion risk",
            "description": "Assess risk of runway excursion during wet conditions",
            "hazard_ids": [h1, h2],
            "likelihood": "possible",
            "severity": "major",
            "risk_level": "high",
            "mitigation_measures": "Improved drainage and braking action monitoring",
            "residual_risk": "Low with mitigations in place"
        }, headers=safety_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Runway excursion risk"
        assert data["status"] == "draft"
        assert data["risk_level"] == "high"
        assert data["assessment_id"].startswith("RA")
        assert set(data["hazard_ids"]) == {h1, h2}

    def test_list_risk_assessments(self, client, safety_headers):
        resp = client.get("/api/p1/risk-assessments", headers=safety_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_computes_current_user_approval_by_canonical_assessor_identity(self, client, admin_headers):
        created = client.post("/api/p1/risk-assessments", json={
            "title": "Alias-aware approval action", "risk_level": "low",
        }, headers=admin_headers)
        assert created.status_code == 201, created.text
        assessment_id = created.json()["assessment_id"]
        legacy_admin_alias = f"legacy-admin-{assessment_id}"

        async def store_legacy_assessor_alias():
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO user_id_aliases (legacy_user_id, canonical_user_id, merged_at) VALUES (?, 'u-admin', datetime('now'))",
                    (legacy_admin_alias,),
                )
                await db.execute(
                    "UPDATE risk_assessments SET assessor_id = ? WHERE assessment_id = ?",
                    (legacy_admin_alias, assessment_id),
                )
                await db.commit()
            finally:
                await db.close()
        asyncio.run(store_legacy_assessor_alias())

        own_list = client.get("/api/p1/risk-assessments", headers=admin_headers)
        independent_list = client.get(
            "/api/p1/risk-assessments",
            headers={"X-Role": "head_safety", "X-Actor": "u-safety"},
        )
        assert own_list.status_code == independent_list.status_code == 200
        own_item = next(item for item in own_list.json() if item["assessment_id"] == assessment_id)
        independent_item = next(item for item in independent_list.json() if item["assessment_id"] == assessment_id)
        assert own_item["can_approve_for_current_user"] is False
        assert independent_item["can_approve_for_current_user"] is True

    def test_list_filters_by_risk_level_before_pagination(self, client, safety_headers):
        low = client.post("/api/p1/risk-assessments", json={
            "title": "Filtered low risk", "likelihood": "rare", "severity": "negligible", "risk_level": "low",
        }, headers=safety_headers).json()
        high = client.post("/api/p1/risk-assessments", json={
            "title": "Filtered high risk", "likelihood": "likely", "severity": "major", "risk_level": "high",
        }, headers=safety_headers).json()

        response = client.get("/api/p1/risk-assessments", params={
            "status": "draft", "risk_level": "low", "limit": 1, "offset": 0,
        }, headers=safety_headers)
        assert response.status_code == 200
        assert [item["assessment_id"] for item in response.json()] == [low["assessment_id"]]
        assert high["assessment_id"] not in {item["assessment_id"] for item in response.json()}

    @pytest.mark.parametrize("params", [
        {"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 1_000_001},
        {"status": "under_review"}, {"risk_level": "unrated"},
    ])
    def test_risk_assessment_list_rejects_unbounded_or_unknown_filters(self, client, safety_headers, params):
        response = client.get("/api/p1/risk-assessments", params=params, headers=safety_headers)
        assert response.status_code == 422

    def test_summary_counts_full_table_and_is_permission_gated(self, client, safety_headers):
        created = client.post("/api/p1/risk-assessments", json={
            "title": "Summary count risk", "likelihood": "rare", "severity": "negligible", "risk_level": "low",
        }, headers=safety_headers)
        assert created.status_code == 201, created.text

        summary = client.get("/api/p1/risk-assessments/summary", headers=safety_headers)
        assert summary.status_code == 200
        async def persisted_counts():
            db = await get_db()
            try:
                cursor = await db.execute(
                    """SELECT COUNT(*) AS total,
                              SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) AS draft,
                              SUM(CASE WHEN status = 'scrutiny_required' THEN 1 ELSE 0 END) AS scrutiny_required,
                              SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved,
                              SUM(CASE WHEN status = 'cancelled' OR flight_cancelled = 1 THEN 1 ELSE 0 END) AS cancelled,
                              SUM(CASE WHEN risk_level IN ('high', 'critical') THEN 1 ELSE 0 END) AS high_or_critical
                       FROM risk_assessments"""
                )
                row = await cursor.fetchone()
                assert row is not None
                return {key: (row[key] or 0) for key in summary.json()}
            finally:
                await db.close()

        assert summary.json() == asyncio.run(persisted_counts())
        assert client.get("/api/p1/risk-assessments/summary").status_code == 401

    def test_creation_for_mission_links_assessment_to_that_planned_mission(self, client, admin_headers):
        mission = client.post("/api/p1/missions", json={"title": "Risk-linked mission"}, headers=admin_headers)
        assert mission.status_code == 201, mission.text
        mission_id = mission.json()["mission_id"]

        assessment = client.post("/api/p1/risk-assessments", json={
            "title": "Mission risk", "mission_id": mission_id,
            "risk_model": "sms_5x5", "likelihood": "rare", "severity": "negligible", "risk_level": "low",
        }, headers=admin_headers)
        assert assessment.status_code == 201, assessment.text

        persisted_mission = client.get(f"/api/p1/missions/{mission_id}", headers=admin_headers)
        assert persisted_mission.status_code == 200
        assert persisted_mission.json()["risk_assessment_id"] == assessment.json()["assessment_id"]

    def test_creation_rejects_unknown_mission_link(self, client, admin_headers):
        response = client.post("/api/p1/risk-assessments", json={
            "title": "Unknown mission risk", "mission_id": "MSN-MISSING",
        }, headers=admin_headers)
        assert response.status_code == 404

    def test_approved_assessment_is_immutable_until_amendment_workflow_exists(self, client, admin_headers):
        created = client.post("/api/p1/risk-assessments", json={
            "title": "Approved immutable risk", "risk_level": "low",
        }, headers=admin_headers)
        assert created.status_code == 201, created.text
        assessment_id = created.json()["assessment_id"]
        reviewer_headers = {"X-Role": "head_safety", "X-Actor": "u-safety"}
        approved = client.post(f"/api/p1/risk-assessments/{assessment_id}/approve", headers=reviewer_headers)
        assert approved.status_code == 200, approved.text
        assert approved.json()["reviewed_at"]

        changed = client.patch(f"/api/p1/risk-assessments/{assessment_id}", json={
            "mitigation_measures": "Changed after approval",
        }, headers=admin_headers)
        assert changed.status_code == 409
        assert "approved" in changed.json()["detail"].lower()

        persisted = next(
            item for item in client.get("/api/p1/risk-assessments", headers=admin_headers).json()
            if item["assessment_id"] == assessment_id
        )
        assert persisted["mitigation_measures"] is None

    def test_assessor_cannot_approve_own_risk_assessment(self, client, safety_headers, admin_headers):
        created = client.post("/api/p1/risk-assessments", json={
            "title": "Independent review required", "risk_level": "low",
        }, headers=safety_headers)
        assert created.status_code == 201, created.text
        assessment_id = created.json()["assessment_id"]

        self_approval = client.post(f"/api/p1/risk-assessments/{assessment_id}/approve", headers=safety_headers)
        assert self_approval.status_code == 403
        independent_approval = client.post(f"/api/p1/risk-assessments/{assessment_id}/approve", headers=admin_headers)
        assert independent_approval.status_code == 200, independent_approval.text

    def test_risk_assessment_without_assessor_cannot_be_approved(self, client, safety_headers, admin_headers):
        created = client.post("/api/p1/risk-assessments", json={
            "title": "Missing assessor identity", "risk_level": "low",
        }, headers=safety_headers)
        assert created.status_code == 201, created.text
        assessment_id = created.json()["assessment_id"]

        async def remove_assessor_identity():
            db = await get_db()
            try:
                await db.execute("UPDATE risk_assessments SET assessor_id = '' WHERE assessment_id = ?", (assessment_id,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(remove_assessor_identity())

        listed = client.get("/api/p1/risk-assessments", headers=admin_headers)
        missing_assessor = next(item for item in listed.json() if item["assessment_id"] == assessment_id)
        assert missing_assessor["can_approve_for_current_user"] is False

        approval = client.post(f"/api/p1/risk-assessments/{assessment_id}/approve", headers=admin_headers)
        assert approval.status_code == 409
        assert "assessor" in approval.json()["detail"].lower()

    def test_filter_by_hazard_id(self, client, safety_headers):
        h = _create_hazard(client, safety_headers, "Filtered hazard")
        resp = client.post("/api/p1/risk-assessments", json={
            "title": "Filtered risk",
            "description": "Test hazard filter",
            "hazard_ids": [h],
            "risk_level": "medium"
        }, headers=safety_headers)
        assert resp.status_code == 201
        resp = client.get("/api/p1/risk-assessments", params={"hazard_id": h}, headers=safety_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(h in r["hazard_ids"] for r in data)

    def test_create_with_multiple_hazards(self, client, safety_headers):
        ids = [_create_hazard(client, safety_headers, f"Multi-hazard {i}") for i in range(1, 4)]
        resp = client.post("/api/p1/risk-assessments", json={
            "title": "Multi-hazard assessment",
            "description": "Assessment linked to multiple hazards",
            "hazard_ids": ids,
            "risk_level": "high"
        }, headers=safety_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert set(data["hazard_ids"]) == set(ids)

    def test_create_with_no_hazards(self, client, safety_headers):
        resp = client.post("/api/p1/risk-assessments", json={
            "title": "No-hazard assessment",
            "description": "Assessment without linked hazards",
            "risk_level": "low"
        }, headers=safety_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["hazard_ids"] == []

    def test_create_rejects_unknown_hazard_with_validation_error(self, client, safety_headers):
        response = client.post("/api/p1/risk-assessments", json={
            "title": "Unknown linked hazard", "hazard_ids": ["MISSING-HAZARD"],
        }, headers=safety_headers)
        assert response.status_code == 422

    def test_update_risk_assessment(self, client, safety_headers, admin_headers):
        resp = client.post("/api/p1/risk-assessments", json={
            "title": "Updatable risk",
            "description": "Test update",
            "risk_level": "medium"
        }, headers=safety_headers)
        assessment_id = resp.json()["assessment_id"]
        h = _create_hazard(client, safety_headers, "Updated hazard")
        # Content/hazard edits remain patchable; approval is a separate command.
        resp = client.patch(f"/api/p1/risk-assessments/{assessment_id}", json={
            "residual_risk": "Accepted residual risk", "hazard_ids": [h]
        }, headers=safety_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"
        assert resp.json()["residual_risk"] == "Accepted residual risk"
        assert resp.json()["hazard_ids"] == [h]
        approved = client.post(f"/api/p1/risk-assessments/{assessment_id}/approve", headers=admin_headers)
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

    @pytest.mark.parametrize("field,value", [
        ("risk_model", "unrecognized_model"),
        ("likelihood", "unknown"),
        ("severity", "extreme"),
        ("exposure", "unknown"),
    ])
    def test_unknown_risk_inputs_are_rejected(self, client, safety_headers, field, value):
        response = client.post("/api/p1/risk-assessments", json={"title": "Invalid risk input", field: value}, headers=safety_headers)
        assert response.status_code == 422

    def test_flight_risk_model_requires_explicit_exposure(self, client, safety_headers):
        response = client.post("/api/p1/risk-assessments", json={
            "title": "Missing exposure", "risk_model": "om_flight_26", "likelihood": "possible", "severity": "minor",
        }, headers=safety_headers)
        assert response.status_code == 422

    def test_invalid_hazard_replacement_rolls_back_entire_risk_update(self, client, safety_headers):
        created = client.post("/api/p1/risk-assessments", json={
            "title": "Atomic risk update", "description": "Original", "risk_level": "medium",
        }, headers=safety_headers).json()
        assessment_id = created["assessment_id"]
        response = client.patch(f"/api/p1/risk-assessments/{assessment_id}", json={
            "title": "Must roll back", "hazard_ids": ["MISSING-HAZARD"],
        }, headers=safety_headers)
        assert response.status_code == 422
        unchanged = next(
            item for item in client.get("/api/p1/risk-assessments", headers=safety_headers).json()
            if item["assessment_id"] == assessment_id
        )
        assert unchanged["title"] == "Atomic risk update"
        assert unchanged["hazard_ids"] == []

    def test_om_risk_score_is_derived_not_caller_supplied(self, client, safety_headers):
        response = client.post("/api/p1/risk-assessments", json={
            "title": "Derived flight risk", "risk_model": "om_flight_26", "likelihood": "probable",
            "severity": "major", "exposure": "frequent", "risk_score": 26,
        }, headers=safety_headers)
        assert response.status_code == 201
        assert response.json()["risk_score"] == 17
        assert response.json()["flight_cancelled"] is False

    def test_risk_assessment_status_and_score_are_not_patchable(self, client, safety_headers):
        created = client.post("/api/p1/risk-assessments", json={"title": "Protected risk"}, headers=safety_headers).json()
        response = client.patch(f"/api/p1/risk-assessments/{created['assessment_id']}", json={
            "status": "approved", "risk_score": 25, "risk_level": "low"
        }, headers=safety_headers)
        assert response.status_code == 422
        unchanged = next(item for item in client.get("/api/p1/risk-assessments", headers=safety_headers).json() if item["assessment_id"] == created["assessment_id"])
        assert unchanged["status"] == "draft"
        assert unchanged["risk_score"] == 6

    @pytest.mark.parametrize("role,actor", [
        ("system_admin", "admin"),
        ("accountable_manager", "u-accountable"),
        ("head_safety", "u-safety"),
        ("head_operations", "u-ops"),
        ("chief_pilot", "u-chief-pilot"),
    ])
    def test_risk_assessment_approval_permission_allows_existing_roles(self, client, safety_headers, admin_headers, role, actor):
        creator_headers = admin_headers if role == "head_safety" else safety_headers
        created = client.post("/api/p1/risk-assessments", json={"title": f"Approval by {role}"}, headers=creator_headers).json()
        approved = client.post(
            f"/api/p1/risk-assessments/{created['assessment_id']}/approve",
            headers={"X-Role": role, "X-Actor": actor},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

    @pytest.mark.parametrize("role,actor", [
        ("head_security", "u-security"),
        ("flight_ops_officer", "u-flight-ops"),
        ("head_quality", "u-quality"),
        ("librarian", "u-lib"),
    ])
    def test_risk_assessment_approval_permission_denies_other_roles(self, client, safety_headers, role, actor):
        created = client.post("/api/p1/risk-assessments", json={"title": f"Denied approval by {role}"}, headers=safety_headers).json()
        rejected = client.post(
            f"/api/p1/risk-assessments/{created['assessment_id']}/approve",
            headers={"X-Role": role, "X-Actor": actor},
        )
        assert rejected.status_code == 403, rejected.text
        current = client.get("/api/p1/risk-assessments", headers=safety_headers).json()
        assessment = next(item for item in current if item["assessment_id"] == created["assessment_id"])
        assert assessment["status"] == "draft"

    def test_nonexistent_risk_assessment_returns_404(self, client, safety_headers):
        resp = client.post("/api/p1/risk-assessments/NONEXISTENT/approve", headers=safety_headers)
        assert resp.status_code == 404

    def test_sms_5x5_rejects_contradictory_risk_level(self, client, safety_headers):
        resp = client.post("/api/p1/risk-assessments", json={
            "title": "Contradictory 5x5 rating",
            "risk_model": "sms_5x5",
            "likelihood": "frequent",
            "severity": "catastrophic",
            "risk_level": "low",
        }, headers=safety_headers)
        assert resp.status_code == 400

    def test_om_flight_risk_tool_thresholds_20_and_25(self, client, safety_headers):
        # Ignore the client score; probable x hazardous + frequent exposure calculates 21 (>20).
        r22 = client.post("/api/p1/risk-assessments", json={
            "title": "Unfamiliar route survey",
            "risk_model": "om_flight_26",
            "likelihood": "probable",
            "severity": "hazardous",
            "exposure": "frequent",
            "risk_score": 22,
        }, headers=safety_headers)
        assert r22.status_code == 201
        d22 = r22.json()
        assert d22["risk_model"] == "om_flight_26"
        assert d22["risk_score"] == 21
        assert d22["scrutiny_required"] is True
        assert d22["flight_cancelled"] is False

        # Score 26 (>25) mandates cancellation per OM §2.6
        r26 = client.post("/api/p1/risk-assessments", json={
            "title": "Severe weather unfamiliar area",
            "risk_model": "om_flight_26",
            "likelihood": "frequent",
            "severity": "catastrophic",
            "exposure": "rare",
            "risk_score": 26,
        }, headers=safety_headers)
        assert r26.status_code == 201
        d26 = r26.json()
        assert d26["risk_score"] == 26
        assert d26["flight_cancelled"] is True
        assert d26["status"] == "cancelled"
