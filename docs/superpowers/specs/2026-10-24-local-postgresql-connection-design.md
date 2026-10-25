# Dedicated local PostgreSQL connection design

## Intent

Connect the FastAPI backend and React frontend to PostgreSQL without depending on the unknown password for the existing PostgreSQL 18 service. The backend uses SQLAlchemy with the PostgreSQL psycopg driver, has an Alembic initial migration, and the frontend already proxies API requests to FastAPI.

## Approach

1. **Dedicated PostgreSQL cluster (selected):** initialize a new local PostgreSQL 18 data directory under `%LOCALAPPDATA%\StaffPortalPostgres`, listen only on `127.0.0.1:5433`, and create a `staff_portal` database/login with a fresh generated password stored only in the ignored root `.env`. Leave the existing PostgreSQL service on port 5432 and all its databases untouched. This uses installed PostgreSQL tools and doesn't require Docker or an existing administrator password.
2. **Use the existing server:** correct the app-role password through pgAdmin, then update `.env`. This cannot be completed because the current password is unknown and there is no saved admin login.

## Goals and constraints

- Configure the backend to connect to `localhost:5433/staff_portal` using the dedicated `staff_portal` login.
- Keep a freshly generated strong database password only in the ignored root `.env` and a temporary password file during initialization; never display, request, or commit it.
- Keep PostgreSQL bound to loopback only and retain its persistent data outside the repository.
- Document how to start/stop the dedicated database, migrate, and start both apps.
- Preserve the existing PostgreSQL models and migration. Do not modify the existing PostgreSQL service or its databases.
- Start the dedicated database, run the Alembic migration, and verify database readiness before reporting the end-to-end connection as complete.

## Builder calls

- The user selected a separate, isolated local PostgreSQL instance.
- Choose port 5433 because 5432 is already occupied by the existing service.
- Run both application servers through the Vite proxy and confirm a successful database-backed API readiness check.
