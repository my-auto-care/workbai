# Workbai Phase 1: Staff Check-in

## Goal

Deliver a secure browser-based staff Check-in workflow at the requested future test hostname, `test.workbay.autorepairsolutions.ai`. A signed-in service advisor or administrator will enter the vehicle, capture the customer's stated concern, select the active inspection template, assign a technician, and create a **pending** Workbai inspection session. The existing technician and queue/report workflows continue the session after this handoff.

## Implementation

The feature belongs in the existing Next.js dashboard and FastAPI backend. The dashboard becomes a token-mediating backend: the browser talks only to the same-origin dashboard; server code retrieves an Auth0 access token and sends it to the internal FastAPI service. The backend validates Auth0 JWTs through the configured JWKS, resolves the authenticated `auth0_id` to an active Workbai user, and derives shop and role server-side. Client-provided shop scope is never trusted.

The Check-in route exposes two backend operations:

- `GET /check-in/options`: returns the authenticated advisor/admin’s own shop, active technicians in that shop, and existing checklist template versions.
- `POST /check-in/sessions`: creates a Workbai `pending` session only after validation of manual vehicle information, stated concern, selected template, and in-scope assigned technician.

The backend’s existing session, checklist, media, and voice-token routes receive actor-and-shop enforcement so the new HTTPS browser surface cannot use the former unauthenticated endpoints. CORS is configured from explicit environment origins rather than wildcard credentialed CORS. The test Compose stack runs `alembic upgrade head` as a one-shot migration service before it starts the API.

The dashboard uses a restrained mechanic-confident visual system: cream canvas, navy text, circuit-cyan primary action, semantic inspection status colors, one primary action, no default gray block buttons, and no ambient assistant on this consent-sensitive flow.

## Intentional exclusions

This Phase 1 build does **not** store customer name, phone, customer portal identity, Digital Glovebox links, DVIPlus records, plate images, consent receipts, or vehicle-specific AI recommendations. It also does not freeze the final inspection sheet. Until their legal/data and cross-product contracts are approved, these are separate build gates rather than placeholder behavior. The test runtime does not register billing, voice-inspection, plate/VIN lookup, transcript processing, or experimental vehicle-AI routes; they are explicitly disabled by default rather than exposed half-finished.

The UI therefore uses confirmed manual vehicle entry. Plate/VIN scanning will be a later explicit-consent, transient-processing flow with manual fallback. Checklists are available shared templates in this Phase 1 data model; active/retired, shop-owned template governance is a later migration rather than a claim the UI cannot support.

## Project structure

- `backend/app/auth.py`: Auth0 JWT verification and database-derived actor/scope dependency.
- `backend/app/api/checkin.py`: advisor/admin-only check-in bootstrap and pending-session creation.
- `backend/app/api/sessions.py`: shop- and role-scoped inspection lifecycle APIs.
- `backend/app/api/checklists.py`: staff read/admin write access protection.
- `dashboard/lib/`: Auth0 client and server-only internal API client.
- `dashboard/app/check-in/`: server-gated Check-in page and client form.
- `dashboard/app/api/check-in/`: same-origin dashboard command route.
- `dashboard/proxy.ts`: Auth0 SDK route and rolling-session middleware.
- `dashboard/Dockerfile` and Compose changes: future supervised dashboard runtime.

## Delivery gates

The isolated candidate must pass Python compilation, Next lint/build, and focused source checks before it is committed. No deployment occurs during this build phase. The test host still requires a separate service/process, explicit vhost, valid certificate, Auth0 web callback/logout/origin registration, secrets in the runtime store, real user/shop/technician/checklist seed data, and a Cloudflare DNS record before an after-hours test release can be considered.
