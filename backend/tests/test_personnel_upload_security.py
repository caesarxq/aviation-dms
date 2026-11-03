from pathlib import Path

import pytest

from app import p2_routes


@pytest.fixture

def upload_dir(tmp_path, monkeypatch):
    root = tmp_path / "private-uploads"
    monkeypatch.setattr(p2_routes, "UPLOAD_DIR", root)
    return root


def test_self_service_upload_uses_authenticated_person_and_safe_storage(client, safety_headers, upload_dir):
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("../../my-license.pdf", b"%PDF-1.7\ncredential", "application/pdf")},
        headers=safety_headers,
    )

    assert response.status_code == 200
    uploaded = response.json()
    path = Path(uploaded["file_path"]).resolve()
    assert uploaded["person_id"] == "u-safety"
    assert path.parent == upload_dir.resolve()
    assert path.name == uploaded["upload_id"] + ".pdf"
    assert path.name == Path(path.name).name
    assert path.read_bytes().startswith(b"%PDF-")
    listed = client.get("/api/p2/personnel/uploads/u-safety", headers=safety_headers)
    assert listed.status_code == 200
    assert uploaded["upload_id"] in {entry["upload_id"] for entry in listed.json()}


def test_self_service_cannot_list_another_person_uploads(client, reporter_headers):
    response = client.get("/api/p2/personnel/uploads/u-lib", headers=reporter_headers)

    assert response.status_code == 403


def test_self_service_cannot_upload_for_another_person(client, safety_headers, upload_dir):
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"person_id": "u-lib", "license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", b"%PDF-1.7\\ncredential", "application/pdf")},
        headers=safety_headers,
    )

    assert response.status_code == 403
    assert not list(upload_dir.glob("*"))


def test_self_service_upload_rejects_path_in_person_id(client, admin_headers, upload_dir):
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"person_id": "../outside", "license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", b"%PDF-1.7\ncredential", "application/pdf")},
        headers=admin_headers,
    )

    assert response.status_code in (400, 422)
    assert not (upload_dir.parent / "outside").exists()


def test_self_service_upload_rejects_absolute_person_id(client, admin_headers, upload_dir, tmp_path):
    outside = tmp_path / "outside"
    response = client.post(
        "/api/p2/personnel/uploads/file",
        data={"person_id": str(outside), "license_type": "pilot_license", "document_type": "license_copy"},
        files={"file": ("license.pdf", b"%PDF-1.7\ncredential", "application/pdf")},
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
            files={"file": ("credential.pdf", b"%PDF-1.7\\ncredential", "application/pdf")},
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
