from backend.app.modules.reports.validation import REQUIRED_PHOTOS


def login_headers(client, email="admin@example.com"):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_manage_branches_and_settings(client):
    headers = login_headers(client)

    created = client.post(
        "/api/v1/auth/branches",
        headers=headers,
        json={
            "code": "CPT",
            "name": "Cape Town",
            "routing_email": "cape@example.com",
        },
    )
    assert created.status_code == 201
    branch_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/auth/branches/{branch_id}",
        headers=headers,
        json={"name": "Cape Town Central", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Cape Town Central"
    assert updated.json()["is_active"] is False

    settings = {
        "company_name": "Royal Tyres Test",
        "ocr_confidence_threshold": 91,
        "pdf_template": "Technical Report v1.0",
        "offline_sync_enabled": False,
        "offline_sync_minutes": 15,
        "smtp_server": "smtp.example.com",
    }
    saved = client.put("/api/v1/admin/settings", headers=headers, json=settings)
    assert saved.status_code == 200
    assert client.get("/api/v1/admin/settings", headers=headers).json() == settings


def test_report_reference_data_uses_application_records(client):
    headers = login_headers(client)
    response = client.get("/api/v1/reports/reference-data", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert {"value": "PHX", "label": "Phoenix"} in data["branches"]
    assert data["categories"] == [
        "Manufacturing",
        "Road hazard",
        "Service related",
    ]
    assert "Front left" in data["tyre_positions"]


def test_report_validation_is_server_side_and_invoice_is_optional(client):
    headers = login_headers(client)
    valid = client.post(
        "/api/v1/reports/validate",
        headers=headers,
        json={
            "step": 0,
            "report": {
                "salesperson": "Admin",
                "customerName": "Fleet Customer",
                "branch": "PHX",
                "customerInvoiceNumber": "",
            },
        },
    )
    assert valid.status_code == 200
    assert valid.json() == {"valid": True, "errors": {}}

    invalid = client.post(
        "/api/v1/reports/validate",
        headers=headers,
        json={"step": 0, "report": {"salesperson": "Admin", "customerName": "Fleet"}},
    )
    assert invalid.status_code == 200
    assert invalid.json()["errors"]["branch"] == "Branch selection is required."


def test_admin_can_manage_recipient_rules(client):
    headers = login_headers(client)
    created = client.post(
        "/api/v1/recipients",
        headers=headers,
        json={
            "company": "Fleet Partner",
            "contact_name": "Claims Desk",
            "email": "claims@example.com",
            "default_cc": "manager@example.com",
            "branch_code": "PHX",
            "category": "Manufacturing",
            "escalation_hours": 12,
        },
    )
    assert created.status_code == 201
    recipient_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/recipients/{recipient_id}",
        headers=headers,
        json={
            "company": "Fleet Partner",
            "contact_name": "Claims Team",
            "email": "claims@example.com",
            "default_cc": None,
            "branch_code": "All Branches",
            "category": "All Categories",
            "escalation_hours": 48,
            "is_active": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["contact_name"] == "Claims Team"
    assert updated.json()["default_cc"] == ""
    assert updated.json()["escalation_hours"] == 48
    assert updated.json()["is_active"] is False


def test_recipient_rules_are_applied_to_claim_delivery(client):
    headers = login_headers(client)
    recipient = client.post(
        "/api/v1/recipients",
        headers=headers,
        json={
            "company": "Manufacturing Partner",
            "contact_name": "Claims",
            "email": "routing@example.com",
            "branch_code": "Phoenix",
            "category": "Manufacturing",
            "escalation_hours": 24,
        },
    ).json()
    report_id = "d09e7d92-d5df-487b-a9b6-9996925866de"
    report = {
        "id": report_id,
        "claimReference": "TR-ROUTING-001",
        "status": "Ready to Submit",
        "branch": "Cape Town",
        "category": "Manufacturing",
        "salesperson": "Admin",
        "customerName": "Fleet Customer",
        "brand": "Dunlop",
        "dot": "0124",
        "serialNumber": "SERIAL-1",
        "photos": [{"category": category} for category in REQUIRED_PHOTOS],
    }
    assert (
        client.put(
            f"/api/v1/reports/records/{report_id}",
            headers=headers,
            json={"report": report},
        ).status_code
        == 200
    )

    filtered = client.get(
        "/api/v1/recipients",
        headers=headers,
        params={"branch": "Cape Town", "category": "Manufacturing"},
    )
    assert filtered.status_code == 200
    assert filtered.json() == []

    rejected = client.post(
        "/api/v1/reports/deliver",
        headers=headers,
        json={"recipient_id": recipient["id"], "report": report, "cc": []},
    )
    assert rejected.status_code == 422
    assert "branch" in rejected.json()["detail"].lower()


def test_audit_viewer_reads_real_events(client):
    headers = login_headers(client)
    client.put(
        "/api/v1/admin/settings",
        headers=headers,
        json={
            "company_name": "Royal Tyres Test",
            "ocr_confidence_threshold": 90,
            "pdf_template": "Technical Report v1.0",
            "offline_sync_enabled": True,
            "offline_sync_minutes": 10,
            "smtp_server": "smtp.example.com",
        },
    )

    response = client.get(
        "/api/v1/admin/audit-events",
        headers=headers,
        params={"query": "settings.updated"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["action"] == "settings.updated"

    viewer_headers = login_headers(client, "viewer@example.com")
    assert (
        client.get("/api/v1/admin/audit-events", headers=viewer_headers).status_code
        == 200
    )
    assert (
        client.get("/api/v1/admin/settings", headers=viewer_headers).status_code == 403
    )


def test_operations_health_is_admin_only(client):
    headers = login_headers(client)
    response = client.get("/api/v1/admin/operations", headers=headers)
    assert response.status_code == 200
    assert response.json()["database"] == "healthy"
    assert response.json()["file_storage"] == "healthy"
    assert response.json()["delivery_worker"] == "not_started"

    viewer_headers = login_headers(client, "viewer@example.com")
    assert (
        client.get("/api/v1/admin/operations", headers=viewer_headers).status_code
        == 403
    )
