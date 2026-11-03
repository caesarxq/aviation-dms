import asyncio

from app.database import get_db


def _incident_counts():
    async def query_counts():
        db = await get_db()
        try:
            cursor = await db.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN lower(severity) IN ('critical', 'high') THEN 1 ELSE 0 END) AS critical_high,
                          SUM(CASE WHEN lower(status) IN ('open', 'reported', 'investigating') THEN 1 ELSE 0 END) AS open
                   FROM security_incidents"""
            )
            row = await cursor.fetchone()
            if row is None:
                return {"total": 0, "critical_high": 0, "open": 0}
            return {key: row[key] or 0 for key in ("total", "critical_high", "open")}
        finally:
            await db.close()

    return asyncio.run(query_counts())


def test_security_incident_summary_aggregates_all_rows_and_requires_authorization(client):
    headers = {"X-Role": "head_security", "X-Actor": "u-security"}
    baseline = _incident_counts()
    expected = {"total": 53, "critical_high": 3, "open": 51}

    incident_ids = []
    for index in range(53):
        severity = "critical" if index in (0, 2) else "high" if index == 1 else "minor"
        response = client.post("/api/p1/security-incidents", json={
            "title": f"Summary fixture incident {index}",
            "description": "Regression test incident",
            "severity": severity,
        }, headers=headers)
        assert response.status_code == 201, response.text
        incident_ids.append(response.json()["incident_id"])

    for index, status in enumerate(("open", "investigating", "reported", "resolved", "closed")):
        response = client.patch(
            f"/api/p1/security-incidents/{incident_ids[index]}",
            json={"status": status}, headers=headers,
        )
        assert response.status_code == 200, response.text

    summary = client.get("/api/p1/security-incidents/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert summary.json() == {key: baseline[key] + expected[key] for key in expected}

    authorized_reader = client.get(
        "/api/p1/security-incidents/summary",
        headers={"X-Role": "head_safety", "X-Actor": "u-safety"},
    )
    assert authorized_reader.status_code == 200, authorized_reader.text

    designated_security_reader = client.get(
        "/api/p1/security-incidents/summary",
        headers={"X-Role": "head_security", "X-Actor": "u-security"},
    )
    assert designated_security_reader.status_code == 200, designated_security_reader.text

    denied_safety_reader = client.get(
        "/api/p1/security-incidents/summary",
        headers={"X-Role": "head_quality", "X-Actor": "u-quality"},
    )
    assert denied_safety_reader.status_code == 403

    denied = client.get(
        "/api/p1/security-incidents/summary",
        headers={"X-Role": "records_custodian", "X-Actor": "u-records"},
    )
    assert denied.status_code == 403
