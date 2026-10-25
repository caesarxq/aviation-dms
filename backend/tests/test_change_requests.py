import pytest


class TestChangeRequests:
    def test_list_change_requests(self, client, admin_headers):
        resp = client.get("/api/p1/change-requests", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_and_submit_change_request(self, client, admin_headers):
        payload = {
            "document_id": "DOC-001",
            "title": "Update emergency procedures",
            "description": "Revise section 4.2 to reflect new battery requirements.",
            "change_type": "minor",
        }
        r = client.post("/api/p1/change-requests", json=payload, headers=admin_headers)
        assert r.status_code == 201
        cr = r.json()
        assert cr["cr_id"].startswith("CR-")
        assert cr["status"] == "open"
        assert cr["title"] == "Update emergency procedures"

        # Submit
        s = client.post(f"/api/p1/change-requests/{cr['cr_id']}/submit", headers=admin_headers)
        assert s.status_code == 200
        assert s.json()["status"] == "submitted"

    def test_review_change_request(self, client, admin_headers):
        # Librarian can create, head_quality can review
        payload = {
            "document_id": "DOC-006",
            "title": "Security manual update",
            "description": "Update access control section.",
            "change_type": "major",
        }
        r = client.post("/api/p1/change-requests", json=payload, headers=admin_headers)
        assert r.status_code == 201
        cr = r.json()

        # Requester cannot review their own CR (SOD)
        s = client.post(f"/api/p1/change-requests/{cr['cr_id']}/submit", headers=admin_headers)
        assert s.status_code == 200

        # Review as a different actor (simulate head_quality)
        quality_headers = {"X-Role": "head_quality", "X-Actor": "u-quality"}
        rv = client.post(f"/api/p1/change-requests/{cr['cr_id']}/review", headers=quality_headers)
        assert rv.status_code == 200
        assert rv.json()["status"] == "under_review"

    def test_approve_change_request(self, client, admin_headers):
        payload = {
            "document_id": "DOC-007",
            "title": "DG manual update",
            "description": "Update lithium battery guidance.",
            "change_type": "minor",
        }
        r = client.post("/api/p1/change-requests", json=payload, headers=admin_headers)
        assert r.status_code == 201
        cr = r.json()

        client.post(f"/api/p1/change-requests/{cr['cr_id']}/submit", headers=admin_headers)
        client.post(f"/api/p1/change-requests/{cr['cr_id']}/review", headers={"X-Role": "head_quality", "X-Actor": "u-quality"})

        # Approve as accountable_manager
        am_headers = {"X-Role": "accountable_manager", "X-Actor": "u-accountable"}
        ap = client.post(f"/api/p1/change-requests/{cr['cr_id']}/approve", headers=am_headers)
        assert ap.status_code == 200
        assert ap.json()["status"] == "approved"

    def test_reject_change_request(self, client, admin_headers):
        payload = {
            "document_id": "DOC-012",
            "title": "QMS manual update",
            "description": "Revise audit schedule.",
            "change_type": "minor",
        }
        r = client.post("/api/p1/change-requests", json=payload, headers=admin_headers)
        assert r.status_code == 201
        cr = r.json()

        client.post(f"/api/p1/change-requests/{cr['cr_id']}/submit", headers=admin_headers)
        client.post(f"/api/p1/change-requests/{cr['cr_id']}/review", headers={"X-Role": "head_quality", "X-Actor": "u-quality"})

        # Reject as accountable_manager
        am_headers = {"X-Role": "accountable_manager", "X-Actor": "u-accountable"}
        rj = client.post(
            f"/api/p1/change-requests/{cr['cr_id']}/reject",
            json={"rejection_reason": "Needs more justification."},
            headers=am_headers,
        )
        assert rj.status_code == 200
        assert rj.json()["status"] == "rejected"
        assert rj.json()["rejection_reason"] == "Needs more justification."

    def test_update_open_change_request(self, client, admin_headers):
        payload = {
            "document_id": "DOC-001",
            "title": "Original title",
            "description": "Original description.",
            "change_type": "minor",
        }
        r = client.post("/api/p1/change-requests", json=payload, headers=admin_headers)
        assert r.status_code == 201
        cr = r.json()

        upd = client.patch(
            f"/api/p1/change-requests/{cr['cr_id']}",
            json={"title": "Updated title"},
            headers=admin_headers,
        )
        assert upd.status_code == 200
        assert upd.json()["title"] == "Updated title"

    def test_cannot_submit_twice(self, client, admin_headers):
        payload = {
            "document_id": "DOC-001",
            "title": "Double submit test",
            "description": "Test.",
            "change_type": "minor",
        }
        r = client.post("/api/p1/change-requests", json=payload, headers=admin_headers)
        assert r.status_code == 201
        cr = r.json()

        client.post(f"/api/p1/change-requests/{cr['cr_id']}/submit", headers=admin_headers)
        s2 = client.post(f"/api/p1/change-requests/{cr['cr_id']}/submit", headers=admin_headers)
        assert s2.status_code == 400

    def test_sod_requester_cannot_approve(self, client, admin_headers):
        payload = {
            "document_id": "DOC-001",
            "title": "SOD test",
            "description": "Requester tries to approve.",
            "change_type": "minor",
        }
        r = client.post("/api/p1/change-requests", json=payload, headers=admin_headers)
        assert r.status_code == 201
        cr = r.json()

        client.post(f"/api/p1/change-requests/{cr['cr_id']}/submit", headers=admin_headers)
        client.post(f"/api/p1/change-requests/{cr['cr_id']}/review", headers={"X-Role": "head_quality", "X-Actor": "u-quality"})

        # Same actor (admin = requester) tries to approve -> 403
        ap = client.post(f"/api/p1/change-requests/{cr['cr_id']}/approve", headers=admin_headers)
        assert ap.status_code == 403

    def test_change_request_requires_auth(self, client):
        r = client.get("/api/p1/change-requests", headers={"X-Role": "unknown", "X-Actor": "nobody"})
        assert r.status_code in {401, 403}

    def test_review_comments(self, client, admin_headers):
        payload = {
            "document_id": "DOC-001",
            "title": "Comment test",
            "description": "Test comments.",
            "change_type": "minor",
        }
        r = client.post("/api/p1/change-requests", json=payload, headers=admin_headers)
        assert r.status_code == 201
        cr = r.json()

        # Add comment
        c = client.post(
            f"/api/p1/change-requests/{cr['cr_id']}/comments",
            json={"content": "Looks good to me."},
            headers=admin_headers,
        )
        assert c.status_code == 201

        # List comments
        lc = client.get(f"/api/p1/change-requests/{cr['cr_id']}/comments", headers=admin_headers)
        assert lc.status_code == 200
        assert len(lc.json()) == 1
        assert lc.json()[0]["content"] == "Looks good to me."
