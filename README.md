# Haven Staff Portal

A full-stack staff authentication starter built as a monorepo:

- `apps/web` — React, TypeScript, and Vite
- `apps/api` — FastAPI, SQLAlchemy, and Alembic
- PostgreSQL — account, verification-token, and session storage
- Mailpit — local SMTP inbox for account verification and password-reset links

Public sign-up creates a pending, unverified account. After verifying the email, a user waits for an administrator to assign a role. Roles are never selected during public registration.

## Requirements

- Python 3.12 or newer
- Node.js 20 or newer
- PostgreSQL 16 or newer (or Docker Desktop for an optional container)

## Connect to local PostgreSQL

The API connects through SQLAlchemy and Psycopg using `DATABASE_URL` in the root `.env`. To create a dedicated database on a local PostgreSQL server with pgAdmin:

1. Connect to PostgreSQL as an administrator in pgAdmin.
2. Under **Login/Group Roles**, create a login named `staff_portal`. Set a strong password in the pgAdmin password field and leave superuser and database-creation privileges disabled.
3. Under **Databases**, create a database named `staff_portal` and set its owner to `staff_portal`.
4. From the repository root, copy the example configuration and edit the database URL with the password you just set:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Set `DATABASE_URL` to `postgresql+psycopg://staff_portal:<your-password>@localhost:5432/staff_portal`. Use a URL-encoded password if it contains reserved URL characters. Do not share or commit `.env`.

The existing local PostgreSQL service already uses port 5432. Do not start another PostgreSQL server on that same port.

### Optional Docker PostgreSQL

If you prefer a container instead of the local PostgreSQL service, configure `POSTGRES_PASSWORD` in `.env` and set `DATABASE_URL` to use port `5433`, then run:

```powershell
docker compose up -d db mailpit
```

The compose file publishes its PostgreSQL container on port 5433 to avoid conflicting with the local server. Mailpit is available at `http://localhost:8025`.

## Install and run

Install and start the API:

```powershell
cd apps\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic upgrade head
uvicorn app.main:app --reload
```

After the API starts, verify that it can reach PostgreSQL at `http://localhost:8000/health/ready`. It returns `{"status":"ready","database":"connected"}` only after a successful database query. If the connection is refused, check that PostgreSQL is running and the host/port in `.env` are correct; an authentication error usually means the username or password does not match the role created in pgAdmin.

In a second terminal, install and start the frontend:

```powershell
cd apps\web
npm install
npm run dev
```

Open `http://localhost:5173` for the app. The API is available at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`. Account-verification and password-reset email requires SMTP settings in `.env`; Mailpit is available for local email testing when Docker is installed.

## Create the first administrator

After migrations have run, use the API virtual environment and run this from `apps\api`:

```powershell
python -m app.cli create-admin
```

The command prompts for the administrator email and password. It refuses to create another administrator if one already exists.

## API overview

All endpoints are versioned under `/api/v1`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/auth/csrf` | Issue a CSRF token for the browser |
| `POST` | `/auth/register` | Register an unverified, pending account |
| `POST` | `/auth/verification/resend` | Resend an email-verification link |
| `POST` | `/auth/verify-email` | Verify an email with a single-use token |
| `POST` | `/auth/login` | Sign in and create a secure server-side session |
| `POST` | `/auth/refresh` | Rotate and renew the current session |
| `GET` | `/auth/me` | Return the authenticated account |
| `POST` | `/auth/logout` | Revoke the current session |
| `POST` | `/auth/forgot-password` | Request a password-reset email |
| `POST` | `/auth/reset-password` | Set a new password and revoke old sessions |
| `GET` | `/admin/users/pending` | List verified accounts awaiting approval |
| `PATCH` | `/admin/users/{user_id}/role` | Assign a role and activate a verified account |

State-changing requests require the CSRF cookie and `X-CSRF-Token` header. The frontend handles this automatically. Sign-in's role selection is checked against the account's assigned role by the API; it cannot grant access or change a role. Administrator permissions are checked by the API as well as by the UI. Sign-out is available from the authenticated portal header.

## Configuration

Configure the database, browser origins, cookie security, and SMTP settings in `.env`. Never commit `.env` or production credentials. For production, set `SESSION_COOKIE_SECURE=true`, use HTTPS, and configure trusted CORS origins and an authenticated SMTP provider.

## Database migrations

Run from `apps\api`:

```powershell
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "describe the change"
```

## Tests and production build

Run the API tests from `apps\api`:

```powershell
pytest
```

Build and type-check the frontend from `apps\web`:

```powershell
npm run build
```
