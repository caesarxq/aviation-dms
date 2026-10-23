class TestAtomicProposalBatch:
    def _create_document_with_version(self, client, admin_headers, librarian_headers):
        document = client.post(
            "/api/p0/documents",
            json={"title": "Atomic Proposal Test", "doc_class": "procedure", "owner_id": "u-lib"},
            headers=admin_headers,
        )
        assert document.status_code == 201, document.text
        doc_id = document.json()["document_id"]
        version = client.post(
            "/api/p0/versions",
            json={
                "document_id": doc_id,
                "version_number": "01.00.00",
                "content": "<h2>4.2 Emergency Procedures</h2><p>The operator shall report.</p>",
            },
            headers=librarian_headers,
        )
        assert version.status_code == 201, version.text
        return doc_id, version.json()["version_id"]

    def test_preview_detects_section_targeted_atomic_change(self, client, admin_headers, librarian_headers):
        doc_id, version_id = self._create_document_with_version(client, admin_headers, librarian_headers)
        response = client.post(
            f"/api/p2/documents/{doc_id}/proposals/preview",
            json={"proposed_content": "<h2>4.2 Emergency Procedures</h2><p>The remote pilot shall report.</p>"},
            headers=librarian_headers,
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["base_version_id"] == version_id
        assert payload["change_count"] == 1
        change = payload["changes"][0]
        assert change["target_ref"].startswith("§4.2")
        assert change["original_text"] == "operator"
        assert change["proposed_text"] == "remote pilot"
        assert "<script" not in change["original_excerpt_html"].lower()

    def test_batch_creates_independent_proposals_with_focused_excerpts(self, client, admin_headers, librarian_headers):
        doc_id, _ = self._create_document_with_version(client, admin_headers, librarian_headers)
        response = client.post(
            f"/api/p2/documents/{doc_id}/proposals/batch",
            json={
                "proposed_content": "<h2>4.2 Emergency Procedures</h2><p>The remote pilot shall report.</p>",
                "severity": "major",
            },
            headers=librarian_headers,
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["created_count"] == 1
        proposal = payload["proposals"][0]
        assert proposal["proposal_id"].startswith("PROP-")
        assert proposal["change_set_id"].startswith("SET-")
        assert proposal["section_heading"] == "Emergency Procedures"
        assert proposal["original_excerpt_html"] != proposal["proposed_excerpt_html"]

        listed = client.get(f"/api/p2/documents/{doc_id}/proposals", headers=librarian_headers)
        assert listed.status_code == 200
        assert listed.json()[0]["section_heading"] == "Emergency Procedures"
