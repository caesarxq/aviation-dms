from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.upload_validation_service import app


def _valid_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_isolated_validator_health_and_valid_pdf():
    client = TestClient(app)

    health = client.get("/health")
    response = client.post(
        "/validate?extension=.pdf&max_bytes=1048576&max_image_pixels=40000000",
        content=_valid_pdf(),
        headers={"content-type": "application/octet-stream"},
    )

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert response.status_code == 204


def test_isolated_validator_rejects_malformed_and_oversized_pdf():
    client = TestClient(app)
    payload = _valid_pdf()

    malformed = client.post(
        "/validate?extension=.pdf&max_bytes=1048576&max_image_pixels=40000000",
        content=b"%PDF-1.7 invalid bytes",
        headers={"content-type": "application/octet-stream"},
    )
    oversized = client.post(
        f"/validate?extension=.pdf&max_bytes={len(payload) - 1}&max_image_pixels=40000000",
        content=payload,
        headers={"content-type": "application/octet-stream"},
    )

    assert malformed.status_code == 422
    assert oversized.status_code == 413
