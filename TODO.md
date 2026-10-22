# Workbai Phase 1 Check-in — To Do

- [x] Add an Auth0-protected staff dashboard boundary and a server-only internal API client; no browser-side runtime-IP API calls for Check-in.
- [x] Add backend Auth0 JWT verification and database-derived active-user, shop, and role scope; reject missing configuration, invalid JWTs, unknown users, cross-shop resources, and unauthorized roles.
- [x] Add staff Check-in options and a single pending-inspection command requiring manual vehicle details, stated concern, an existing checklist, and an in-shop active technician.
- [x] Enforce session, checklist, media, voice, and vehicle-lookup ownership rules for the inspection surfaces used by Check-in, and replace credentialed wildcard CORS with named environment origins.
- [x] Build a responsive, professional Check-in screen with a clear handoff, 44px controls, no default gray block buttons, no ambient assistant, and truthful manual-entry messaging while consent-led scanning remains out of scope.
- [x] Add dashboard container/runtime declarations and non-secret environment templates for the future isolated test release.
- [x] Validate the isolated candidate with focused compilation/lint/build checks, inspect the diff, and commit it without deploying.

## Phase 1.1 — Template-driven technician inspection

- [x] Require an advisor to mark each new Check-in as exactly **Waiter** or **Drop-off**, and carry that operational fact to technician work without calling it customer contact data.
- [x] Snapshot the available template JSON and version into the visit at creation; preserve a generic, provisional-template-only rule with no claim to represent the unverified controlled inspection sheet.
- [x] Add a technician-scoped inspection workspace where every snapshot item receives an explicit result. Require a written note for Needs attention and N/A, and never treat an unfilled item as Good.
- [x] Permit a technician to submit only a fully rated inspection for advisor review. Do not send customer messages, release a Digital Glovebox view, create an estimate, or turn submission into authorization.
- [x] Enforce the no-bypass integrity contract: public session creation is unavailable; template section and item identities are structurally validated and globally unique; selected observations must belong to the saved snapshot; the command surface accepts only Good, Needs attention, and N/A.
- [x] Validate database migration, backend syntax, dashboard lint/build, final container images, and isolated API acceptance scenarios; commit without deploying.

## Phase 1.2 — Advisor Review Workbench

- [x] Add an advisor/admin-only review state that follows technician submission, with no customer release, repair authorization, estimate, or automatic communication side effect.
- [x] Give an advisor a single-visit workbench ordered by original concern, then explicit human triage of technician-attested Needs attention items: Safety, Maintenance, Visit concern, Monitor, No action, or Needs clarification.
- [x] Require a written advisor rationale for every attention-item disposition; show Good and N/A work as a contained count rather than a sales list.
- [x] Keep technician observations and advisor dispositions separate, attribute the advisor reviewer, prevent cross-shop review, and block review completion until every Needs attention item has a saved human decision; serialize competing save/complete commands on the canonical visit row.
- [x] Validate the migration, role/scope/state boundaries, lint/build, images, and isolated API acceptance scenarios—including simultaneous completion attempts—and commit without deploying.
