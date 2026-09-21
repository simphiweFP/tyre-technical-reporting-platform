from sqlalchemy import select

from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.delivery.infrastructure import SmtpEmailGateway


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
            "default_cc": "manager@example.co.za",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_report_delivery_records_success_and_history(client, monkeypatch):
    monkeypatch.setattr(SmtpEmailGateway, "send", lambda self, message: "message-123")
    headers = auth_headers(client)
    recipient = create_recipient(client, headers)
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
    assert response.json()["message_id"] == "message-123"
    assert response.json()["cc"] == ["manager@example.co.za"]
    history = client.get("/api/v1/reports/TR-2026-0042/deliveries", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_failed_delivery_can_be_retried(client, monkeypatch):
    calls = iter([RuntimeError("SMTP unavailable"), "message-456"])

    def send(self, message):
        result = next(calls)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(SmtpEmailGateway, "send", send)
    headers = auth_headers(client)
    recipient = create_recipient(client, headers)
    failed = client.post(
        "/api/v1/reports/deliver",
        headers=headers,
        json={"recipient_id": recipient["id"], "report": {"claimReference": "TR-RETRY"}},
    ).json()
    assert failed["status"] == "Failed"
    retried = client.post(
        f"/api/v1/reports/deliveries/{failed['id']}/retry", headers=headers
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "Sent"
    assert retried.json()["attempt_count"] == 2


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
