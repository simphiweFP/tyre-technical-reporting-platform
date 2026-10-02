from uuid import UUID, uuid4

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.modules.reports.infrastructure import TechnicalReportRecord


def auth_headers(client):
    response = client.post('/api/v1/auth/login', json={
        'email': 'admin@example.com', 'password': 'Password123!',
    })
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def test_claim_numbers_continue_and_remain_stable(client):
    headers = auth_headers(client)
    first_id = str(uuid4())
    first = client.put(f'/api/v1/reports/records/{first_id}', headers=headers,
                       json={'report': {'status': 'Draft', 'claimReference': 'ignored'}})
    assert first.status_code == 200
    assert first.json()['report']['claimReference'] == 'I000001'
    changed = client.put(f'/api/v1/reports/records/{first_id}', headers=headers,
                         json={'report': {'status': 'Draft', 'claimReference': 'I999999'}})
    assert changed.json()['report']['claimReference'] == 'I000001'

    # A reserved number stays reserved even when the report is archived.
    with next(app.dependency_overrides[get_db]()) as db:
        record = db.get(TechnicalReportRecord, UUID(first_id))
        record.claim_reference = 'I000290'
        record.archived = True
        db.commit()
    second = client.put(f'/api/v1/reports/records/{uuid4()}', headers=headers,
                        json={'report': {'status': 'Draft'}})
    assert second.status_code == 200
    assert second.json()['report']['claimReference'] == 'I000291'
    pdf = client.post('/api/v1/reports/generate-pdf', headers=headers,
                      json={'report': second.json()['report'], 'filename': 'wrong.pdf'})
    assert pdf.status_code == 200
    assert pdf.headers['content-disposition'] == (
        'attachment; filename="Technical_Report_I000291.pdf"'
    )
    assert pdf.content.startswith(b'%PDF')
