# RT-Auth configuration

The Technical Claim app uses RT-Auth's authorization-code + PKCE flow. Its existing login layout shows a company sign-in button when enabled. RT-Auth handles the credential form and returns to the dashboard. Business screens and styling are unchanged.

The registered callback is `https://192.168.1.236:8020/api/auth/callback`. This route is implemented outside the usual `/api/v1` prefix to match the registration exactly. The HTTPS host/reverse proxy must route both `/api/auth/callback` and `/api/v1` to this API, and serve the Angular app with its normal SPA fallback.

## Configure the server

Install the updated backend dependencies from the repository root, in the app's virtual environment:

```powershell
python -m pip install -e ".[dev]"
```

Add these values to the app's own `.env`, using the client secret returned by RT-Auth registration. Never commit the secret or send it to the browser.

```dotenv
AUTH_ENABLED=true
AUTH_ISSUER_URL=https://192.168.1.236:8010
AUTH_CLIENT_ID=RT-TechnicalClaim
AUTH_CLIENT_SECRET=<registered secret>
AUTH_REDIRECT_URI=https://192.168.1.236:8020/api/auth/callback
AUTH_CA_FILE=L:/Projects/certs/rootCA.crt
PUBLIC_APP_URL=https://192.168.1.236:8020
ALLOWED_ORIGINS=https://192.168.1.236:8020
JWT_SECRET=<strong random secret of at least 32 characters>
```

`PUBLIC_APP_URL` is the URL serving Angular; adjust it if the frontend is hosted separately. Keep frontend and API on the same HTTPS hostname so the browser can send the API's HttpOnly session cookie and read the CSRF cookie. A different frontend port needs its exact origin in `ALLOWED_ORIGINS`. The certificate must cover the chosen hostname/IP, and browsers must trust the company root CA. Certificate verification is never disabled.

The API runs migrations on startup; the new migration creates server-side login transactions and company sessions. Existing users, report IDs, claims, ownership and history remain intact. RT-Auth is disabled by default until the deployment config enables it.

## Test locally before deployment

Keep the server callback registered. Add this **additional** redirect URI to the same RT-Auth client through its supported client registration settings:

```text
https://localhost:4200/api/auth/callback
```

Use a test database and an assigned test user. In the app's root `.env`, retain the issuer, client ID, client secret, trusted issuer CA and strong JWT secret above, and override:

```dotenv
AUTH_ENABLED=true
AUTH_REDIRECT_URI=https://localhost:4200/api/auth/callback
PUBLIC_APP_URL=https://localhost:4200
ALLOWED_ORIGINS=https://localhost:4200
```

Start the API from the repository root in its virtual environment:

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, from the repository root, start the HTTPS frontend with a certificate covering `localhost` and a matching private key. The browser must trust its issuing CA. These paths are examples; use your actual local certificate paths:

```powershell
npm run start:rt-auth --prefix frontend -- --ssl-cert C:/certs/localhost.crt --ssl-key C:/certs/localhost.key
```

Open **https://localhost:4200/login**. This development configuration uses `/api/v1` and proxies all `/api/**` requests, including the callback, to the local API. The browser therefore receives Secure session and CSRF cookies on the same HTTPS origin. The API's connection to RT-Auth still validates `AUTH_CA_FILE`; do not disable TLS checks. The normal HTTP development command remains available for local authentication mode.

Check `https://localhost:4200/api/v1/auth/config` returns `{"provider":"rt-auth"}`. If it returns `local`, check the root `.env` and restart the API. If it fails, the login page shows a retryable settings error. The button must say **Continue with RT-Auth**. Complete the acceptance checks below locally, including sign-in, an authorized write and sign-out. Check existing-account links and branch mappings above if sign-in succeeds but access is denied.

The workspace tests validate the mocked provider flow and local HTTPS proxy routing. A successful sign-in against your real RT-Auth server still needs the registered local callback, trusted certificates, client secret and assigned user on your machine.

## Roles and branch access

In RT-Auth's admin console select **RT-TechnicalClaim**, then **Manage Roles**. Register these exact codes and assign the appropriate role to each user:

- `administrator`
- `claims_administrator`
- `report_capturer`
- `viewer` only if read-only access is needed

Unknown or missing role codes produce a `pending` local profile with no business permissions. The app currently exposes one effective role; when multiple recognized roles are assigned, precedence is administrator, claims administrator, report capturer, viewer. Assign one role per user to match the app's existing workflow.

Assign companies and warehouses to the user for this client. Explicitly map the local branch codes to those assignments in the app's `.env`. For example, only if these codes match the actual records:

```dotenv
AUTH_BRANCH_SCOPES={"PHX":{"company":"RTC","warehouse":"RTCPHX"}}
```

Use the actual local branch codes (see the app's branch management screen) and RT-Auth warehouse codes. Warehouse codes are interpreted within their company. Missing mappings, empty companies or missing warehouse assignments grant no branch data access, including report, image, delivery and claim queries. An administrator role does not bypass these assignments. New branches and changes to report branches must stay within the authorized mappings.

## Link existing accounts

For a first login with an email already used locally, explicitly link the stable RT-Auth user UUID to that local account:

```dotenv
AUTH_USER_LINKS={"<RT-Auth user UUID>":"existing.user@royaltyres.co.za"}
```

Get the UUID from RT-Auth's user details or its documented backend-only admin lookup. This preserves the existing local user ID and claim ownership. Email matching alone does not authorize linking; conflicting existing provider links are rejected. A new identity with a new email receives a new local profile, and its centrally assigned roles determine access.

Company account creation, passwords and role assignments are managed in RT-Auth. The existing local account/password endpoints are blocked when company authentication is enabled. Local profile details, job titles and app-specific assignment records remain local. Password and Microsoft sign-in cannot bypass company authentication.

## Sessions and validation

Provider ID and refresh tokens never enter browser storage or callback URLs. The app validates RS256, the matching JWKS key, issuer, exact audience, expiry, token type and identity claims. JWKS is cached for one hour and refreshed once for an unknown key. Login state and PKCE verifier are stored in a short-lived server transaction; callbacks consume it once.

The browser receives an opaque Secure/HttpOnly/SameSite cookie. Refresh tokens are encrypted in the database using a key derived from `JWT_SECRET`; changing that secret invalidates existing company sessions. Writes require a CSRF header matching a session-bound cookie. Local sessions last eight hours; provider renewal happens at most once per twenty minutes of activity. Temporary provider outages leave an otherwise valid session usable; invalid refresh responses end the session. Sign-out deletes the local session and calls `/revoke` with the provider's `refresh_token`, scoped to this client. If RT-Auth is unreachable, local logout still completes.

## Server acceptance check

1. Verify `/api/v1/auth/config` returns `rt-auth` and the login button opens RT-Auth.
2. Sign in using an assigned test account; confirm return to the existing dashboard or claims screen.
3. Confirm current-user identity, role and branch access. A user without company/warehouse assignments must see no branch data.
4. Check report capture, claim access, PDF/Excel email attachments and Delivery Centre within the assigned branches.
5. Sign out and verify the API rejects the old session. Signing out must not end sessions in other apps.

Automated tests use a mock provider and signed RSA tokens. Live TLS, central refresh/revoke, reverse-proxy routing and assigned users must also be tested on the company server; the internal RT-Auth service is not reachable from the development workspace.
