# Staff authentication starter design

## Intent

Create a conventional, maintainable full-stack starter for staff sign-in and account creation. The requested stack is React, FastAPI, and PostgreSQL. The repository currently contains only a README, so there is no existing application behavior or architecture to preserve.

## Goals

- Provide React pages for sign-in, sign-up, and forgotten-password recovery.
- Provide a versioned FastAPI authentication API backed by PostgreSQL.
- Support administrator, receptionist, housekeeping manager, and housekeeping staff roles.
- Let people register, but keep new accounts pending until an administrator assigns a role. Never let public registration grant administrative privileges.
- Require email verification before an administrator can activate a new account.
- Store passwords using a modern password hash; use one-time, expiring verification and password-reset tokens and avoid revealing whether an email address has an account.
- Give administrators a small interface to review pending accounts, activate them, and assign roles.
- Renew sessions securely and invalidate active sessions after password resets or role changes.
- Keep a clear frontend/backend boundary, migrations, automated tests, environment-based configuration, and local development instructions.

## Non-goals

- Hotel operations features beyond authentication and a minimal authenticated landing page.
- Social sign-in, multi-factor authentication, organization/tenant management, or production hosting setup.
- Public self-selection or self-assignment of privileged roles.

## Approaches

1. **Monorepo with separate apps (selected):** keep the React client and FastAPI API in distinct `apps/web` and `apps/api` folders, with backend tests and migrations close to the API. This is easy to run and evolve together while preserving clear boundaries.
2. **Separate repositories:** independently version and deploy the client and API. This adds coordination and setup overhead that is not justified for this currently empty, small project.

The user selected the monorepo approach.

## Proposed structure and behavior

- `apps/web`: React with TypeScript and Vite; sign-in, registration, email-verification, forgot-password, and reset-password screens; a minimal authenticated landing page; an administrator-only interface for reviewing pending accounts and assigning roles; reusable API client and form validation.
- `apps/api`: FastAPI application split into versioned route handlers, Pydantic schemas, services, SQLAlchemy models, and shared configuration/security/database modules.
- PostgreSQL schema changes managed with Alembic. Automated API tests cover registration, login, role checks, and password reset.
- A user has a unique email, a password hash, a role, and an account status. Public registration creates an unverified, pending account. A single-use verification link confirms the email but does not grant a role or activate the account. An administrator-only interface assigns one of the four roles and activates verified accounts. The first administrator is provisioned by a deliberate, documented administrative bootstrap command, not through public registration or a hard-coded credential.
- Email verification and password reset use cryptographically random, single-use tokens whose hashes alone are stored, with short expiries. The API returns generic responses for verification and reset requests where revealing account existence would be unsafe. Email delivery is configured through environment-based SMTP settings; development setup documents a local mail catcher rather than exposing tokens in API responses.
- Authentication uses secure, HTTP-only cookies with CSRF protection and secure session renewal. Server-side session state supports revocation after password resets and role changes. Cookie security and allowed client origins are configurable for local development versus production. Role checks are enforced by the API, not only by hiding frontend controls.
- Repository setup includes dependency manifests, an environment-variable example without secrets, local PostgreSQL startup instructions, migration/test commands, and concise README documentation. Secrets and real credentials are not committed.

## Constraints and decisions left to the builder

- Use the requested React, FastAPI, and PostgreSQL stack; choose conventional compatible libraries and pin dependencies.
- Configure the SMTP host and credentials outside source control. Email provider selection and production delivery infrastructure are not specified.
- Keep the first release focused on staff authentication; make no assumptions about hotel workflows after login.
- Secure renewal and revocation are required; choose exact session lifetimes, API paths, field validation rules, and implementation details consistently with the security goals above.
