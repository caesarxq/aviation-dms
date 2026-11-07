import asyncio
import hashlib
import sqlite3
from io import BytesIO
import stat
import uuid
from pathlib import Path

import aiosqlite
import pytest
from PIL import Image
from pypdf import PdfWriter

from app import p2_routes
from app import database


def _valid_pdf_bytes(title="Personnel credential"):
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": title})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _valid_image_bytes(image_format):
    output = BytesIO()
    Image.new("RGB", (2, 2), color=(40, 80, 120)).save(output, format=image_format)
    return output.getvalue()


@pytest.fixture

def upload_dir(tmp_path, monkeypatch):
    root = tmp_path / "private-uploads"
    monkeypatch.setattr(p2_routes, "UPLOAD_DIR", root)
    return root


def _create_upload_person():
    person_id = f"upload-person-{uuid.uuid4().hex}"
    async def create():
        db = await database.get_db()
        try:
            await db.execute(
                "INSERT INTO users (user_id, username, email, full_name, role, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))",
                (person_id, person_id, f"{person_id}@example.test", "Upload Test Person", "head_safety"),
            )
            await db.commit()
        finally:
            await db.close()
    asyncio.run(create())
    return person_id


def test_default_upload_directory_is_colocated_with_database_volume():
    assert p2_routes.UPLOAD_DIR.resolve() == (Path(database.DB_PATH).parent / "uploads").resolve()


def test_existing_personnel_upload_schema_gets_checksum_column(tmp_path, monkeypatch):
    legacy_db = tmp_path / "legacy-personnel-uploads.sqlite3"

    async def create_legacy_table():
        async with aiosqlite.connect(legacy_db) as connection:
            await connection.execute("""CREATE TABLE personnel_uploads (
                upload_id TEXT PRIMARY KEY, person_id TEXT NOT NULL, license_type TEXT NOT NULL,
                document_type TEXT NOT NULL, file_name TEXT NOT NULL, file_path TEXT NOT NULL,
                file_size INTEGER, content_type TEXT, verification_status TEXT NOT NULL DEFAULT 'pending',
                verified_by TEXT, verified_at TEXT, rejection_reason TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, created_by TEXT NOT NULL, updated_by TEXT NOT NULL
            )""")
            await connection.commit()

    asyncio.run(create_legacy_table())
    monkeypatch.setattr(database, "DB_PATH", str(legacy_db))
    asyncio.run(database.init_db())

    async def read_columns():
        db = await database.get_db()
        try:
            cursor = await db.execute("PRAGMA table_info(personnel_uploads)")
            return {row["name"] for row in await cursor.fetchall()}
        finally:
            await db.close()

    assert "file_sha256" in asyncio.run(read_columns())


def test_self_service_upload_uses_authenticated_person_and_safe_storage(client, safety_headers, upload_dir):
    content = _valid_pdf_bytes()
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("../../my-license.pdf", content, "application/pdf")},
        headers=safety_headers,
    )

    assert response.status_code == 200
    uploaded = response.json()
    path = (upload_dir / f"{uploaded['upload_id']}.pdf").resolve()
    assert uploaded["person_id"] == "u-safety/security"
    assert "file_path" not in uploaded
    assert uploaded["file_sha256"] == hashlib.sha256(content).hexdigest()
    assert path.parent == upload_dir.resolve()
    assert path.name == uploaded["upload_id"] + ".pdf"
    assert path.name == Path(path.name).name
    assert path.read_bytes().startswith(b"%PDF-")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(upload_dir.stat().st_mode) == 0o700
    listed = client.get("/api/p2/personnel/uploads/u-safety%2Fsecurity", headers=safety_headers)
    assert listed.status_code == 200
    entry = next(entry for entry in listed.json() if entry["upload_id"] == uploaded["upload_id"])
    assert "file_path" not in entry
    assert entry["download_url"].endswith(f"/{uploaded['upload_id']}/file")
    legacy_listed = client.get("/api/p2/personnel/uploads/u-safety", headers=safety_headers)
    assert legacy_listed.status_code == 200
    assert uploaded["upload_id"] in {row["upload_id"] for row in legacy_listed.json()}


def test_owner_can_download_upload_without_exposing_storage_path(client, safety_headers, upload_dir):
    content = _valid_pdf_bytes("Private credential")
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", content, "application/pdf")},
        headers=safety_headers,
    ).json()

    response = client.get(f"/api/p2/personnel/uploads/{uploaded['upload_id']}/file", headers=safety_headers)
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert (upload_dir / f"{uploaded['upload_id']}.pdf").exists()


@pytest.mark.parametrize("field,value", [("license_type", "unlisted_license"), ("document_type", "unlisted_document")])
def test_upload_rejects_unlisted_credential_metadata(client, safety_headers, upload_dir, field, value):
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy", field: value},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=safety_headers,
    )

    assert response.status_code == 422
    assert not list(upload_dir.glob("*"))


def test_owner_upload_history_is_paginated_and_status_filtered(client, admin_headers, upload_dir):
    person_id = _create_upload_person()
    uploaded = []
    for index in range(3):
        response = client.post(
            "/api/p2/personnel/uploads/file",
            data={"person_id": person_id, "license_type": "pilot_license", "document_type": "license_copy"},
            files={"file": (f"history-{index}.pdf", _valid_pdf_bytes(f"History {index}"), "application/pdf")},
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        uploaded.append(response.json())

    first = client.get(f"/api/p2/personnel/uploads/{person_id}", params={"limit": 2, "offset": 0}, headers=admin_headers)
    second = client.get(f"/api/p2/personnel/uploads/{person_id}", params={"limit": 2, "offset": 2}, headers=admin_headers)
    assert first.status_code == second.status_code == 200
    assert len(first.json()) == 2
    assert len(second.json()) == 1
    assert {row["upload_id"] for row in first.json() + second.json()} == {row["upload_id"] for row in uploaded}

    verified = client.patch(
        f"/api/p2/personnel/uploads/{uploaded[0]['upload_id']}/verify",
        json={"verification_status": "verified"}, headers={"X-Role": "head_operations", "X-Actor": "u-ops"},
    )
    assert verified.status_code == 200, verified.text
    only_verified = client.get(
        f"/api/p2/personnel/uploads/{person_id}", params={"status": "verified", "limit": 10, "offset": 0},
        headers=admin_headers,
    )
    assert only_verified.status_code == 200
    assert [row["upload_id"] for row in only_verified.json()] == [uploaded[0]["upload_id"]]
    invalid = client.get(f"/api/p2/personnel/uploads/{person_id}", params={"status": "unknown"}, headers=admin_headers)
    assert invalid.status_code == 422


def test_owner_history_includes_and_downloads_legacy_identity_alias_uploads(client, upload_dir):
    upload_id = f"UPL-ALIAS-{uuid.uuid4().hex[:10].upper()}"
    content = _valid_pdf_bytes("Legacy credential")
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.chmod(0o700)
    file_path = upload_dir / f"{upload_id}.pdf"
    file_path.write_bytes(content)
    file_path.chmod(0o600)
    async def insert_legacy_upload():
        db = await database.get_db()
        try:
            await db.execute(
                """INSERT INTO personnel_uploads
                   (upload_id, person_id, license_type, document_type, file_name, file_path, file_size, file_sha256,
                    content_type, verification_status, created_at, updated_at, created_by, updated_by)
                   VALUES (?, 'u-chief-pilot', 'pilot_license', 'license_copy', 'legacy.pdf',
                           ?, ?, ?, 'application/pdf', 'pending', datetime('now'),
                           datetime('now'), 'u-chief-pilot', 'u-chief-pilot')""",
                (upload_id, str(file_path), len(content), hashlib.sha256(content).hexdigest()),
            )
            await db.commit()
        finally:
            await db.close()
    asyncio.run(insert_legacy_upload())
    headers = {"X-Role": "chief_pilot", "X-Actor": "u-chief-pilot"}
    try:
        response = client.get("/api/p2/personnel/uploads/u-ops", headers=headers)
        assert response.status_code == 200, response.text
        assert upload_id in {row["upload_id"] for row in response.json()}
        queue = client.get("/api/p2/personnel/uploads", params={"status": "pending", "limit": 100, "offset": 0}, headers=headers)
        assert queue.status_code == 200, queue.text
        entry = next(row for row in queue.json() if row["upload_id"] == upload_id)
        assert entry["can_review"] is False
        download = client.get(f"/api/p2/personnel/uploads/{upload_id}/file", headers=headers)
        assert download.status_code == 200, download.text
        assert download.content == content
    finally:
        async def delete_legacy_upload():
            db = await database.get_db()
            try:
                await db.execute("DELETE FROM personnel_uploads WHERE upload_id = ?", (upload_id,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(delete_legacy_upload())


def test_personnel_manager_can_list_pending_verification_queue(client, safety_headers, admin_headers):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=safety_headers,
    ).json()

    queue = client.get("/api/p2/personnel/uploads", params={"status": "pending", "limit": 50, "offset": 0}, headers=admin_headers)
    assert queue.status_code == 200
    item = next(row for row in queue.json() if row["upload_id"] == uploaded["upload_id"])
    assert item["person_id"] == "u-safety/security"
    assert item["verification_status"] == "pending"
    assert item["can_review"] is True
    assert "file_path" not in item


def test_read_only_personnel_queue_does_not_offer_review_action(client, safety_headers):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("readonly-queue.pdf", _valid_pdf_bytes("Read-only queue"), "application/pdf")},
        headers=safety_headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    reviewer_headers = {"X-Role": "flight_ops_officer", "X-Actor": "u-flight-ops"}

    queue = client.get("/api/p2/personnel/uploads", params={"status": "pending"}, headers=reviewer_headers)
    assert queue.status_code == 200, queue.text
    item = next(row for row in queue.json() if row["upload_id"] == uploaded.json()["upload_id"])
    assert item["can_review"] is False


def test_credential_subject_is_not_marked_reviewable_when_not_the_uploader(client):
    upload_id = f"UPL-SUBJECT-{uuid.uuid4().hex[:10].upper()}"

    async def insert_upload_for_subject():
        db = await database.get_db()
        try:
            await db.execute(
                """INSERT INTO personnel_uploads
                   (upload_id, person_id, license_type, document_type, file_name, file_path, file_size,
                    content_type, verification_status, created_at, updated_at, created_by, updated_by)
                   VALUES (?, 'u-ops', 'pilot_license', 'license_copy', 'subject.pdf',
                           'test-only-path', 1, 'application/pdf', 'pending', datetime('now'),
                           datetime('now'), 'u-admin', 'u-admin')""",
                (upload_id,),
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(insert_upload_for_subject())
    try:
        queue = client.get(
            "/api/p2/personnel/uploads",
            params={"status": "pending", "limit": 100, "offset": 0},
            headers={"X-Role": "head_training", "X-Actor": "u-training"},
        )
        assert queue.status_code == 200, queue.text
        item = next(row for row in queue.json() if row["upload_id"] == upload_id)
        assert item["can_review"] is False
    finally:
        async def delete_upload():
            db = await database.get_db()
            try:
                await db.execute("DELETE FROM personnel_uploads WHERE upload_id = ?", (upload_id,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(delete_upload())


def test_upload_with_blank_uploader_is_not_reviewable(client, safety_headers, admin_headers, upload_dir):
    uploaded_response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("identity.pdf", _valid_pdf_bytes("Review identity"), "application/pdf")},
        headers=safety_headers,
    )
    assert uploaded_response.status_code == 200, uploaded_response.text
    upload_id = uploaded_response.json()["upload_id"]

    try:
        async def clear_identity():
            db = await database.get_db()
            try:
                await db.execute("UPDATE personnel_uploads SET created_by = '' WHERE upload_id = ?", (upload_id,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(clear_identity())

        queue = client.get("/api/p2/personnel/uploads", params={"status": "pending"}, headers=admin_headers)
        assert queue.status_code == 200, queue.text
        item = next(row for row in queue.json() if row["upload_id"] == upload_id)
        assert item["can_review"] is False
        review = client.patch(
            f"/api/p2/personnel/uploads/{upload_id}/verify",
            json={"verification_status": "verified"},
            headers=admin_headers,
        )
        assert review.status_code == 409
        assert "identity" in review.json()["detail"].lower()
    finally:
        async def delete_upload():
            db = await database.get_db()
            try:
                await db.execute("DELETE FROM personnel_uploads WHERE upload_id = ?", (upload_id,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(delete_upload())


def test_upload_with_blank_subject_is_not_reviewable(client, safety_headers, admin_headers, upload_dir):
    uploaded_response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("subject.pdf", _valid_pdf_bytes("Missing subject"), "application/pdf")},
        headers=safety_headers,
    )
    assert uploaded_response.status_code == 200, uploaded_response.text
    upload_id = uploaded_response.json()["upload_id"]
    try:
        with sqlite3.connect(database.DB_PATH) as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("UPDATE personnel_uploads SET person_id = '' WHERE upload_id = ?", (upload_id,))

        queue = client.get("/api/p2/personnel/uploads", params={"status": "pending"}, headers=admin_headers)
        assert queue.status_code == 200, queue.text
        item = next(row for row in queue.json() if row["upload_id"] == upload_id)
        assert item["can_review"] is False
        review = client.patch(
            f"/api/p2/personnel/uploads/{upload_id}/verify",
            json={"verification_status": "verified"},
            headers=admin_headers,
        )
        assert review.status_code == 409
        assert "identity" in review.json()["detail"].lower()
    finally:
        async def delete_upload():
            db = await database.get_db()
            try:
                await db.execute("DELETE FROM personnel_uploads WHERE upload_id = ?", (upload_id,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(delete_upload())


def test_upload_rejects_malformed_pdf_with_valid_signature_prefix(client, safety_headers, upload_dir):
    malformed = b"%PDF-1.7\nnot actually a PDF"
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("bad.pdf", malformed, "application/pdf")},
        headers=safety_headers,
    )

    assert response.status_code == 415
    assert not list(upload_dir.glob("*"))


def test_upload_rejects_malformed_png_with_valid_signature_prefix(client, safety_headers, upload_dir):
    malformed = b"\x89PNG\r\n\x1a\nnot actually a PNG"
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("bad.png", malformed, "image/png")},
        headers=safety_headers,
    )

    assert response.status_code == 415
    assert not list(upload_dir.glob("*"))


@pytest.mark.parametrize(("extension", "image_format", "content_type"), [
    (".png", "PNG", "image/png"),
    (".jpg", "JPEG", "image/jpeg"),
    (".jpeg", "JPEG", "image/jpeg"),
])
def test_upload_accepts_structurally_valid_images(client, safety_headers, extension, image_format, content_type):
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": (f"credential{extension}", _valid_image_bytes(image_format), content_type)},
        headers=safety_headers,
    )

    assert response.status_code == 200, response.text


def test_download_serves_the_validated_snapshot_if_storage_path_is_replaced(client, safety_headers, admin_headers, upload_dir, monkeypatch):
    content = _valid_pdf_bytes("Original credential")
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", content, "application/pdf")},
        headers=safety_headers,
    ).json()
    stored_path = upload_dir / f"{uploaded['upload_id']}.pdf"
    original_resolve = p2_routes._resolve_personnel_upload_file

    def resolve_then_replace(row):
        snapshot = original_resolve(row)
        stored_path.write_bytes(_valid_pdf_bytes("Replacement credential"))
        return snapshot

    monkeypatch.setattr(p2_routes, "_resolve_personnel_upload_file", resolve_then_replace)
    response = client.get(f"/api/p2/personnel/uploads/{uploaded['upload_id']}/file", headers=admin_headers)

    assert response.status_code == 200
    assert response.content == content


def test_upload_verification_requires_independent_review_and_rejection_reason(client, admin_headers):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=admin_headers,
    ).json()
    upload_id = uploaded["upload_id"]

    self_verify = client.patch(f"/api/p2/personnel/uploads/{upload_id}/verify", json={"verification_status": "verified"}, headers=admin_headers)
    assert self_verify.status_code == 403

    reviewer_headers = {"X-Role": "head_operations", "X-Actor": "u-ops"}
    missing_reason = client.patch(f"/api/p2/personnel/uploads/{upload_id}/verify", json={"verification_status": "rejected"}, headers=reviewer_headers)
    assert missing_reason.status_code == 422
    rejected = client.patch(f"/api/p2/personnel/uploads/{upload_id}/verify", json={
        "verification_status": "rejected", "rejection_reason": "Image is not legible",
    }, headers=reviewer_headers)
    assert rejected.status_code == 200
    assert rejected.json()["verification_status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Image is not legible"
    assert rejected.json()["verified_by"] is None
    assert rejected.json()["verified_at"] is None
    assert rejected.json()["updated_by"] == "u-ops"

    second_decision = client.patch(f"/api/p2/personnel/uploads/{upload_id}/verify", json={"verification_status": "verified"}, headers=reviewer_headers)
    assert second_decision.status_code == 409


def test_credential_subject_cannot_verify_upload_created_by_another_operator(client, admin_headers):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"person_id": "u-ops", "license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=admin_headers,
    )
    assert uploaded.status_code == 200, uploaded.text

    response = client.patch(
        f"/api/p2/personnel/uploads/{uploaded.json()['upload_id']}/verify",
        json={"verification_status": "verified"},
        headers={"X-Role": "head_operations", "X-Actor": "u-ops"},
    )

    assert response.status_code == 403


def test_verified_upload_sets_only_verification_metadata(client, admin_headers):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("verified-license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=admin_headers,
    ).json()

    verified = client.patch(
        f"/api/p2/personnel/uploads/{uploaded['upload_id']}/verify",
        json={"verification_status": "verified"},
        headers={"X-Role": "head_operations", "X-Actor": "u-ops"},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified_by"] == "u-ops"
    assert verified.json()["verified_at"]
    assert verified.json()["rejection_reason"] is None


def test_tampered_upload_cannot_be_downloaded_or_verified(client, safety_headers, admin_headers, upload_dir):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=safety_headers,
    ).json()
    stored = upload_dir / f"{uploaded['upload_id']}.pdf"
    stored.write_bytes(b"%PDF-1.7\ntampered!     ")

    download = client.get(f"/api/p2/personnel/uploads/{uploaded['upload_id']}/file", headers=admin_headers)
    assert download.status_code == 409
    verify = client.patch(f"/api/p2/personnel/uploads/{uploaded['upload_id']}/verify", json={"verification_status": "verified"}, headers=admin_headers)
    assert verify.status_code == 409


def test_verification_rejects_legacy_pdf_with_only_a_valid_signature_prefix(client, admin_headers, upload_dir):
    upload_id = f"UPL-MALFORMED-{uuid.uuid4().hex[:10].upper()}"
    content = b"%PDF-1.7\\nnot actually a PDF"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.chmod(0o700)
    file_path = upload_dir / f"{upload_id}.pdf"
    file_path.write_bytes(content)
    file_path.chmod(0o600)

    async def insert_legacy_upload():
        db = await database.get_db()
        try:
            await db.execute(
                """INSERT INTO personnel_uploads
                   (upload_id, person_id, license_type, document_type, file_name, file_path, file_size, file_sha256,
                    content_type, verification_status, created_at, updated_at, created_by, updated_by)
                   VALUES (?, 'u-safety/security', 'pilot_license', 'license_copy', 'malformed.pdf', ?, ?, ?,
                           'application/pdf', 'pending', datetime('now'), datetime('now'), 'u-safety', 'u-safety')""",
                (upload_id, str(file_path), len(content), hashlib.sha256(content).hexdigest()),
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(insert_legacy_upload())
    response = client.patch(
        f"/api/p2/personnel/uploads/{upload_id}/verify",
        json={"verification_status": "verified"},
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_legacy_upload_without_checksum_cannot_be_downloaded_or_verified(client, safety_headers, admin_headers):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("legacy.pdf", _valid_pdf_bytes("Legacy credential"), "application/pdf")},
        headers=safety_headers,
    ).json()

    async def clear_digest():
        db = await database.get_db()
        try:
            await db.execute("UPDATE personnel_uploads SET file_sha256 = NULL WHERE upload_id = ?", (uploaded["upload_id"],))
            await db.commit()
        finally:
            await db.close()
    asyncio.run(clear_digest())

    download = client.get(f"/api/p2/personnel/uploads/{uploaded['upload_id']}/file", headers=admin_headers)
    verify = client.patch(
        f"/api/p2/personnel/uploads/{uploaded['upload_id']}/verify",
        json={"verification_status": "verified"}, headers=admin_headers,
    )
    assert download.status_code == 409
    assert verify.status_code == 409


def test_upload_download_rejects_path_escape_and_symlink(client, safety_headers, admin_headers, upload_dir, tmp_path):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=safety_headers,
    ).json()
    upload_id = uploaded["upload_id"]
    stored = upload_dir / f"{upload_id}.pdf"
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.7\nprivate")

    async def set_file_path(path: Path):
        db = await database.get_db()
        try:
            await db.execute("UPDATE personnel_uploads SET file_path = ? WHERE upload_id = ?", (str(path), upload_id))
            await db.commit()
        finally:
            await db.close()

    asyncio.run(set_file_path(outside))
    escaped = client.get(f"/api/p2/personnel/uploads/{upload_id}/file", headers=admin_headers)
    assert escaped.status_code == 409

    awaitable = asyncio.run(set_file_path(stored))
    assert awaitable is None
    stored.unlink()
    stored.symlink_to(outside)
    symlinked = client.get(f"/api/p2/personnel/uploads/{upload_id}/file", headers=admin_headers)
    assert symlinked.status_code == 409


def test_upload_download_rejects_a_symlinked_storage_directory(client, safety_headers, admin_headers, upload_dir):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=safety_headers,
    ).json()
    moved_root = upload_dir.with_name("real-private-uploads")
    upload_dir.rename(moved_root)
    upload_dir.symlink_to(moved_root, target_is_directory=True)

    response = client.get(f"/api/p2/personnel/uploads/{uploaded['upload_id']}/file", headers=admin_headers)

    assert response.status_code == 409


def test_download_uses_open_directory_after_parent_path_is_swapped_for_symlink(client, safety_headers, admin_headers, upload_dir, monkeypatch):
    content = _valid_pdf_bytes("Original directory content")
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", content, "application/pdf")},
        headers=safety_headers,
    ).json()
    expected_filename = f"{uploaded['upload_id']}.pdf"
    original_root = upload_dir.with_name("original-private-uploads")
    attacker_root = upload_dir.with_name("attacker-uploads")
    attacker_root.mkdir(mode=0o700)
    (attacker_root / expected_filename).write_bytes(_valid_pdf_bytes("Replacement directory content"))
    real_open = p2_routes.os.open
    swapped = False

    def swap_before_leaf_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == expected_filename and kwargs.get("dir_fd") is not None and not swapped:
            upload_dir.rename(original_root)
            upload_dir.symlink_to(attacker_root, target_is_directory=True)
            swapped = True
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(p2_routes.os, "open", swap_before_leaf_open)
    response = client.get(f"/api/p2/personnel/uploads/{uploaded['upload_id']}/file", headers=admin_headers)

    assert swapped
    assert response.status_code == 200
    assert response.content == content


def test_nonowner_without_personnel_read_cannot_download(client, safety_headers, reporter_headers, upload_dir):
    uploaded = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=safety_headers,
    ).json()
    response = client.get(f"/api/p2/personnel/uploads/{uploaded['upload_id']}/file", headers=reporter_headers)
    assert response.status_code == 403


def test_self_service_cannot_list_another_person_uploads(client, reporter_headers):
    response = client.get("/api/p2/personnel/uploads/u-lib", headers=reporter_headers)

    assert response.status_code == 403


def test_self_service_cannot_upload_for_another_person(client, safety_headers, upload_dir):
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"person_id": "u-lib", "license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=safety_headers,
    )

    assert response.status_code == 403
    assert not list(upload_dir.glob("*"))


def test_self_service_upload_rejects_path_in_person_id(client, admin_headers, upload_dir):
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"person_id": "../outside", "license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=admin_headers,
    )

    assert response.status_code in (400, 422)
    assert not (upload_dir.parent / "outside").exists()


def test_self_service_upload_rejects_absolute_person_id(client, admin_headers, upload_dir, tmp_path):
    outside = tmp_path / "outside"
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"person_id": str(outside), "license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", _valid_pdf_bytes(), "application/pdf")},
        headers=admin_headers,
    )

    assert response.status_code in (400, 422)
    assert not outside.exists()


def test_oversized_personnel_upload_is_rejected_without_saving(client, safety_headers, upload_dir, monkeypatch):
    monkeypatch.setattr(p2_routes, "MAX_PERSONNEL_UPLOAD_BYTES", 8)

    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", b"%PDF-1.7 credential too large", "application/pdf")},
        headers=safety_headers,
    )

    assert response.status_code == 413
    assert not list(upload_dir.glob("*"))


def test_oversized_streaming_request_is_rejected(client, safety_headers, upload_dir, monkeypatch):
    monkeypatch.setattr(p2_routes, "MAX_PERSONNEL_UPLOAD_BYTES", 8)

    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", b"%PDF-1.7 " + b"x" * (70 * 1024), "application/pdf")},
        headers=safety_headers,
    )

    assert response.status_code == 413
    assert not list(upload_dir.glob("*"))


def test_personnel_upload_metadata_cannot_supply_arbitrary_file_path(client, safety_headers):
    response = client.post(
        "/api/p2/personnel/uploads",
        json={
            "person_id": "u-safety",
            "license_type": "pilot_license",
            "document_type": "license_copy",
            "file_name": "credential.pdf",
            "file_path": "/etc/passwd",
        },
        headers=safety_headers,
    )

    assert response.status_code in (400, 415, 422)


def test_personnel_upload_rejects_mime_signature_mismatch(client, safety_headers, upload_dir):
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("credential.pdf", b"not a pdf", "application/pdf")},
        headers=safety_headers,
    )

    assert response.status_code == 415
    assert not list(upload_dir.glob("*"))


def test_upload_failure_rolls_back_database_row_and_file(client, safety_headers, upload_dir, monkeypatch):
    before = client.get("/api/p2/personnel/uploads/u-safety", headers=safety_headers)
    assert before.status_code == 200
    existing_ids = {entry["upload_id"] for entry in before.json()}
    async def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated audit store failure")

    monkeypatch.setattr(p2_routes, "log_audit_event", fail_audit)
    with pytest.raises(RuntimeError, match="simulated audit store failure"):
        client.post(
            "/api/p2/personnel/uploads/file",
            data={"license_type": "pilot_license", "document_type": "license_copy"},
            files={"file": ("credential.pdf", _valid_pdf_bytes(), "application/pdf")},
            headers=safety_headers,
        )

    assert not list(upload_dir.glob("*"))
    listed = client.get("/api/p2/personnel/uploads/u-safety", headers=safety_headers)
    assert listed.status_code == 200
    assert {entry["upload_id"] for entry in listed.json()} == existing_ids


def test_staff_can_list_other_person_uploads_with_read_permission(client, admin_headers):
    response = client.get("/api/p2/personnel/uploads/u-lib", headers=admin_headers)

    assert response.status_code == 200


def test_staff_verify_action_remains_permission_gated(client, safety_headers):
    response = client.patch(
        "/api/p2/personnel/uploads/not-a-real-upload/verify",
        json={"verification_status": "verified"},
        headers=safety_headers,
    )

    assert response.status_code == 403
