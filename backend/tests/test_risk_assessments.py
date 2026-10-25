import pytest


class TestRiskAssessments:
    def test_create_risk_assessment(self, client, safety_headers):
        resp = client.post("/api/p1/risk-assessments", json={
            "title": "Runway excursion risk",
            "description": "Assess risk of runway excursion during wet conditions",
            "hazard_id": "HAZ-001",
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

    def test_list_risk_assessments(self, client, safety_headers):
        resp = client.get("/api/p1/risk-assessments", headers=safety_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_by_hazard_id(self, client, safety_headers):
        resp = client.post("/api/p1/risk-assessments", json={
            "title": "Filtered risk",
            "description": "Test hazard filter",
            "hazard_id": "HAZ-FILTER",
            "risk_level": "medium"
        }, headers=safety_headers)
        assert resp.status_code == 201
        resp = client.get("/api/p1/risk-assessments", params={"hazard_id": "HAZ-FILTER"}, headers=safety_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(r["hazard_id"] == "HAZ-FILTER" for r in data)

    def test_update_risk_assessment(self, client, safety_headers):
        resp = client.post("/api/p1/risk-assessments", json={
            "title": "Updatable risk",
            "description": "Test update",
            "risk_level": "medium"
        }, headers=safety_headers)
        assessment_id = resp.json()["assessment_id"]
        resp = client.patch(f"/api/p1/risk-assessments/{assessment_id}", json={
            "status": "approved",
            "reviewed_by": "u-quality",
            "residual_risk": "Accepted residual risk"
        }, headers=safety_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["residual_risk"] == "Accepted residual risk"

    def test_nonexistent_risk_assessment_returns_404(self, client, safety_headers):
        resp = client.patch("/api/p1/risk-assessments/NONEXISTENT", json={"status": "approved"}, headers=safety_headers)
        assert resp.status_code == 404
