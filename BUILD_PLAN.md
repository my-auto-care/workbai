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

## Phase 1.1: technician inspection workspace

The next build slice snapshots the selected available template and version when an advisor starts a visit, then gives only the assigned technician a controlled, template-driven workspace. An item response may be `good`, `poor` (**Needs attention** in the UI), or `na`; Needs attention and N/A require a written reason. Templates must have nonempty, globally unique section and item identities, and any selected observation must be one declared in that visit’s own snapshot. The server stores one current response per item and permits a technician to submit only when all snapshot items have an explicit result. Submission means **submitted for advisor review**, not customer delivery, approval, pricing, repair authorization, quality control, or a completed repair.

The bundled Basic Vehicle Inspection Checklist is a named provisional test template. It is not represented as, or substituted for, the controlled inspection sheet. No final field locations, torque values, thresholds, evidence policy, AI diagnosis, plate scan, or customer-facing DVI release will be inferred or enabled by this slice.

## Phase 1.2: Advisor Review Workbench

The next allowed slice is a single-visit, advisor/admin-only workbench for a technician-submitted provisional inspection. It shows the customer’s original concern first, then only human-attested Needs attention responses for an explicit, written human disposition: **Safety**, **Maintenance**, **Visit concern**, **Monitor**, **No action**, or **Needs clarification**. Good and N/A work remain compact counts rather than an upsell list. The workbench records a distinct `advisor_reviewed` state only when every Needs attention response has a saved advisor decision.

This state is an internal review record—not a diagnosis, estimate, customer DVI/Glovebox release, message, repair authorization, appointment, or AI recommendation. Technician observations remain separate from advisor dispositions. The next customer-facing release, pricing, evidence, torque, AI, plate scan, and controlled inspection-sheet work remain separate gates.

## Project structure

- `backend/app/auth.py`: Auth0 JWT verification and database-derived actor/scope dependency.
- `backend/app/api/checkin.py`: advisor/admin-only check-in bootstrap and pending-session creation.
- `backend/app/api/sessions.py`: shop- and role-scoped inspection lifecycle APIs.
- `backend/app/api/checklists.py`: staff read/admin write access protection.
- `backend/app/inspection_template.py`: strict, reusable template document validation for administration, visit snapshotting, and coverage.
- `dashboard/lib/`: Auth0 client and server-only internal API client.
- `dashboard/app/check-in/`: server-gated Check-in page and client form.
- `dashboard/app/inspections/`: technician-scoped provisional template workspace and full-coverage advisor-review handoff.
- `dashboard/app/api/check-in/`: same-origin dashboard command route.
- `dashboard/proxy.ts`: Auth0 SDK route and rolling-session middleware.
- `dashboard/Dockerfile` and Compose changes: future supervised dashboard runtime.

## Delivery gates

The isolated candidate has passed Python compilation, Next lint/build, container builds, a disposable PostgreSQL migration, and an API acceptance exercise. No deployment occurs during this build phase. Auth0 and DNS are now provisioned for the requested test host. The after-hours release still requires an explicit final go/no-go, a guarded release from this isolated commit, a pre-migration backup/check, a post-release health check, a real Auth0 sign-in/callback verification, and real pilot user/shop/technician/checklist seed-data verification.
