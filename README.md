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

## Delivery phases

1. `feat: establish API foundation and role-based access`
   - FastAPI, PostgreSQL, Alembic, JWT rotation, secure password hashing, roles, branches, seeds, tests and Docker Compose.
2. `feat: build responsive technical report workflow`
   - Angular authentication, mobile-first guided capture, desktop-responsive workspace, drafts, photo handling, administration and search.
3. `feat: add tyre data extraction and PDF reporting`
   - Local OCR, confirmation workflow, validation, image compression and branded PDF generation.
4. `feat: complete report delivery and audit tracking`
   - Third-party email delivery, retry, delivery history, audit trail, final tests and deployment documentation.
5. `feat: make the reporting platform production ready`
   - Server report persistence, protected local image files, full report APIs, public registration, Microsoft account linking, user administration, password recovery, durable email queue, analytics and operational protections.

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

The frontend expects the API at `http://localhost:8000/api/v1`. Reports and drafts are stored in PostgreSQL. Compressed images are written to the configured local media directory with metadata in PostgreSQL and are only served through authenticated endpoints. Docker uses a persistent `report_images` volume.

## Registration and sign-in

Registration is public and offers two paths:

- **Continue with Microsoft / Outlook:** OpenID Connect through Microsoft Entra ID. A verified matching email safely links to the existing account instead of creating a duplicate.
- **Create a new account:** name, email and a password of at least 12 characters.

Self-registered accounts receive the `pending` role and cannot access reports. An administrator must assign a branch and promote the account to Viewer, Report Capturer or Administrator. Configure `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` and `MICROSOFT_REDIRECT_URI` to enable Microsoft sign-in. Register the callback URL in the Entra application exactly as configured.

## OCR-assisted capture and PDF generation

Phase 3 adds local Tesseract OCR for tyre markings, browser-side image compression and duplicate-image detection. OCR values are suggestions only: the technician or salesperson must confirm each extracted value before it is copied into the report. This avoids silent AI decisions and keeps the operator accountable for the final data.

When all required fields and photographs are complete, the review screen generates a branded Royal Tyres PDF through the authenticated API. Install `tesseract-ocr` when running outside Docker.

## Email delivery

Administrators maintain approved third-party recipients. Technicians and salespeople select a recipient on the report review screen and send the generated PDF directly; there is no approval or rejection workflow. Every successful or failed attempt is recorded, failed attempts can be retried, and recipient changes and deliveries create audit events.

Delivery requests are stored before returning to the user. The `delivery-worker` service processes the durable queue, uses row locking to prevent two workers taking the same item and schedules automatic retries before marking a delivery failed. Docker Compose includes Mailpit for safe local email testing at `http://localhost:8025`. For deployment, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `EMAIL_FROM` and `EMAIL_FROM_NAME` with the organisation's SMTP provider.

## PDF branding and OCR acceptance

Set `ROYAL_TYRES_LOGO_PATH`, `ROYAL_TYRES_COMPANY_DETAILS` and `ROYAL_TYRES_PDF_DISCLAIMER` to the approved brand assets and legal wording. The PDF engine uses those values without a code change. Final visual sign-off still requires the official logo file and approved wording from Royal Tyres.

OCR values are always suggestions requiring operator confirmation. Parser fixtures cover common spacing and recognition noise. Before a production release, add consented and de-identified real tyre photographs to the documented OCR sample process, covering curved sidewalls, dirt, shadows, worn markings and supported brands.

## Backups and retention

`scripts/backup.sh` creates a PostgreSQL custom-format dump and a matching archive of local report images. Set `PG_BACKUP_URL`, `MEDIA_ROOT` and an encrypted `BACKUP_ROOT`, schedule it outside the application container, and regularly test restores. Archived reports older than `REPORT_RETENTION_DAYS` can be removed with:

```bash
python -m backend.app.maintenance
```

## Production deployment checklist

- Replace the JWT secret and seeded administrator password with managed secrets.
- Use PostgreSQL with encrypted backups and run `alembic upgrade head` before starting the API.
- Back up the database and report-image directory as one recovery set and test restores.
- Configure an HTTPS reverse proxy and restrict `ALLOWED_ORIGINS` to the deployed Angular URL.
- Configure authenticated SMTP with TLS and verify the sender domain's SPF, DKIM and DMARC records.
- Retain delivery and audit records according to the organisation's privacy policy.
- Monitor `/health`, `/ready`, structured request logs, failed deliveries and database health; never expose Mailpit in production.
- Run the delivery worker as a separately supervised process.
- Run `pytest`, `npm test -- --watch=false` and `npm run build` in CI before deployment.

## Roles

- **Administrator:** manages users, roles, branches, recipients and all reports.
- **Report Capturer:** used by technicians and salespeople to create and deliver reports.
- **Viewer:** read-only report and PDF access.
- **Pending:** public registration completed but no report access until an administrator assigns permissions.

## Explicit exclusions

No approval/rejection workflow, customer portal, payments, inventory, quotations, service booking, claim payout processing, chatbot, automated claim decisions or microservices.
