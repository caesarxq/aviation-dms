import pytest


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

    def test_update_risk_assessment(self, client, safety_headers):
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
        approved = client.post(f"/api/p1/risk-assessments/{assessment_id}/approve", headers=safety_headers)
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

    def test_risk_approval_uses_dedicated_role_gated_command(self, client, safety_headers):
        created = client.post("/api/p1/risk-assessments", json={"title": "Approval path"}, headers=safety_headers).json()
        rejected = client.post(f"/api/p1/risk-assessments/{created['assessment_id']}/approve", headers={"X-Role": "flight_ops_officer", "X-Actor": "u-flight-ops"})
        assert rejected.status_code == 403, rejected.text
        approved = client.post(f"/api/p1/risk-assessments/{created['assessment_id']}/approve", headers=safety_headers)
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

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
        # Score 22 (>20) requires additional scrutiny
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
