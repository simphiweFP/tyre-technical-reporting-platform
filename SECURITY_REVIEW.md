# Production Security Review

Date: 2026-09-30

## Scope

Royal Tyres Technical Reporting Platform: Angular frontend, FastAPI API, PostgreSQL, Gemini image analysis, Microsoft SMTP delivery, Microsoft sign-in, delivery worker and generated PDFs.

## Controls present

- Short-lived JWT access tokens with rotating/revocable refresh sessions.
- API-side role and ownership checks.
- PostgreSQL required in production.
- HTTPS required by production configuration and Nginx example.
- Restricted CORS validation; wildcard origins are rejected in production.
- Request IDs, rate limiting, HSTS, CSP, frame denial, no-referrer and nosniff headers.
- Password hashing and expiring password-reset tokens.
- Secrets can be loaded from files for JWT, SMTP, Microsoft and Gemini.
- Production startup rejects default JWT/admin credentials, missing SMTP password and missing Gemini key.
- Report/archive and delivery soft-delete patterns preserve audit history.
- Sent email/PDF snapshots are immutable and SHA-256 hashed.
- Delivery and administrative activity are audited.

## Release blockers

Before production deployment, verify:

1. Real `.env` / secret files are outside Git and readable only by the service account.
2. Rotate any credentials that have ever been pasted into chats, tickets or screenshots.
3. Use a dedicated Microsoft 365 service mailbox with SMTP AUTH limited to that mailbox where possible.
4. Confirm SPF, DKIM and DMARC for the sending domain.
5. Use an organisation-owned Gemini project/API key with billing/quotas and key restrictions appropriate to the deployment.
6. Restrict `ALLOWED_ORIGINS` and `PUBLIC_APP_URL` to the deployed HTTPS URL.
7. Keep PostgreSQL off the public internet; allow only the app/backup hosts.
8. Encrypt backups and perform a restore test.
9. Run the manual provider smoke workflow in the non-production environment.
10. Complete Android and iPhone physical-device sign-off.

## Residual risks

- Base64 image storage increases database size and backup volume. This is an accepted business requirement; monitor growth and retention.
- The in-process HTTP rate limiter is suitable for a single API instance. If the API scales horizontally, move rate limiting to the reverse proxy or a shared store.
- SweetAlert2 is loaded from a pinned CDN version. For the strongest supply-chain posture, package it into the Angular bundle in a future dependency refresh.
- Gemini output is probabilistic. The application must continue treating extracted values/comments as suggestions that users verify.
- Offline edits use optimistic timestamp conflict detection; conflicts require user review rather than silent last-write-wins.

## Security regression checks

- Backend: `python -m ruff check backend && python -m pytest`
- Frontend: `npm test -- --watch=false && npm run build`
- Production dependencies: `npm audit --omit=dev --audit-level=high`
- Real providers: manually run **Provider Smoke** using the protected `provider-smoke` GitHub environment.
