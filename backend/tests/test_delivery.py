from uuid import UUID

from sqlalchemy.orm import sessionmaker

from backend.app import worker
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.delivery.application import ReportDeliveryService
from backend.app.modules.delivery.infrastructure import (
    DeliveryAttempt,
)
from backend.app.modules.document_generation.application import GenerateTechnicalReport
from backend.app.modules.document_generation.infrastructure import (
    ReportLabTechnicalReportGenerator,
)
from backend.app.modules.reports.validation import REQUIRED_PHOTOS


def auth_headers(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Password123!"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_recipient(client, headers):
    response = client.post(
        "/api/v1/recipients",
        headers=headers,
        json={
            "company": "Manufacturer Claims",
            "contact_name": "Claims Desk",
            "email": "claims@example.co.za",
            "default_cc": ["manager@example.co.za", "audit@example.co.za"],
            "escalation_enabled": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def save_report(client, headers, claim_reference):
    report_id = "1ab85e4a-ff6c-487c-a39f-30a0bded412c"
    response = client.put(
        f"/api/v1/reports/records/{report_id}",
        headers=headers,
        json={
            "report": {
                "claimReference": claim_reference,
                "status": "Ready to Submit",
                "salesperson": "Admin",
                "customerName": "Test Fleet",
                "branch": "All Branches",
                "brand": "Dunlop",
                "dot": "0124",
                "serialNumber": "SERIAL-1",
                "photos": [{"category": category} for category in REQUIRED_PHOTOS],
            }
        },
    )
    assert response.status_code == 200


def test_report_delivery_is_sent_and_visible_in_history(client):
    headers = auth_headers(client)
    recipient = create_recipient(client, headers)
    save_report(client, headers, "TR-2026-0042")
    response = client.post(
        "/api/v1/reports/deliver",
        headers=headers,
        json={
            "recipient_id": recipient["id"],
            "report": {"claimReference": "TR-2026-0042", "customerName": "Test Fleet"},
            "cc": [],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Sent"
    assert response.json()["message_id"]
    assert response.json()["cc"] == ["manager@example.co.za", "audit@example.co.za"]
    history = client.get("/api/v1/reports/TR-2026-0042/deliveries", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_queued_delivery_worker_marks_attempt_sent(client):
    headers = auth_headers(client)
    recipient = create_recipient(client, headers)
    save_report(client, headers, "TR-WORKER")
    queued = client.post(
        "/api/v1/reports/deliver",
        headers=headers,
        json={
            "recipient_id": recipient["id"],
            "report": {"claimReference": "TR-WORKER"},
        },
    ).json()

    class Gateway:
        def send(self, message):
            assert message.attachment.startswith(b"%PDF")
            return "message-worker-1"

    session_override = app.dependency_overrides[get_db]()
    db = next(session_override)
    try:
        attempt = db.get(DeliveryAttempt, UUID(queued["id"]))
        result = ReportDeliveryService(
            db,
            Gateway(),
            GenerateTechnicalReport(ReportLabTechnicalReportGenerator()),
        ).deliver(attempt, attempt.requested_by)
        assert result.status == "Sent"
        assert result.message_id == "message-worker-1"
    finally:
        session_override.close()


def test_failed_delivery_can_be_requeued(client):
    headers = auth_headers(client)
    recipient = create_recipient(client, headers)
    save_report(client, headers, "TR-RETRY")
    queued = client.post(
        "/api/v1/reports/deliver",
        headers=headers,
        json={
            "recipient_id": recipient["id"],
            "report": {"claimReference": "TR-RETRY"},
        },
    ).json()
    session_override = app.dependency_overrides[get_db]()
    db = next(session_override)
    try:
        attempt = db.get(DeliveryAttempt, UUID(queued["id"]))
        attempt.status = "Failed"
        db.commit()
    finally:
        session_override.close()
    retried = client.post(
        f"/api/v1/reports/deliveries/{queued['id']}/retry", headers=headers
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "Sent"
    assert retried.json()["attempt_count"] >= 2


def test_viewer_cannot_manage_recipients(client):
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@example.com", "password": "Password123!"},
    ).json()["access_token"]
    response = client.post(
        "/api/v1/recipients",
        headers={"Authorization": f"Bearer {token}"},
        json={"company": "Blocked", "email": "blocked@example.co.za"},
    )
    assert response.status_code == 403


def test_delivery_worker_claims_and_processes_due_items(client, monkeypatch):
    headers = auth_headers(client)
    recipient = create_recipient(client, headers)
    save_report(client, headers, "TR-WORKER-QUEUE")
    queued = client.post(
        "/api/v1/reports/deliver",
        headers=headers,
        json={
            "recipient_id": recipient["id"],
            "report": {"claimReference": "TR-WORKER-QUEUE"},
        },
    ).json()

    session_override = app.dependency_overrides[get_db]()
    db = next(session_override)
    testing_session = sessionmaker(bind=db.bind, expire_on_commit=False)
    attempt_id = UUID(queued["id"])
    attempt = db.get(DeliveryAttempt, attempt_id)
    attempt.status = "Pending"
    db.commit()
    session_override.close()

    class Gateway:
        def __init__(self, _settings):
            pass

        def send(self, _message):
            return "worker-queue-message"

    monkeypatch.setattr(worker, "SessionLocal", testing_session)
    monkeypatch.setattr(worker, "SmtpEmailGateway", Gateway)

    assert worker.process_due_deliveries() == (1, 0)
    with testing_session() as verification_db:
        attempt = verification_db.get(DeliveryAttempt, UUID(queued["id"]))
        assert attempt.status == "Sent"
        assert attempt.message_id == "worker-queue-message"

    worker.update_heartbeat(processed=1)
    response = client.get("/api/v1/admin/operations", headers=headers)
    assert response.json()["delivery_worker"] == "healthy"



def test_sent_delivery_keeps_immutable_pdf_snapshot(client):
    headers = auth_headers(client)
    recipient = create_recipient(client, headers)
    save_report(client, headers, "TR-SNAPSHOT")
    sent = client.post(
        "/api/v1/reports/deliver",
        headers=headers,
        json={
            "recipient_id": recipient["id"],
            "report": {"claimReference": "TR-SNAPSHOT"},
        },
    )
    assert sent.status_code == 200
    delivery_id = sent.json()["id"]

    details = client.get(f"/api/v1/deliveries/{delivery_id}/details", headers=headers)
    assert details.status_code == 200
    assert details.json()["attachment_sha256"]

    pdf = client.get(f"/api/v1/deliveries/{delivery_id}/pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert pdf.headers["x-content-sha256"] == details.json()["attachment_sha256"]
