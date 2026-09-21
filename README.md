# Tyre Technical Reporting Platform

A mobile-first and desktop-responsive platform for capturing tyre inspections, producing Royal Tyres technical-report PDFs and delivering them to third parties.

## Architecture

The backend is a **modular monolith using Clean Architecture principles**. Business capabilities are separated into modules, while deployment remains simple.

Dependency direction:

```text
Presentation -> Application -> Domain
Infrastructure -> Application / Domain
Domain -> no framework dependencies
```

The system avoids microservices, generic repositories for every entity and abstractions without a real testing or replacement need. Angular will use feature-based, lazy-loaded modules with separate mobile-first and desktop-responsive layouts.

## Four commit phases

1. `feat: establish API foundation and role-based access`
   - FastAPI, PostgreSQL, Alembic, JWT rotation, secure password hashing, roles, branches, seeds, tests and Docker Compose.
2. `feat: build responsive technical report workflow`
   - Angular authentication, mobile-first guided capture, desktop-responsive workspace, drafts, photo handling, administration and search.
3. `feat: add tyre data extraction and PDF reporting`
   - Local OCR, confirmation workflow, validation, image compression and branded PDF generation.
4. `feat: complete report delivery and audit tracking`
   - Third-party email delivery, retry, delivery history, audit trail, final tests and deployment documentation.

## Phase 1 setup

```bash
cp .env.example .env
docker compose up --build
```

API documentation is available at `http://localhost:8000/docs`.

For local Python development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
python -m backend.app.seed
uvicorn backend.app.main:app --reload
pytest
```

The seeded development administrator defaults are defined in `.env.example`. Change them before any shared deployment.

## Angular frontend

The feature-based Angular application uses lazy-loaded features, route-level role guards, an authentication interceptor and a responsive application shell.

```bash
cd frontend
npm install
npm start
```

The frontend expects the API at `http://localhost:8000/api/v1`. Report drafts and compressed image previews are saved in browser storage so an interrupted capture can be recovered on the same device.

## OCR-assisted capture and PDF generation

Phase 3 adds local Tesseract OCR for tyre markings, browser-side image compression and duplicate-image detection. OCR values are suggestions only: the technician or salesperson must confirm each extracted value before it is copied into the report. This avoids silent AI decisions and keeps the operator accountable for the final data.

When all required fields and photographs are complete, the review screen generates a branded Royal Tyres PDF through the authenticated API. Install `tesseract-ocr` when running outside Docker.

## Email delivery

Administrators maintain approved third-party recipients. Technicians and salespeople select a recipient on the report review screen and send the generated PDF directly; there is no approval or rejection workflow. Every successful or failed attempt is recorded, failed attempts can be retried, and recipient changes and deliveries create audit events.

Docker Compose includes Mailpit for safe local email testing. Its inbox is available at `http://localhost:8025`. For deployment, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `EMAIL_FROM` and `EMAIL_FROM_NAME` with the organisation's SMTP provider.

## Production deployment checklist

- Replace the JWT secret and seeded administrator password with managed secrets.
- Use PostgreSQL with encrypted backups and run `alembic upgrade head` before starting the API.
- Configure an HTTPS reverse proxy and restrict `ALLOWED_ORIGINS` to the deployed Angular URL.
- Configure authenticated SMTP with TLS and verify the sender domain's SPF, DKIM and DMARC records.
- Retain delivery and audit records according to the organisation's privacy policy.
- Monitor failed deliveries and database health; never expose Mailpit in production.
- Run `pytest`, `npm test -- --watch=false` and `npm run build` in CI before deployment.

## Roles

- **Administrator:** manages users, roles, branches, recipients and all reports.
- **Report Capturer:** used by technicians and salespeople to create and deliver reports.
- **Viewer:** read-only report and PDF access.

## Explicit exclusions

No approval/rejection workflow, public registration, customer portal, payments, inventory, quotations, service booking, claim payout processing, chatbot, automated claim decisions or microservices.
