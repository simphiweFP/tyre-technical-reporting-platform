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
3. `feat: add AI-assisted tyre data extraction and PDF reporting`
   - Gemini structured image analysis, operator verification, image compression and branded PDF generation.
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

## AI-assisted capture and PDF generation

Captured or uploaded inspection images are compressed in the Angular client and sent to the authenticated FastAPI endpoint `POST /api/v1/reports/analyse-image`. The backend uses Gemini structured JSON output to extract tyre/vehicle values and an optional per-photo inspection comment. AI values are suggestions only: the technician or salesperson remains responsible for verifying the final report data.

The guided capture flow is **Report details → Take photos → Tyre & vehicle → Preview**. Required fields and photos are validated by the API before submission. The generated Royal Tyres PDF uses the approved header/footer artwork, the technical-report field table, one evidence image per page and the stored AI comment when one exists.

Configure Gemini only through deployment secrets or the local uncommitted `.env` file:

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3-flash-preview
GEMINI_TIMEOUT_SECONDS=30
# Optional production secret-file path:
GEMINI_API_KEY_FILE=
```

## Email delivery

Administrators maintain approved third-party recipients. Technicians and salespeople select a recipient in Preview and send the generated PDF directly; there is no approval or rejection workflow. The API attempts the first SMTP delivery immediately so users receive direct feedback. Failed/retrying attempts remain durable and can be processed again by the delivery worker.

Every delivery stores an immutable snapshot of the email subject/body and exact PDF bytes plus SHA-256 hash. Delivery Centre therefore shows the historical attachment that was sent rather than regenerating a potentially changed report. Sent emails can be followed up with user-written text using standard reply-thread headers. Failed deliveries expose their SMTP error and can be retried. Soft-deleted delivery records remain in the database for audit history but are hidden from active lists. Docker Compose includes Mailpit for safe local email testing at `http://localhost:8025`.

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

AI-extracted values are always suggestions requiring operator verification. Before a production release, validate Gemini extraction with consented/de-identified real tyre photographs covering curved sidewalls, dirt, shadows, worn markings, tread gauges and the supported photo categories.

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


## Mobile device verification

The Angular capture experience is mobile-first and responsive, but physical-device sign-off must still be completed before production. Verify at least one current Android device and one current iPhone using the deployed HTTPS environment. Test camera capture, gallery upload, permission prompts, image compression, offline/online transitions, long forms, tyre-position selection, PDF preview/download and email submission. Browser emulation is useful for layout checks but is not a substitute for real-device camera testing.

## Production security notes

- Keep `.env` and real credentials out of Git.
- Prefer secret files or the deployment secret store for JWT, SMTP, Microsoft and Gemini credentials.
- The API is the single owner of Alembic migrations at startup; Docker does not run a second migration command.
- Use PostgreSQL in production and HTTPS at the reverse proxy.
- Restrict CORS to the deployed Angular origin.
- Review delivery/audit retention with the business before enabling automatic cleanup.
- Run backend tests, Angular tests/build and container validation in CI on every change.

## Claims Management

The backend seeds both administrators after applying migrations at startup. The second administrator defaults to `claims@royaltyres.co.za` with the **Claims Administrator** role. Configure `SEED_CLAIMS_ADMIN_EMAIL` and `SEED_CLAIMS_ADMIN_PASSWORD`; a blank claims password uses `SEED_ADMIN_PASSWORD`. Existing account passwords and assignments are preserved on restart. You can also create another user under **Administration → Users** with the **Claims Administrator** role. Successfully emailed technical reports are assigned automatically. Open **Claims Management** from the sidebar to view the same case. Claims administrators see only their assigned claims and own tracking updates, credit instructions, settlement and claim-report emails. The original administrator views progress and exports, and can manage users, import historical workbooks and reassign claims; tracking and settlement controls are read-only for that role. Technical-report delivery status and claim-tracking progress are stored separately.

The four screens follow the Claims Management workbook: **Claim Tracker**, **Instruction to Credit**, **Supplier Scorecard**, and **Other Metrics**. All 23 tracker columns and 15 credit-instruction columns are included in the app and exports. Customer credit percentage is entered manually from 0 to 100; remaining tread percentage is calculated as RTD / OTD × 100. Tyre size is captured separately from rim size. Supplier suggestions come from `SUPPLIER_JSON_PATH` (default `backend/data/suppliers.json`), with manual entry supported. Mock supplier codes must be replaced with real supplier codes before downstream integration.

Administrators can import the source `.xlsx` workbook and select a claims owner. Valid `I000001`-format references are retained; existing references are skipped without overwriting. Rows without references or with invalid values are reported for correction. Tracker and instruction suppliers can differ, and source rows are retained for traceability. Workbook scorecards and metrics are recomputed from claim records.

PDFs include the technical report, claim tracker, credit instruction, rejection report and supplier scorecard. Email delivery saves the PDF snapshot, recipient, CC addresses and delivery outcome; retries use that same snapshot. Credit instruction snapshots retain the values at issue time. Credits and supplier offsets are recorded manually through references, dates and amounts.

Scorecard acceptance/rejection rates use all claims in the selected period. Response days run from supplier submission to feedback; resolution days run from claim date to customer credit date. Recovered credit value sums entered amounts only for completed supplier offsets, with missing amounts highlighted. Other metrics show under-review claims, outstanding supplier offsets, unpassed customer credits, and highest/lowest claim suppliers and customers (including ties).

Deploy the backend migration before opening the new screens:

```bash
python -m alembic -c backend/alembic.ini upgrade head
```

To apply migrations and seed both administrators manually from the repository root:

```bash
python -m backend.app.seed
```

When updating a local checkout, fetching downloads commits but does not update your working files. Use `git switch tyre-technical-reporting` followed by `git pull --ff-only origin tyre-technical-reporting`, then restart/rebuild the app.

### Automatic continuation

Technical reports enter Claims Management after a successful technical-report email, under the seeded Claims Administrator. Pending, failed and unsent reports stay with the first administrator for delivery correction and retry. A successful retry also triggers handover. Previously sent reports are added when the backend starts or the seed runs. Drafts and archived reports remain outside this queue; existing cases and assignments are preserved. If the configured claims administrator is unavailable and there is more than one active claims administrator, use manual handover to choose the owner. Disable automatic handover with `CLAIMS_AUTO_HANDOVER_ENABLED=false` if needed.

Customer, invoice and tyre details carry forward from the original report. Corrections to tread depth, tyre size and damage synchronize while their claim values still match the original source; values already edited by the Claims Administrator are preserved. Tyre size is captured separately from rim size and is populated by tyre-image extraction.

Saving an accepted decision with the manually entered customer credit percentage creates the credit instruction automatically. Repeated saves with unchanged instruction values do not create duplicates. Revised instructions retain earlier snapshots; the inbox shows the latest version and receipt of an outdated version is blocked.

The default tracker is a compact work list showing each claim's next action. All workbook fields remain available through the separate **View** screen and exports. Feedback and settlement dates default to the local date when the relevant event is recorded and remain editable. Financial percentages, credit references and recovered amounts remain entered by the operator.
