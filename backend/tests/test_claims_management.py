import csv
import smtplib
from io import BytesIO, StringIO
from uuid import UUID
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from backend.app.core.database import get_db
from backend.app.core.security import hash_password
from backend.app.main import app
from backend.app.modules.claims.documents import TRACKER_COLUMNS
from backend.app.modules.delivery import presentation as delivery_presentation
from backend.app.modules.delivery.infrastructure import DeliveryAttempt
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.reports.infrastructure import TechnicalReportRecord


def login(client, email="admin@example.com"):
    result = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    assert result.status_code == 200
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


@pytest.fixture
def claims_setup(client):
    with next(app.dependency_overrides[get_db]()) as db:
        admin = db.scalar(select(User).where(User.email == "admin@example.com"))
        owners = []
        for name in ["claims", "other"]:
            user = User(
                email=f"{name}@example.com",
                full_name=name.title(),
                role="claims_administrator",
                password_hash=hash_password("Password123!"),
            )
            db.add(user)
            db.flush()
            owners.append(str(user.id))
        report = TechnicalReportRecord(
            claim_reference="I000291",
            status="Submitted",
            created_by=admin.id,
            customer_name="Morgado Plant Hire",
            branch_name="RTCPHX",
            tyre_brand="AEOLUS",
            serial_number="KA251004858",
            report_data={
                "claimReference": "I000291",
                "status": "Submitted",
                "customerName": "Morgado Plant Hire",
                "customerInvoiceNumber": "INV100",
                "branch": "RTCPHX",
                "brand": "AEOLUS",
                "tyreSize": "23.5R25",
                "pattern": "AE417",
                "serialNumber": "KA251004858",
                "claimCode": "Sidewall scuffing",
                "remainingTreadDepth": "49",
                "photos": [],
            },
        )
        db.add(report)
        db.flush()
        db.add(
            DeliveryAttempt(
                claim_reference=report.claim_reference,
                recipient_email="supplier@example.com",
                requested_by=admin.id,
                status="Sent",
                document_type="technical",
                report_payload={"claimReference": report.claim_reference},
            )
        )
        db.commit()
        report_id = str(report.id)
    return {
        "admin": login(client),
        "claims": login(client, "claims@example.com"),
        "other": login(client, "other@example.com"),
        "owner": owners[0],
        "other_owner": owners[1],
        "report": report_id,
    }


def handover(client, crew):
    response = client.post(
        "/api/v1/claims/handover",
        headers=crew["admin"],
        json={
            "report_id": crew["report"],
            "assigned_to": crew["owner"],
            "notes": "Follow up with supplier",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def update(client, crew, claim, **values):
    data = {**claim["data"], **values}
    result = client.put(
        f"/api/v1/claims/{claim['id']}",
        headers=crew["claims"],
        json={
            "data": data,
            "expected_updated_at": claim["updated_at"],
            "workflow_status": "In progress",
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_handover_permissions_and_no_duplicate(client, claims_setup):
    crew = claims_setup
    claim = handover(client, crew)
    assert claim["claim_reference"] == "I000291"
    assert claim["tyre_size"] == "23.5R25"
    assert claim["data"]["remaining_tread_depth"] == 49
    assert (
        client.get(f"/api/v1/claims/{claim['id']}", headers=crew["other"]).status_code
        == 404
    )
    assert client.get("/api/v1/claims", headers=crew["other"]).json()["total"] == 0
    assert client.get("/api/v1/claims", headers=crew["claims"]).json()["total"] == 1
    assert client.get("/api/v1/auth/users", headers=crew["claims"]).status_code == 403
    assert (
        client.post(
            "/api/v1/claims/handover",
            headers=crew["claims"],
            json={"report_id": crew["report"], "assigned_to": crew["owner"]},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/claims/handover",
            headers=crew["admin"],
            json={"report_id": crew["report"], "assigned_to": crew["owner"]},
        ).status_code
        == 409
    )


def test_credit_workflow_and_manual_percentages(client, claims_setup, monkeypatch):
    crew = claims_setup
    claim = handover(client, crew)
    claim = update(
        client,
        crew,
        claim,
        supplier="Prometeon Group",
        original_tread_depth=54,
        supplier_status="Accepted",
        accepted_percentage=100,
        customer_credit_percentage=91,
        supplier_submitted_date="2026-09-08",
        supplier_feedback_date="2026-09-09",
        claim_date="2026-09-08",
        instruction_supplier="Aeolus Tyre Co",
    )
    assert claim["remaining_percentage"] == 90.74
    assert claim["credit_outstanding"] and claim["supplier_offset_outstanding"]
    response = client.post(
        f"/api/v1/claims/{claim['id']}/instructions",
        headers=crew["claims"],
        json={"notes": "Pass the agreed 91% credit"},
    )
    assert response.status_code == 201, response.text
    instruction = response.json()["instructions"][0]
    assert instruction["data"]["customer_credit_percentage"] == 91
    assert instruction["data"]["supplier"] == "Aeolus Tyre Co"
    received = client.post(
        f"/api/v1/claims/{claim['id']}/instructions/{instruction['id']}/receive",
        headers=crew["claims"],
    )
    assert received.status_code == 200
    assert received.json()["instructions"][0]["acknowledged_at"]
    captured = []
    monkeypatch.setattr(
        delivery_presentation.SmtpEmailGateway,
        "send",
        lambda self, message: captured.append(message) or "<test@example.com>",
    )
    sent = client.post(
        f"/api/v1/claims/{claim['id']}/documents/credit/send",
        headers=crew["claims"],
        json={
            "recipient_email": "claims@example.com",
            "cc": ["accounts@example.com"],
            "instruction_id": instruction["id"],
        },
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "Sent"
    assert captured[0].attachment_name == "Instruction_to_Credit_I000291.pdf"
    assert captured[0].attachment.startswith(b"%PDF")
    delivery_id = sent.json()["id"]
    original = client.get(
        f"/api/v1/deliveries/{delivery_id}/pdf", headers=crew["claims"]
    )
    assert original.status_code == 200
    assert (
        client.get(
            f"/api/v1/deliveries/{delivery_id}/pdf", headers=crew["other"]
        ).status_code
        == 404
    )
    claim = client.get(f"/api/v1/claims/{claim['id']}", headers=crew["claims"]).json()
    claim = update(client, crew, claim, customer_credit_percentage=75)
    assert (
        client.get(
            f"/api/v1/deliveries/{delivery_id}/pdf", headers=crew["claims"]
        ).content
        == original.content
    )
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.get(TechnicalReportRecord, UUID(crew["report"])).status == "Submitted"
    claim = update(
        client,
        crew,
        claim,
        customer_credit_amount=4500,
        credit_note_reference="CN1234",
        customer_credit_date="2026-09-10",
        supplier_offset_invoice="INV45678",
        supplier_offset_date="2026-09-15",
        supplier_recovered_amount=4500,
    )
    stats = client.get("/api/v1/claims/metrics", headers=crew["claims"]).json()
    row = stats["scorecard"][0]
    assert row["acceptance_rate"] == 100 and row["rejection_rate"] == 0
    assert row["average_response_days"] == 1 and row["average_resolution_days"] == 2
    assert row["credit_value_recovered"] == 4500
    assert (
        stats["credit_notes_not_passed"] == 0
        and stats["outstanding_supplier_offsets"] == 0
    )
    closed = client.put(
        f"/api/v1/claims/{claim['id']}",
        headers=crew["claims"],
        json={
            "data": claim["data"],
            "expected_updated_at": claim["updated_at"],
            "workflow_status": "Closed",
        },
    )
    assert closed.status_code == 200


def test_validation_stale_updates_and_missing_dates(client, claims_setup):
    crew = claims_setup
    claim = handover(client, crew)
    for values in [
        {"supplier": "Typed supplier", "original_tread_depth": 0},
        {"supplier": "Typed supplier", "customer_credit_percentage": 101},
        {"supplier": "Typed supplier", "supplier_status": "Rejected"},
        {"supplier": "Typed supplier", "original_tread_depth": 40},
    ]:
        result = client.put(
            f"/api/v1/claims/{claim['id']}",
            headers=crew["claims"],
            json={
                "data": {**claim["data"], **values},
                "expected_updated_at": claim["updated_at"],
            },
        )
        assert result.status_code == 422
    saved = update(client, crew, claim, supplier="Manually typed supplier")
    stale = client.put(
        f"/api/v1/claims/{claim['id']}",
        headers=crew["claims"],
        json={"data": saved["data"], "expected_updated_at": claim["updated_at"]},
    )
    assert stale.status_code == 409
    closed = client.put(
        f"/api/v1/claims/{claim['id']}",
        headers=crew["claims"],
        json={
            "data": saved["data"],
            "expected_updated_at": saved["updated_at"],
            "workflow_status": "Closed",
        },
    )
    assert closed.status_code == 422


@pytest.mark.parametrize(
    "partial",
    [
        {"supplier_offset_invoice": "INV1"},
        {"supplier_offset_date": "2026-09-10"},
        {"credit_note_reference": "CN1"},
        {"customer_credit_date": "2026-09-10"},
        {"supplier_offset_invoice": "   ", "supplier_offset_date": "2026-09-10"},
    ],
)
def test_partial_tracking_saves_but_remains_outstanding(client, claims_setup, partial):
    crew = claims_setup
    claim = update(
        client,
        crew,
        handover(client, crew),
        supplier="Typed supplier",
        claim_date="2026-09-08",
        supplier_status="Accepted",
        supplier_feedback_date="2026-09-09",
        accepted_percentage=50,
        customer_credit_percentage=50,
        **partial,
    )
    assert claim["credit_outstanding"] and claim["supplier_offset_outstanding"]
    persisted = client.get(
        f"/api/v1/claims/{claim['id']}", headers=crew["claims"]
    ).json()
    for field, value in partial.items():
        assert persisted["data"][field] == value
    metrics = client.get("/api/v1/claims/metrics", headers=crew["claims"]).json()
    assert metrics["outstanding_supplier_offsets"] == 1
    assert metrics["credit_notes_not_passed"] == 1
    assert metrics["scorecard"][0]["average_resolution_days"] is None
    closed = client.put(
        f"/api/v1/claims/{claim['id']}",
        headers=crew["claims"],
        json={
            "data": claim["data"],
            "expected_updated_at": claim["updated_at"],
            "workflow_status": "Closed",
        },
    )
    assert closed.status_code == 422
    claim = update(
        client,
        crew,
        claim,
        credit_note_reference="CN1",
        customer_credit_date="2026-09-10",
        supplier_offset_invoice="INV1",
        supplier_offset_date="2026-09-10",
    )
    assert not claim["credit_outstanding"]
    assert not claim["supplier_offset_outstanding"]
    closed = client.put(
        f"/api/v1/claims/{claim['id']}",
        headers=crew["claims"],
        json={
            "data": claim["data"],
            "expected_updated_at": claim["updated_at"],
            "workflow_status": "Closed",
        },
    )
    assert closed.status_code == 200


def test_rejection_report_failure_is_visible_and_retry_uses_snapshot(
    client, claims_setup, monkeypatch
):
    crew = claims_setup
    claim = handover(client, crew)
    claim = update(
        client,
        crew,
        claim,
        supplier="Typed supplier",
        claim_date="2026-09-08",
        supplier_status="Rejected",
        supplier_feedback_date="2026-09-09",
        accepted_percentage=0,
        customer_credit_percentage=0,
        supplier_feedback_comments="Impact damage",
    )

    def fail(self, message):
        raise smtplib.SMTPRecipientsRefused(
            {"invalid@example.com": (550, b"Mailbox unavailable")}
        )

    monkeypatch.setattr(delivery_presentation.SmtpEmailGateway, "send", fail)
    sent = client.post(
        f"/api/v1/claims/{claim['id']}/documents/rejection/send",
        headers=crew["claims"],
        json={"recipient_email": "invalid@example.com"},
    )
    assert sent.status_code == 200 and sent.json()["status"] == "Failed"
    delivery_id = sent.json()["id"]
    listing = client.get("/api/v1/deliveries", headers=crew["claims"]).json()
    assert listing["items"][0]["document_type"] == "rejection"
    assert client.get("/api/v1/deliveries", headers=crew["other"]).json()["total"] == 0
    captured = []
    monkeypatch.setattr(
        delivery_presentation.SmtpEmailGateway,
        "send",
        lambda self, message: captured.append(message) or "<retry@example.com>",
    )
    retry = client.post(
        f"/api/v1/reports/deliveries/{delivery_id}/retry", headers=crew["claims"]
    )
    assert retry.status_code == 200 and retry.json()["status"] == "Sent"
    assert captured[0].attachment_name == "Rejection_Report_I000291.pdf"
    assert (
        client.get(
            f"/api/v1/deliveries/{delivery_id}/details", headers=crew["other"]
        ).status_code
        == 404
    )
    follow_up = client.post(
        f"/api/v1/deliveries/{delivery_id}/follow-up",
        headers=crew["claims"],
        json={"message": "Please confirm receipt."},
    )
    assert follow_up.status_code == 200


def test_supplier_lookup_export_and_scorecard_send(client, claims_setup, monkeypatch):
    crew = claims_setup
    assert all(
        row["CardType"] == "S"
        for row in client.get(
            "/api/v1/claims/suppliers?search=Aeolus", headers=crew["claims"]
        ).json()["items"]
    )
    claim = handover(client, crew)
    claim = update(client, crew, claim, supplier="=Unsafe Supplier")
    response = client.get("/api/v1/claims/export/tracker", headers=crew["claims"])
    rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][:23] == [label for label, _ in TRACKER_COLUMNS]
    assert rows[1][2] == "'=Unsafe Supplier"
    for section in ["credit", "scorecard", "metrics"]:
        assert (
            client.get(
                f"/api/v1/claims/export/{section}", headers=crew["claims"]
            ).status_code
            == 200
        )
    monkeypatch.setattr(
        delivery_presentation.SmtpEmailGateway,
        "send",
        lambda self, message: "<scorecard@example.com>",
    )
    sent = client.post(
        "/api/v1/claims/scorecard/send",
        headers=crew["claims"],
        json={"recipient_email": "manager@example.com"},
    )
    assert sent.status_code == 200 and sent.json()["document_type"] == "scorecard"
    assert (
        client.get(
            f"/api/v1/deliveries/{sent.json()['id']}/pdf", headers=crew["claims"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/deliveries/{sent.json()['id']}/pdf", headers=crew["other"]
        ).status_code
        == 404
    )


def mock_workbook():
    rows = {
        "A": 46273,
        "B": "I000235",
        "C": "Prometeon Group",
        "D": "Morgado",
        "F": "RTCPHX",
        "G": "AEOLUS",
        "H": "23.5R25",
        "I": "AE417",
        "J": "KA251004858",
        "K": "Sidewall scuffing",
        "L": 49,
        "M": 54,
        "O": 46273,
        "P": "Accepted",
        "Q": 1,
        "R": 46274,
        "S": 0.91,
        "T": "1234",
        "U": 46275,
        "V": "INV45678",
        "W": 46280,
    }
    instruction = {
        **{key: value for key, value in rows.items() if key <= "K"},
        "C": "Aeolus Tyre Co",
        "L": "Accepted",
        "M": 0.91,
    }

    def sheet(values, row):
        return (
            '<worksheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main"><sheetData><row r="%s">%s</row>'
            "</sheetData></worksheet>"
            % (
                row,
                "".join(
                    (
                        f'<c r="{k}{row}" t="inlineStr"><is><t>'
                        f"{escape(str(v))}</t></is></c>"
                    )
                    if isinstance(v, str)
                    else f'<c r="{k}{row}"><v>{v}</v></c>'
                    for k, v in values.items()
                ),
            )
        )

    content = BytesIO()
    with ZipFile(content, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships"><sheets>'
            '<sheet name="Claim Tracker" r:id="r1"/>'
            '<sheet name="Instruction to credit" r:id="r2"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>',
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet(rows, 4))
        z.writestr("xl/worksheets/sheet2.xml", sheet(instruction, 3))
    return content.getvalue()


def test_workbook_import_preserves_all_tracker_values(client, claims_setup):
    crew = claims_setup
    response = client.post(
        f"/api/v1/claims/import?assigned_to={crew['owner']}",
        headers=crew["admin"],
        files={"file": ("Claims Management.xlsx", mock_workbook())},
    )
    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 1, response.json()
    case = client.get("/api/v1/claims", headers=crew["claims"]).json()["items"][0]
    assert case["claim_reference"] == "I000235"
    assert case["tyre_size"] == "23.5R25"
    assert case["data"]["customer_credit_percentage"] == 91
    assert case["data"]["accepted_percentage"] == 100
    assert case["data"]["credit_note_reference"] == "1234"
    assert case["data"]["supplier_offset_invoice"] == "INV45678"
    assert case["data"]["instruction_supplier"] == "Aeolus Tyre Co"
    assert case["instructions"][0]["data"]["supplier"] == "Aeolus Tyre Co"
    again = client.post(
        f"/api/v1/claims/import?assigned_to={crew['owner']}",
        headers=crew["admin"],
        files={"file": ("Claims Management.xlsx", mock_workbook())},
    )
    assert again.json()["skipped"] == 1
    assert (
        client.post(
            f"/api/v1/claims/import?assigned_to={crew['owner']}",
            headers=crew["claims"],
            files={"file": ("Claims Management.xlsx", mock_workbook())},
        ).status_code
        == 403
    )


def test_first_admin_views_but_cannot_run_claim_operations(client, claims_setup):
    crew = claims_setup
    claim = handover(client, crew)
    claim = update(
        client,
        crew,
        claim,
        supplier="Supplier",
        supplier_status="Accepted",
        supplier_feedback_date=claim["data"]["claim_date"],
        accepted_percentage=100,
        customer_credit_percentage=75,
    )
    base = f"/api/v1/claims/{claim['id']}"
    before = client.get(base, headers=crew["admin"])
    assert before.status_code == 200
    instruction = claim["instructions"][0]["id"]
    operations = [
        (
            "put",
            base,
            {"data": claim["data"], "expected_updated_at": claim["updated_at"]},
        ),
        ("post", base + "/instructions", {"notes": "Credit"}),
        ("post", base + f"/instructions/{instruction}/receive", None),
        (
            "post",
            base + "/documents/tracker/send",
            {"recipient_email": "supplier@example.com"},
        ),
        (
            "post",
            "/api/v1/claims/scorecard/send",
            {"recipient_email": "supplier@example.com"},
        ),
    ]
    for method, url, body in operations:
        response = getattr(client, method)(url, headers=crew["admin"], json=body)
        assert response.status_code == 403, (url, response.text)
    viewed = client.get(base, headers=crew["admin"]).json()
    assert viewed["updated_at"] == before.json()["updated_at"]
    assert viewed["instructions"][0]["acknowledged_at"] is None


def test_manual_handover_waits_for_sent_email(client, claims_setup):
    crew = claims_setup
    with next(app.dependency_overrides[get_db]()) as db:
        attempt = db.scalar(select(DeliveryAttempt))
        attempt.status = "Failed"
        db.commit()
    assert (
        client.get("/api/v1/claims/available-reports", headers=crew["admin"]).json()
        == []
    )
    response = client.post(
        "/api/v1/claims/handover",
        headers=crew["admin"],
        json={"report_id": crew["report"], "assigned_to": crew["owner"]},
    )
    assert response.status_code == 422


def test_claim_email_only_attaches_selected_files_and_one_claim_csv(
    client, claims_setup, monkeypatch
):
    crew = claims_setup
    claim = handover(client, crew)
    captured = []
    monkeypatch.setattr(
        delivery_presentation.SmtpEmailGateway,
        "send",
        lambda self, message: captured.append(message) or "claim-mail",
    )
    sent = client.post(
        f"/api/v1/claims/{claim['id']}/email",
        headers=crew["claims"],
        json={
            "recipient_email": "accounts@example.com",
            "attachments": ["tracker", "tracker_csv"],
        },
    )
    assert sent.status_code == 200 and sent.json()["status"] == "Sent", sent.text
    message = captured[0]
    assert message.attachment is None
    assert len(message.attachments) == 2
    assert {a.filename for a in message.attachments} == {
        "Claim_Tracker_I000291.pdf",
        "Claim_Tracker_I000291.csv",
    }
    csv_file = next(a for a in message.attachments if a.content_type == "text/csv")
    rows = list(csv.reader(StringIO(csv_file.content.decode("utf-8-sig"))))
    assert len(rows) == 2 and rows[1][1] == "I000291"
    delivery_id = sent.json()["id"]
    saved = client.get(f"/api/v1/deliveries/{delivery_id}/pdf", headers=crew["claims"])
    assert saved.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(saved.content)) as archive:
        assert set(archive.namelist()) == {a.filename for a in message.attachments}
    assert (
        client.get(
            f"/api/v1/deliveries/{delivery_id}/pdf", headers=crew["other"]
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/claims/{claim['id']}/email",
            headers=crew["admin"],
            json={
                "recipient_email": "accounts@example.com",
                "attachments": ["tracker"],
            },
        ).status_code
        == 403
    )


def test_claim_email_rejects_empty_or_unavailable_attachments(client, claims_setup):
    crew = claims_setup
    claim = handover(client, crew)
    for selections in [[], ["credit"], ["rejection"], ["scorecard"]]:
        response = client.post(
            f"/api/v1/claims/{claim['id']}/email",
            headers=crew["claims"],
            json={"recipient_email": "accounts@example.com", "attachments": selections},
        )
        assert response.status_code == 422, response.text


def test_claim_email_retry_keeps_selected_attachments(
    client, claims_setup, monkeypatch
):
    crew = claims_setup
    claim = handover(client, crew)
    captured = []

    def fail(self, message):
        captured.append(message)
        raise smtplib.SMTPRecipientsRefused(
            {"accounts@example.com": (550, b"Unavailable")}
        )

    monkeypatch.setattr(delivery_presentation.SmtpEmailGateway, "send", fail)
    response = client.post(
        f"/api/v1/claims/{claim['id']}/email",
        headers=crew["claims"],
        json={
            "recipient_email": "accounts@example.com",
            "attachments": ["tracker", "tracker_csv"],
        },
    )
    assert response.status_code == 200 and response.json()["status"] == "Failed", (
        response.text
    )
    update(client, crew, claim, supplier="Changed after sending")
    monkeypatch.setattr(
        delivery_presentation.SmtpEmailGateway,
        "send",
        lambda self, message: captured.append(message) or "retry",
    )
    retry = client.post(
        f"/api/v1/reports/deliveries/{response.json()['id']}/retry",
        headers=crew["claims"],
    )
    assert retry.status_code == 200 and retry.json()["status"] == "Sent", retry.text
    assert captured[0].attachments == captured[1].attachments


@pytest.mark.parametrize(
    "content_type,filename",
    [("text/csv", "Claims.csv"), ("application/pdf", "Claims.pdf")],
)
def test_smtp_attachment_uses_correct_mime_type(monkeypatch, content_type, filename):
    from backend.app.core.config import Settings
    from backend.app.modules.delivery.domain import EmailAttachment, EmailMessage
    from backend.app.modules.delivery.infrastructure import SmtpEmailGateway

    sent = []

    class SmtpClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ehlo(self):
            pass

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(smtplib, "SMTP", SmtpClient)
    gateway = SmtpEmailGateway(
        Settings(smtp_host="smtp.example.com", smtp_use_tls=False, smtp_username="")
    )
    gateway.send(
        EmailMessage(
            subject="Report",
            body="Report attached",
            to=("accounts@example.com",),
            cc=(),
            attachment_name=filename,
            attachment=b"report-content",
            attachment_content_type=content_type,
            attachments=(EmailAttachment("Extra.csv", b"extra-csv", "text/csv"),),
        )
    )
    attachments = list(sent[0].iter_attachments())
    assert len(attachments) == 2
    assert attachments[1].get_filename() == "Extra.csv"
    assert attachments[1].get_payload(decode=True) == b"extra-csv"
    attachment = attachments[0]
    assert attachment.get_content_type() == content_type
    assert attachment.get_filename() == filename
    assert attachment.get_payload(decode=True) == b"report-content"


def test_single_claim_csv_is_attached_without_a_bundle(
    client, claims_setup, monkeypatch
):
    crew = claims_setup
    claim = handover(client, crew)
    captured = []
    monkeypatch.setattr(
        delivery_presentation.SmtpEmailGateway,
        "send",
        lambda self, message: captured.append(message) or "csv-only",
    )
    sent = client.post(
        f"/api/v1/claims/{claim['id']}/email",
        headers=crew["claims"],
        json={
            "recipient_email": "accounts@example.com",
            "attachments": ["tracker_csv"],
        },
    )
    assert sent.status_code == 200 and sent.json()["status"] == "Sent", sent.text
    assert captured[0].attachment_name == "Claim_Tracker_I000291.csv"
    assert captured[0].attachment_content_type == "text/csv"
    assert not captured[0].attachments
    assert (
        len(list(csv.reader(StringIO(captured[0].attachment.decode("utf-8-sig"))))) == 2
    )
