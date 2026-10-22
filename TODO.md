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

## Phase 1.3 — Controlled Template Governance

- [x] Add an additive template lifecycle: Draft, Approved, and Retired, plus an explicit provisional flag and immutable provenance fields. Every pre-governance record is permanently locked provisional and inactive; no existing provisional template may silently become approved.
- [x] Allow exactly one non-provisional, artifact-hash-backed approved template to be active for new Check-in sessions; block template edits after approval and preserve retired templates plus their source provenance for historical inspection snapshots.
- [x] Build an admin-only professional template-governance interface that shows lifecycle/provenance honestly and makes approval and retirement explicit; remove the obsolete gray/dark template-editor surface.
- [x] Make Check-in truthfully unavailable when there is no active approved non-provisional template, and select/lock the one active controlled template on the server rather than accepting a browser-selected template ID.
- [x] Validate lifecycle serialization, approval requirements, Check-in selection, immutability, retirement, migration, lint/build, image builds, and isolated API acceptance; commit without deployment.

## Phase 1.4 — Current Visit readiness, not release

- [x] Add a server-derived advisor-only readiness result based on immutable advisor-review and controlled-template provenance facts; do not issue or persist a customer URL, token, QR code, or delivery record.
- [x] Surface readiness as a quiet internal workbench state with explicit block reasons and no public/share/send/customer action.
- [x] Validate that the advisor-review lifecycle still locks correctly and that no Current Visit release capability is added; commit without deployment.

## Phase 1.5 — Current Visit counter view, manager-gated and default-off

- [x] Add optional per-visit customer contact capture at Check-in with separate recorded answers for private-link and progress-update permissions. Keep contact optional, encrypted server-side, keyed for lookup without raw-value persistence, and unavailable unless the feature flag plus security configuration are explicitly set.
- [x] Add a server-owned customer-release ledger with immutable, allowlisted projection revisions; retain advisor-review/template-provenance facts; name a human owner; and require a separately delegated in-shop Current Visit manager to approve customer view activation and every published progress update.
- [x] Add one expiring, revocable, HMAC-only 15-minute counter link that returns its random secret only in a browser URL fragment—not a server request path—with token-free staff/release audits, source rechecks, no raw secret persistence, and no public internal-report adapter.
- [x] Require both the default-off feature flag and a separate edge-verification gate before counter activation or public resolution. Supply a dedicated exact `/v` and resolver ingress template with logs disabled, client identity overwritten from trusted edge data, explicit denial of all public variants, no public wildcard route, edge rate limit, live-edge anti-framing/referrer/no-store policy, and a dashboard nonce CSP compatible with Next hydration.
- [x] Use atomic, expiring database rate-limit buckets keyed only by a keyed ingress address or link; retain minimized public access audit for under seven days with no user-agent collection, and prune expired records every five minutes through a restartable, health-checked Compose cleanup worker independent of web-process uptime.
- [x] Add a minimal mobile customer Current Visit page that exposes only vehicle label, shop call route, fixed manager-approved progress, update time, expiry, and an explicit non-diagnostic/non-approval scope disclosure. Apply no-store, no-referrer, HSTS, permissions, and CSP protections at the page/edge layers.
- [x] Keep all outbound SMS/email delivery held: do not ship a sender, customer identity/account, OTP, recipient verification, findings/media/VIN/notes/decisions, estimates, invoices, customer approval, repair authorization, or AI decision/explanation path in this slice.
- [ ] Before any deployment enables `WORKBAI_ENABLE_CURRENT_VISIT_RELEASE` or `WORKBAI_CURRENT_VISIT_EDGE_VERIFIED`, inspect the actual loaded public proxy: exact `/v` and resolver locations, disabled/redacted logs, trusted real-IP configuration, overwriting headers, edge limits, synthetic-secret absence from logs, private security config presence, explicit manager delegation, support-call contact, consent policy/notice, vulnerability/rate-limit testing, and the full guarded test-release preflight. Do not enable an automated customer message without a separately approved provider, recipient verification, opt-out, delivery/audit, and template-control gate.
