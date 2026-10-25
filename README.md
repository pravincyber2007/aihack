# Haven Staff Portal

Smart hotel housekeeping task management with role-based dashboards, built as a monorepo:

- `apps/web` — React, TypeScript, and Vite
- `apps/api` — FastAPI, SQLAlchemy, and Alembic
- PostgreSQL — accounts, sessions, rooms, guest stays, tasks, and assignment history
- Mailpit — local SMTP inbox for password-reset links

## Roles and dashboards

| Role | Dashboard | Responsibility | Access limits |
| --- | --- | --- | --- |
| Housekeeping Manager | `/manager` | Allocates staff to floors, monitors workload, and handles escalations (retry, assign, cancel); reviews declined and timed-out offers, inspects rooms, configures assignment rules | Does not routinely assign every individual task; the system offers tasks automatically |
| Housekeeping Staff | `/staff` | Reviews offers, accepts or declines tasks, performs work, and updates status (mobile-first) | Only their own offers and assigned tasks, with the information needed to do them |
| Receptionist | `/reception` | Checks guests in to available rooms and out again, checks task and room-readiness status, and submits requests for guests | No employee administration; sees only a guest's name, last 4 phone digits, and stay dates |
| Guest | `/guest` | Enters their registered phone number, submits housekeeping requests, and views their status | Only their own requests and status, for the matched stay |

Employees create an account with one of the three staff roles and can sign in immediately. Guests use **Continue as Guest** on the sign-in page. All role and privacy rules are enforced by the API, not only the UI.

**Automatic assignment.** Each new request gets a priority from the rules shown on the manager's settings tab. The system offers it to one on-shift staff member at a time, ranked by floor distance and then current workload, searching adjacent floors up to the configured limit. Declines and timeouts (checked every 10 seconds) trigger the next offer. After the configured number of attempts, or when no one is eligible, the task appears as an alert for the manager. A task can only ever have one confirmed owner.

**Guest access and demo data.** A guest enters their registered phone number; if it matches exactly one current stay, they see their room and services. Unknown numbers and numbers with several stays get the same message and no room details, and repeated failed attempts from one device are throttled. There is no second verification step, so anyone who knows a guest's number can request services for that room. Receptionists create stays at check-in (room must be vacant and Ready; one current stay per phone number). Check-out ends the stay, signs the guest out, marks the room Cleaning Required, and sends a checkout clean to housekeeping automatically. `python -m app.demo_seed` loads clearly labelled DEMO rooms (101–510) and a few demo stays.

## Requirements

- Python 3.12 or newer
- Node.js 20 or newer
- PostgreSQL 18 installed at `C:\Program Files\PostgreSQL\18` (for the local database scripts), or Docker Desktop for an optional container

## Start the dedicated local PostgreSQL database

The API connects through SQLAlchemy and Psycopg. A dedicated PostgreSQL 18 cluster can run on `127.0.0.1:5433` without changing the existing PostgreSQL service on port 5432. The startup script generates a strong local password, stores it in the ignored root `.env`, and configures the application login without superuser privileges.

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
.\scripts\start-local-postgres.ps1
```

The database files are stored outside the repository at `%LOCALAPPDATA%\StaffPortalPostgres\data`. To stop this dedicated instance, run:

```powershell
.\scripts\stop-local-postgres.ps1
```

The existing PostgreSQL service and its databases are left untouched.

### Optional Docker PostgreSQL

If you prefer a container instead of the dedicated local PostgreSQL service, configure `POSTGRES_PASSWORD` in `.env` and set `DATABASE_URL` to use port `5433`, then run:

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
python -m app.demo_seed        # DEMO rooms and guest stays
uvicorn app.main:app --reload
```

Demo guest numbers: `+1 555 010 0305` (room 305), `+1 555 010 0208` (room 208), and `+1 555 010 0999`, which has two stays and shows the "cannot match" path.

After the API starts, verify that it can reach PostgreSQL at `http://localhost:8000/health/ready`. It returns `{"status":"ready","database":"connected"}` only after a successful database query. If the connection is refused, check that PostgreSQL is running and the host/port in `.env` are correct; an authentication error usually means the username or password does not match the role created in pgAdmin.

In a second terminal, install and start the frontend:

```powershell
cd apps\web
npm install
npm run dev
```

Open `http://localhost:5173` for the app. The API is available at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`. Password-reset email requires SMTP settings in `.env`; Mailpit is available for local email testing when Docker is installed.

## API overview

All endpoints are versioned under `/api/v1`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/auth/csrf` | Issue a CSRF token for the browser |
| `POST` | `/auth/register` | Create an active employee account with the selected role |
| `POST` | `/auth/login` | Sign in and create a secure server-side session |
| `POST` | `/auth/refresh` | Rotate and renew the current session |
| `GET` | `/auth/me` | Return the authenticated account |
| `POST` | `/auth/logout` | Revoke the current session |
| `POST` | `/auth/forgot-password` | Request a password-reset email |
| `POST` | `/auth/reset-password` | Set a new password and revoke old sessions |
| `GET` | `/tasks`, `/tasks/summary`, `/tasks/alerts`, `/tasks/{id}/history` | Task monitoring and escalations (manager) |
| `*` | `/manager/...` | Staff floors, settings, offers, room readiness, retry/assign/cancel (manager) |
| `*` | `/staff/...` | Own shift, offers, and tasks (housekeeping staff) |
| `*` | `/reception/...` | Room search, occupancy, check-in, check-out, requests, progress (receptionist) |
| `*` | `/guest/...` | Phone-number access, own room, own requests (guest) |

State-changing requests require the CSRF cookie and `X-CSRF-Token` header. The frontend handles this automatically. Sign-in's role selection is checked against the account's assigned role by the API; it cannot grant access or change a role. Sign-out is available from the authenticated portal header.

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
