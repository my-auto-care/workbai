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

This Phase 1 build does **not** store customer name, phone, customer portal identity, Digital Glovebox links, DVIPlus records, plate images, consent receipts, or vehicle-specific AI recommendations. It also does not freeze the final inspection sheet. Until their legal/data and cross-product contracts are approved, these are separate build gates rather than placeholder behavior. The isolated test runtime sets the billing, voice-inspection, plate/VIN lookup and vehicle-AI/transcript router flags to `false`. Production keeps them mounted (the flags default on when unset) because the released mobile app, the voice worker and Stripe use them; every route in them requires staff Auth0, the voice worker's service credential, or a verified Stripe signature.

The UI therefore uses confirmed manual vehicle entry. Plate/VIN scanning will be a later explicit-consent, transient-processing flow with manual fallback. Checklist templates are shop-owned (migration `c9d0e1f2a3b4`): each shop sees, edits and activates only its own templates.

## Phase 1.1: technician inspection workspace

The next build slice snapshots the selected available template and version when an advisor starts a visit, then gives only the assigned technician a controlled, template-driven workspace. An item response may be `good`, `poor` (**Needs attention** in the UI), or `na`; Needs attention and N/A require a written reason. Templates must have nonempty, globally unique section and item identities, and any selected observation must be one declared in that visit’s own snapshot. The server stores one current response per item and permits a technician to submit only when all snapshot items have an explicit result. Submission means **submitted for advisor review**, not customer delivery, approval, pricing, repair authorization, quality control, or a completed repair.

The bundled Basic Vehicle Inspection Checklist is a named provisional test template. It is not represented as, or substituted for, the controlled inspection sheet. No final field locations, torque values, thresholds, evidence policy, AI diagnosis, plate scan, or customer-facing DVI release will be inferred or enabled by this slice.

## Phase 1.2: Advisor Review Workbench

The next allowed slice is a single-visit, advisor/admin-only workbench for a technician-submitted provisional inspection. It shows the customer’s original concern first, then only human-attested Needs attention responses for an explicit, written human disposition: **Safety**, **Maintenance**, **Visit concern**, **Monitor**, **No action**, or **Needs clarification**. Good and N/A work remain compact counts rather than an upsell list. The workbench records a distinct `advisor_reviewed` state only when every Needs attention response has a saved advisor decision.

This state is an internal review record—not a diagnosis, estimate, customer DVI/Glovebox release, message, repair authorization, appointment, or AI recommendation. Technician observations remain separate from advisor dispositions. The next customer-facing release, pricing, evidence, torque, AI, plate scan, and controlled inspection-sheet work remain separate gates.

## Phase 1.3: Controlled Template Governance

New Check-in sessions must use the shop's one active **approved**, non-provisional inspection template. A draft stays editable; an approved template is immutable to preserve the snapshot contract; a retired template is unavailable for new visits but remains readable for historical inspection records. Approving a template requires a named source reference, SHA-256 artifact hash, a recorded administrator, and an explicit no-longer-provisional declaration. The exact inspection-sheet artifact is still unavailable in this build, so no bundled template may be marked approved or made active.

This is template governance only. It does not digitize or infer the unverified sheet’s rows, torque values, field locations, thresholds, layout, vehicle logic, or evidence policy. It does not release a customer view, send an invitation, enable a camera scan, or authorize AI diagnosis.

## Phase 1.4: Current Visit readiness only

The advisor workbench may expose a server-derived **Current Visit readiness** status after internal review. It evaluates only immutable visit facts: completed/attributed advisor review, a template snapshot, and matching approved-template provenance. It creates **no** token, link, QR code, customer identity, invitation, message, delivery attempt, report, estimate, authorization, or customer-facing endpoint.

A future Digital Glovebox access release requires its own reviewed customer identity/access policy, random-secret and hashed-token lifecycle, expiry/revocation/access audit, rate limiting, log redaction, explicit minimized public projection, no-store/no-referrer/CSP headers, and customer delivery/consent contract. None of those public-access mechanisms are part of this candidate.

## Phase 1.5: Manager-gated Current Visit counter view

This next isolated candidate implements the foundational **view-only** Current Visit access contract as a default-off feature flag. At Check-in, staff may optionally capture one visit-scoped SMS or email destination with separate, explicit answers for a private visit link and progress updates. The destination is encrypted server-side, uses a keyed lookup digest, and is never customer identity, authorization, or an account. A customer can receive service without providing contact information or consent.

After the existing advisor review and immutable controlled-template provenance are complete, an advisor can prepare a minimal projection owned by a named human advisor. A distinct, explicitly delegated per-shop Current Visit manager—not every advisor or administrator by default—must approve it before issuing one 15-minute counter-view link. The random link secret is stored only as an HMAC, returned to staff once inside the browser-only URL fragment (never a server request path), expires, can be revoked immediately, and is audited without storing the plaintext link, destination, or internal report. Manager-reviewed fixed progress states can replace the already-approved customer projection; they never send a message.

The public page resolves its browser-fragment secret to FastAPI by POST body so the backend path never contains a secret, emits a strictly allowlisted projection (vehicle label, shop name/call route, fixed progress, timestamp, and clear scope disclosure), and is protected by no-store, no-referrer, HSTS, clickjacking, permissions-policy, a per-request nonce CSP compatible with Next hydration, and edge frame isolation. Counter-link activation and public resolution require both the default-off feature flag and an explicit `WORKBAI_CURRENT_VISIT_EDGE_VERIFIED` deployment gate; it must remain false until a tested ingress disables/redacts logs, overwrites the dedicated client-address header, permits only exact `/v` and resolver routes, and denies all variants. The dashboard-to-backend resolver uses a server-only shared secret and a literal verified-edge marker after the BFF has checked the edge marker. Application rate limiting uses atomic, expiring database buckets keyed only by a keyed ingress address/link value; public access audit excludes user-agent collection and is pruned by a restartable, health-checked worker every five minutes before the seven-day maximum.

This slice intentionally does **not** send SMS/email, use an external delivery provider, issue an OTP, verify a recipient, create a customer account, show findings/notes/media/VIN/mileage/contact data/internal decisions, solicit approval, expose estimates/invoices, authorize repairs, or add AI explanation/diagnosis. Outbound delivery remains a separate provider, consent, recipient-verification, audit, opt-out, rate-limit, and template-approval gate; it cannot be turned on by the Current Visit manager controls.

## Phase 1.6: Internal customer context and rapid intake

This isolated candidate adds a staff-only, shop-scoped customer-context domain beside the canonical `InspectionSession`; it does **not** introduce a second visit record. Customer name and durable contact fields are encrypted with a purpose-specific key. Fast reception search uses shop- and field-bound HMAC blind-index tokens for name, email, phone, customer reference, and secured vehicle-identifier lookups rather than plaintext PII columns or full-text search. An advisor or administrator can select a candidate, create a distinct encrypted profile, or proceed with manual intake. A candidate match is never an identity match, customer merge, ownership claim, authorization, or cross-shop lookup.

The domain records an explicit, attributable customer–vehicle association only after staff confirms it with the customer. A customer can still be linked to a canonical visit without silently creating a durable vehicle relationship. New shop vehicle records keep newly-entered VIN data encrypted and indexed by full/VIN-tail HMAC lookup values; it is never copied to the legacy plaintext vehicle profile or inspection-session VIN field. Existing legacy VIN/transcript fields are not copied, indexed, or broadened by this slice. Rapid Find uses authenticated POST bodies end-to-end so typed customer, contact, VIN-tail, or vehicle queries do not appear in dashboard/backend request URLs or normal access logs.

The rapid vehicle search queries a cached provider-sourced NHTSA vPIC year/make/model catalog. A one-line match such as `2017 Toyota Highlander` can fill proposed year, make, and model, with source IDs, URL, and retrieval time retained on the catalog row. It is an identification aid only. It cannot create a customer vehicle, infer ownership/VIN/trim/mileage, create an inspection item, assert a common failure, calculate maintenance, or support a diagnostic, safety, repair, pricing, or authorization claim. A controlled operator-run importer preloads selected year/make pairs; it is rate-limited and never runs inside Check-in, so manual entry remains a reliable fallback.

Staff can attach encrypted, visit-bound context records for a reviewed phone transcript, appointment note, service history, prior visit, or manual note. Raw context is excluded from search, normal history, reports, public Current Visit payloads, analytics, and browser logs. It is readable only through a narrowly scoped advisor/admin endpoint that writes a token-free factual access audit. Phone-transcript raw text requires an explicit retention expiry no more than 90 days away; a durable worker removes expired raw content while retaining the reviewed source metadata and excerpt. The staff-facing Check-in context shows only bounded reviewed excerpts, visit metadata, a factual upcoming appointment, and source-backed draft wording.

The reason-for-visit field remains the customer’s confirmed words on the canonical Visit. The UI offers customer-specific reviewed excerpts and administrator-curated customer-wording prompts, plus generic non-diagnostic wording. Selecting one can prefill a draft and retains source provenance, but staff may edit it and the prompt cannot overwrite the current visit, create a finding, set an inspection result, alter a technician record, or move the visit state. Cross-customer vehicle-wide wording is empty unless a human administrator curates it with a source label/revision; no AI or unsourced "known issue"/maintenance/TSB feed is used.

An authenticated incoming-call context endpoint accepts an exact normalized caller number and returns a capped set of same-shop candidate cards: masked contact, confirmed vehicles, recent visit metadata, reviewed conversation summaries, and an upcoming appointment summary. A match writes a content-free staff profile-access audit containing only shop, customer, actor, purpose, and time—not the caller number, contact, transcript, or displayed summary. It neither verifies the caller’s identity nor initiates a call, message, screen pop, appointment sync, transcript import, or telephony webhook. A future PBX/appointment connector requires a separate signed-webhook/provider-authorization, replay protection, staff display, consent, audit, and retention review before it can push a card on screen.

## Project structure

- `backend/app/auth.py`: Auth0 JWT verification and database-derived actor/scope dependency.
- `backend/app/api/checkin.py`: advisor/admin-only check-in bootstrap and pending-session creation.
- `backend/app/customer_data_security.py`: purpose-specific customer/context encryption and shop-bound blind-index helpers.
- `backend/app/api/checkin.py`: staff-only customer/vehicle candidate search, reviewed appointment/history/transcript context, curated reason prompts, and authenticated incoming-call context.
- `backend/scripts/preload_vehicle_catalog.py`: explicit NHTSA vPIC year/make catalog preload command; it creates no customer, vehicle, inspection, or diagnosis record.
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
