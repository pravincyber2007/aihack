# Hospitality sign-in page design

## Intent

Improve the existing React staff portal sign-in experience to match the requested clean white-and-green hospitality look, with a hospitality illustration on the left and the login form on the right.

This is a small UI enhancement to the already-running staff portal, not a new authentication system.

## Goals

- Keep email and password sign-in, a forgot-password link below the password field, and the existing sign-up option.
- Add a role dropdown for administrator, receptionist, housekeeping manager, and housekeeping staff.
- Validate the selected role against the authenticated account's server-assigned role. A dropdown must never grant or change permissions.
- Keep sign-out on authenticated pages, where it is available after a successful sign-in.
- Use a locally created illustration so the page doesn't rely on third-party image hosting.
- Preserve the existing FastAPI integration, responsive layout, and other registration, recovery, verification, dashboard, and admin flows.

## Approaches

1. **Local illustration (selected):** create a small inline SVG depicting a hotel/team scene, avoiding external requests and image licensing dependencies.
2. **Online hotel photo:** adds realistic photography but relies on external availability and sourcing; not selected.

## Builder calls

- Put role selection on the sign-in page and require its value to match the role returned by the backend. Server-side permissions remain authoritative.
- Retain the existing sign-out control in the authenticated portal header.
- Design the auth page with a white canvas, restrained green accents, left-side illustration, and right-side form, adapting to a stacked layout on small screens.
