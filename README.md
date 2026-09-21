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

## Roles

- **Administrator:** manages users, roles, branches, recipients and all reports.
- **Report Capturer:** used by technicians and salespeople to create and deliver reports.
- **Viewer:** read-only report and PDF access.

## Explicit exclusions

No approval/rejection workflow, public registration, customer portal, payments, inventory, quotations, service booking, claim payout processing, chatbot, automated claim decisions or microservices.
