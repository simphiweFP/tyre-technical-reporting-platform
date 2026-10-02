from uuid import UUID, uuid4

from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.claims.automation import continue_existing_reports
from backend.app.modules.claims.infrastructure import ClaimCase
from backend.app.modules.reports.infrastructure import TechnicalReportRecord
from backend.app.modules.reports.validation import REQUIRED_PHOTOS
from backend.tests.test_claims_management import claims_setup as claims_setup
from backend.tests.test_claims_management import handover, update


def report_data():
    return {
        "status": "Submitted",
        "salesperson": "Admin",
        "customerName": "Fleet",
        "customerInvoiceNumber": "INV-100",
        "branch": "Phoenix",
        "brand": "AEOLUS",
        "tyreSize": "315/80R22.5",
        "rimSize": "22.5",
        "pattern": "AE417",
        "dot": "2026",
        "serialNumber": "SER-1",
        "remainingTreadDepth": "49",
        "inspectedPressure": "800",
        "inspectedLocation": "RTCPHX",
        "tyrePosition": "Front",
        "claimCode": "Sidewall damage",
        "photos": [{"category": c} for c in REQUIRED_PHOTOS],
    }


def test_submit_automatically_continues_same_claim_and_syncs_source(
    client, claims_setup, monkeypatch
):
    crew = claims_setup
    monkeypatch.setattr(get_settings(), "seed_claims_admin_email", "claims@example.com")
    report_id = str(uuid4())
    data = report_data()
    saved = client.put(
        f"/api/v1/reports/records/{report_id}",
        headers=crew["admin"],
        json={"report": data},
    )
    assert saved.status_code == 200, saved.text
    claims = client.get("/api/v1/claims", headers=crew["claims"]).json()["items"]
    assert len(claims) == 1
    claim = claims[0]
    lookup = client.get(
        f"/api/v1/claims/for-report/{report_id}", headers=crew["claims"]
    )
    assert lookup.status_code == 200 and lookup.json()["id"] == claim["id"]
    assert (
        client.get(
            f"/api/v1/claims/for-report/{report_id}", headers=crew["other"]
        ).status_code
        == 404
    )
    assert claim["report_id"] == report_id
    assert claim["claim_reference"] == saved.json()["report"]["claimReference"]
    assert claim["data"]["tyre_size"] == "315/80R22.5"
    assert claim["data"]["remaining_tread_depth"] == 49
    data.update(customerName="Corrected fleet", remainingTreadDepth="48")
    assert (
        client.put(
            f"/api/v1/reports/records/{report_id}",
            headers=crew["admin"],
            json={"report": data},
        ).status_code
        == 200
    )
    claim = client.get(f"/api/v1/claims/{claim['id']}", headers=crew["claims"]).json()
    assert claim["customer_name"] == "Corrected fleet"
    assert claim["data"]["remaining_tread_depth"] == 48
    claim = update(
        client, crew, claim, supplier="Typed supplier", remaining_tread_depth=46
    )
    data["remainingTreadDepth"] = "45"
    assert (
        client.put(
            f"/api/v1/reports/records/{report_id}",
            headers=crew["admin"],
            json={"report": data},
        ).status_code
        == 200
    )
    claims = client.get("/api/v1/claims", headers=crew["claims"]).json()["items"]
    assert len(claims) == 1 and claims[0]["data"]["remaining_tread_depth"] == 46


def test_drafts_and_ambiguous_owners_stay_out_of_automatic_queue(
    client, claims_setup, monkeypatch
):
    monkeypatch.setattr(
        get_settings(), "seed_claims_admin_email", "missing@example.com"
    )
    for status in ("Draft", "Submitted"):
        data = {**report_data(), "status": status}
        response = client.put(
            f"/api/v1/reports/records/{uuid4()}",
            headers=claims_setup["admin"],
            json={"report": data},
        )
        assert response.status_code == 200, response.text
    assert (
        client.get("/api/v1/claims", headers=claims_setup["admin"]).json()["total"] == 0
    )


def test_existing_reports_backfill_once_and_keep_owner(
    client, claims_setup, monkeypatch
):
    monkeypatch.setattr(get_settings(), "seed_claims_admin_email", "claims@example.com")
    with next(app.dependency_overrides[get_db]()) as db:
        continue_existing_reports(db)
        db.commit()
        continue_existing_reports(db)
        db.commit()
        cases = db.scalars(select(ClaimCase)).all()
        assert len(cases) == 1
        assert cases[0].report_id == UUID(claims_setup["report"])
        assert str(cases[0].assigned_to) == claims_setup["owner"]
        assert db.get(TechnicalReportRecord, cases[0].report_id).status == "Submitted"


def test_manual_percentage_auto_issues_once_and_keeps_previous_snapshot(
    client, claims_setup
):
    crew = claims_setup
    claim = handover(client, crew)
    claim = update(
        client,
        crew,
        claim,
        supplier="Prometeon Group",
        claim_date="2026-09-08",
        supplier_feedback_date="2026-09-09",
        supplier_status="Accepted",
        accepted_percentage=100,
        customer_credit_percentage=91,
    )
    assert len(claim["instructions"]) == 1
    original = claim["instructions"][0]
    assert original["data"]["customer_credit_percentage"] == 91
    claim = update(client, crew, claim, original_tread_depth=54)
    assert len(claim["instructions"]) == 1
    claim = update(client, crew, claim, customer_credit_percentage=75)
    assert len(claim["instructions"]) == 2
    assert claim["instructions"][0]["data"]["customer_credit_percentage"] == 75
    assert (
        next(i for i in claim["instructions"] if i["id"] == original["id"])["data"][
            "customer_credit_percentage"
        ]
        == 91
    )

    assert (
        client.post(
            f"/api/v1/claims/{claim['id']}/instructions/{original['id']}/receive",
            headers=crew["claims"],
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/claims/{claim['id']}/instructions/{claim['instructions'][0]['id']}/receive",
            headers=crew["claims"],
        ).status_code
        == 200
    )
