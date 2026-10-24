# Local PostgreSQL connection design

## Intent

Connect the FastAPI backend to the PostgreSQL 18 server already running on the developer's machine. The backend currently uses SQLAlchemy with the PostgreSQL psycopg driver and has an Alembic initial migration, but its example `app` credentials are rejected by this server and no root `.env` exists.

## Approach

Use the existing local PostgreSQL service to create a dedicated `staff_portal` database and login via the developer's PostgreSQL administrator access. A separate Docker database is not a fit here because Docker is unavailable and PostgreSQL is already listening on port 5432.

## Goals and constraints

- Configure the backend to connect to `localhost:5432/staff_portal` using the dedicated `staff_portal` login.
- Keep the database password local in the ignored root `.env`; never request it in chat or commit it.
- Document database/user creation in pgAdmin, migration application, and a simple connection check.
- Preserve the existing PostgreSQL models and migration. Do not alter or drop data from other databases.

## Builder calls

- The developer chooses a strong password locally and enters it into pgAdmin and `.env`.
- Update `.env.example` and README setup instructions to reflect the local PostgreSQL server.
- A successful SQLAlchemy connection and applied Alembic migration are the acceptance checks.
