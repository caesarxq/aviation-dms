"""M3 regression: document content responses support conditional requests (ETag).

Published manual HTML is multi-MB and immutable per version. The content endpoint
must emit an ETag + private cache directive and honor If-None-Match with a 304 so
repeat views do not re-transfer the whole payload. The ETag must change when the
content changes.
"""


def test_content_response_has_etag_and_private_cache(client, librarian_headers):
    resp = client.get("/api/p0/documents/DOC-001/content", headers=librarian_headers)
    assert resp.status_code == 200
    assert resp.headers.get("ETag"), "content response must carry an ETag"
    assert "private" in resp.headers.get("Cache-Control", "")


def test_matching_if_none_match_returns_304_without_body(client, librarian_headers):
    first = client.get("/api/p0/documents/DOC-001/content", headers=librarian_headers)
    etag = first.headers["ETag"]
    cond = client.get(
        "/api/p0/documents/DOC-001/content",
        headers={**librarian_headers, "If-None-Match": etag},
    )
    assert cond.status_code == 304
    assert cond.content == b""
    assert cond.headers.get("ETag") == etag


def test_stale_if_none_match_returns_full_content(client, librarian_headers):
    resp = client.get(
        "/api/p0/documents/DOC-001/content",
        headers={**librarian_headers, "If-None-Match": '"stale-etag-value"'},
    )
    assert resp.status_code == 200
    assert "content" in resp.json()


def test_etag_changes_when_content_changes(client, librarian_headers):
    before = client.get("/api/p0/documents/DOC-001/content?include_draft=true", headers=librarian_headers)
    etag_before = before.headers["ETag"]
    save = client.put(
        "/api/p0/documents/DOC-001/content",
        json={"content": "<p>Changed for ETag test</p>", "change_summary": "etag test"},
        headers=librarian_headers,
    )
    assert save.status_code == 200
    after = client.get("/api/p0/documents/DOC-001/content?include_draft=true", headers=librarian_headers)
    assert after.headers["ETag"] != etag_before