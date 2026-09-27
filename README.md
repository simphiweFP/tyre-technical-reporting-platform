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
   - Server report persistence, database-backed Base64 image storage, full report APIs, public registration, Microsoft account linking, user administration, password recovery, durable email queue, analytics and operational protections.

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
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload
pytest
```

Starting the API automatically runs all pending Alembic migrations from
`backend/migrations` before the server begins accepting requests. If a migration
fails, API startup fails so the application cannot run against an outdated schema.

The seeded development administrator defaults are defined in `.env.example`. Change them before any shared deployment.

## Angular frontend

The feature-based Angular application uses lazy-loaded features, route-level role guards, an authentication interceptor and a responsive application shell.

```bash
cd frontend
npm install
npm start
```

The frontend expects the API at `http://localhost:8000/api/v1`. Reports, drafts and compressed report images are stored in PostgreSQL. Image bytes are Base64-encoded in `report_images.base64_data` and are only served through authenticated endpoints.

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

Delivery requests are stored before returning to the user. The `delivery-worker` service processes the durable queue, uses row locking to prevent two workers taking the same item and schedules automatic retries before marking a delivery failed. Docker Compose includes Mailpit for safe local email testing at `http://localhost:8025`.

For local Docker development, leave:

```env
SMTP_HOST=localhost
SMTP_DOCKER_HOST=mailpit
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=false
EMAIL_FROM=technical-reports@royaltyres.co.za
EMAIL_FROM_NAME=Royal Tyres Technical Reports
```

For a real SMTP server, configure the credentials in the deployment `.env`. When the API and delivery worker run in Docker, `SMTP_DOCKER_HOST` is the hostname used inside the containers.

Microsoft 365 / Outlook example:

```env
SMTP_HOST=smtp.office365.com
SMTP_DOCKER_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your-mailbox@yourdomain.co.za
SMTP_PASSWORD=your-app-or-smtp-password
SMTP_USE_TLS=true
EMAIL_FROM=your-mailbox@yourdomain.co.za
EMAIL_FROM_NAME=Royal Tyres Technical Reports
```

Gmail / Google Workspace example:

```env
SMTP_HOST=smtp.gmail.com
SMTP_DOCKER_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-mailbox@yourdomain.co.za
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
EMAIL_FROM=your-mailbox@yourdomain.co.za
EMAIL_FROM_NAME=Royal Tyres Technical Reports
```

Do not commit the real `.env` file or SMTP password. After restarting the API and `delivery-worker`, an administrator can use the existing recipient **Test** action (`POST /api/v1/recipients/{recipient_id}/test`) to verify SMTP before sending a technical report. For production, also verify the sender domain's SPF, DKIM and DMARC records.
## PDF branding and OCR acceptance

The supplied Royal Tyres header and footer artwork is repeated on every generated PDF page. `ROYAL_TYRES_REPORT_HEADER_PATH` and `ROYAL_TYRES_REPORT_FOOTER_PATH` can replace the bundled artwork without a code change. Set `ROYAL_TYRES_COMPANY_DETAILS` and `ROYAL_TYRES_PDF_DISCLAIMER` to the approved business and legal wording.

OCR values are always suggestions requiring operator confirmation. Parser fixtures cover common spacing and recognition noise. Before a production release, add consented and de-identified real tyre photographs to the documented OCR sample process, covering curved sidewalls, dirt, shadows, worn markings and supported brands.

## Backups and retention

Report images are stored in PostgreSQL as Base64 together with their metadata, so the database is the complete persistence layer for technical reports and their photographs. `scripts/backup.sh` creates a PostgreSQL custom-format dump; no separate image-directory backup is required. Set `PG_BACKUP_URL` and an encrypted `BACKUP_ROOT`, schedule it outside the application container, and regularly test restores. Archived reports older than `REPORT_RETENTION_DAYS` can be removed with:

```bash
python -m backend.app.maintenance
```

Each backup includes a `SHA256SUMS` manifest. Run `sha256sum -c SHA256SUMS` before every restore test. The administration System & Audit screen reports database, delivery-worker heartbeat and delivery-queue health; a worker becomes stale after 30 seconds without a heartbeat.

## Production deployment checklist

- Replace the JWT secret and seeded administrator password with managed secrets.
- Use PostgreSQL with encrypted backups. API startup applies pending migrations automatically.
- Back up PostgreSQL and test restores; report images are included in the database dump.
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
