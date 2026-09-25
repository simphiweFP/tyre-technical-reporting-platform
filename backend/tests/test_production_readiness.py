from io import BytesIO

from PIL import Image


def login_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Password123!"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_public_registration_creates_viewer_account(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Public User",
            "email": "public@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "pending"
    assert response.json()["access_token"]


def test_admin_can_create_disable_and_reset_user(client):
    headers = login_headers(client)
    branches = client.get("/api/v1/auth/branches", headers=headers).json()
    created = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "full_name": "Tyre Technician",
            "email": "tech@example.com",
            "job_title": "Technician",
            "role": "report_capturer",
            "branch_id": branches[0]["id"],
        },
    )
    assert created.status_code == 201
    assert len(created.json()["temporary_password"]) >= 12
    user_id = created.json()["id"]
    disabled = client.patch(
        f"/api/v1/auth/users/{user_id}", headers=headers, json={"is_active": False}
    )
    assert disabled.json()["is_active"] is False
    reset = client.post(f"/api/v1/auth/users/{user_id}/reset-password", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["temporary_password"]


def test_report_crud_search_image_analytics_and_archive(client):
    headers = login_headers(client)
    report_id = "8bc7be31-8f4e-42cf-89ec-dc759971e20d"
    report = {
        "id": report_id,
        "claimReference": "TR-SEARCH-001",
        "status": "Draft",
        "customerName": "Example Fleet",
        "customerInvoiceNumber": "INV-42",
        "serialNumber": "SER-99",
        "brand": "Bridgestone",
        "category": "Manufacturing",
        "branch": "Phoenix",
        "photos": [],
    }
    saved = client.put(
        f"/api/v1/reports/records/{report_id}", headers=headers, json={"report": report}
    )
    assert saved.status_code == 200
    found = client.get(
        "/api/v1/reports/records", headers=headers, params={"query": "Example Fleet"}
    )
    assert found.json()["total"] == 1
    image = BytesIO()
    Image.new("RGB", (120, 80), "#444444").save(image, "JPEG")
    uploaded = client.post(
        f"/api/v1/reports/records/{report_id}/images",
        headers=headers,
        params={"category": "dot"},
        files={"image": ("dot.jpg", image.getvalue(), "image/jpeg")},
    )
    assert uploaded.status_code == 201
    image_id = uploaded.json()["id"]
    assert (
        client.get(
            f"/api/v1/reports/records/{report_id}/images/{image_id}", headers=headers
        ).status_code
        == 200
    )
    analytics = client.get("/api/v1/reports/analytics/summary", headers=headers).json()
    assert analytics["by_brand"]["Bridgestone"] == 1
    assert (
        client.post(
            f"/api/v1/reports/records/{report_id}/archive", headers=headers
        ).status_code
        == 204
    )
    assert client.get("/api/v1/reports/records", headers=headers).json()["total"] == 0
    archived = client.get(
        "/api/v1/reports/records",
        headers=headers,
        params={"archived_only": True},
    ).json()
    assert archived["total"] == 1
    assert archived["items"][0]["id"] == report_id


def test_report_capturer_only_sees_owned_claims_and_audit(client):
    admin_headers = login_headers(client)
    branches = client.get("/api/v1/auth/branches", headers=admin_headers).json()
    created_user = client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={
            "full_name": "Capture User",
            "email": "capture@example.com",
            "job_title": "Report Capturer",
            "role": "report_capturer",
            "branch_id": branches[0]["id"],
        },
    ).json()
    password = created_user["temporary_password"]
    capture_login = client.post(
        "/api/v1/auth/login",
        json={"email": "capture@example.com", "password": password},
    )
    capture_headers = {
        "Authorization": f"Bearer {capture_login.json()['access_token']}"
    }

    admin_report_id = "2ab745b0-0e8e-49ef-bf3b-1b8a67a19c51"
    own_report_id = "89a33b2e-991d-4d0e-9442-d217e6b43dc1"
    client.put(
        f"/api/v1/reports/records/{admin_report_id}",
        headers=admin_headers,
        json={
            "report": {
                "id": admin_report_id,
                "claimReference": "TR-ADMIN-ONLY",
                "status": "Draft",
                "customerName": "Admin Fleet",
                "branch": "PHX",
                "photos": [],
            }
        },
    )
    client.put(
        f"/api/v1/reports/records/{own_report_id}",
        headers=capture_headers,
        json={
            "report": {
                "id": own_report_id,
                "claimReference": "TR-MY-CLAIM",
                "status": "Draft",
                "customerName": "My Fleet",
                "branch": "PHX",
                "photos": [],
            }
        },
    )

    listing = client.get("/api/v1/reports/records", headers=capture_headers)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == [own_report_id]
    assert (
        client.get(
            f"/api/v1/reports/records/{admin_report_id}", headers=capture_headers
        ).status_code
        == 404
    )

    audit = client.get("/api/v1/admin/audit-events", headers=capture_headers)
    assert audit.status_code == 200
    references = {
        item["details"].get("claim_reference") for item in audit.json()["items"]
    }
    assert "TR-MY-CLAIM" in references
    assert "TR-ADMIN-ONLY" not in references
