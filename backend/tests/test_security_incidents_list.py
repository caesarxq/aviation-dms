def _create_incident(client, headers, title, incident_type):
    response = client.post("/api/p1/security-incidents", json={
        "title": title,
        "description": f"Description for {title}",
        "incident_type": incident_type,
        "severity": "high",
    }, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["incident_id"]


def test_sensitive_reader_can_search_filter_and_paginate_incidents(client, admin_headers):
    matching_ids = {
        _create_incident(client, admin_headers, "Needle alpha", "access_breach"),
        _create_incident(client, admin_headers, "Needle beta", "access_breach"),
    }
    wrong_type_id = _create_incident(client, admin_headers, "Needle wrong type", "theft")
    wrong_status_id = _create_incident(client, admin_headers, "Needle wrong status", "access_breach")
    unrelated_id = _create_incident(client, admin_headers, "Unrelated", "access_breach")

    for incident_id in matching_ids | {wrong_type_id, unrelated_id}:
        update = client.patch(
            f"/api/p1/security-incidents/{incident_id}",
            json={"status": "investigating"}, headers=admin_headers,
        )
        assert update.status_code == 200, update.text

    params = {
        "search": "NEEDLE",
        "status": "investigating",
        "incident_type": "access_breach",
        "limit": 1,
    }
    first_page = client.get("/api/p1/security-incidents", params={**params, "offset": 0}, headers=admin_headers)
    second_page = client.get("/api/p1/security-incidents", params={**params, "offset": 1}, headers=admin_headers)
    third_page = client.get("/api/p1/security-incidents", params={**params, "offset": 2}, headers=admin_headers)
    assert first_page.status_code == second_page.status_code == third_page.status_code == 200
    first_id = first_page.json()[0]["incident_id"]
    second_id = second_page.json()[0]["incident_id"]
    assert {first_id, second_id} == matching_ids
    assert first_id != second_id
    assert third_page.json() == []

    for query in (
        {"limit": 101}, {"limit": 0}, {"offset": -1}, {"offset": 1_000_001},
        {"search": "x" * 101}, {"status": "s" * 41}, {"incident_type": "t" * 81},
    ):
        response = client.get("/api/p1/security-incidents", params=query, headers=admin_headers)
        assert response.status_code == 422, (query, response.text)


def test_non_sensitive_reader_gets_one_generic_shell_without_ids_counts_or_chronology(client, admin_headers):
    _create_incident(client, admin_headers, "Secret runway intrusion", "restricted_intrusion")
    closed_id = _create_incident(client, admin_headers, "Secret closed event", "restricted_intrusion")
    update = client.patch(
        f"/api/p1/security-incidents/{closed_id}",
        json={"status": "closed"}, headers=admin_headers,
    )
    assert update.status_code == 200, update.text

    headers = {"X-Role": "head_quality", "X-Actor": "u-quality"}
    ordinary = client.get("/api/p1/security-incidents", params={"limit": 100}, headers=headers)
    filtered = client.get("/api/p1/security-incidents", params={
        "search": "no matching incident", "status": "not-a-real-status",
        "incident_type": "not-a-real-type", "limit": 100,
    }, headers=headers)
    second_page = client.get("/api/p1/security-incidents", params={
        "search": "no matching incident", "status": "not-a-real-status",
        "incident_type": "not-a-real-type", "limit": 100, "offset": 1,
    }, headers=headers)
    assert ordinary.status_code == filtered.status_code == second_page.status_code == 200
    assert len(ordinary.json()) == len(filtered.json()) == 1
    assert ordinary.json() == filtered.json()
    assert second_page.json() == []

    shell = filtered.json()[0]
    for field in (
        "incident_id", "title", "description", "incident_type", "severity", "location",
        "reported_by", "reported_at", "status", "investigation_notes", "resolved_at",
        "resolved_by", "created_at", "updated_at",
    ):
        assert shell[field] == "[SSI REDACTED]"
