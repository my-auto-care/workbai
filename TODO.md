# Workbai Phase 1 Check-in — To Do

- [x] Add an Auth0-protected staff dashboard boundary and a server-only internal API client; no browser-side runtime-IP API calls for Check-in.
- [x] Add backend Auth0 JWT verification and database-derived active-user, shop, and role scope; reject missing configuration, invalid JWTs, unknown users, cross-shop resources, and unauthorized roles.
- [x] Add staff Check-in options and a single pending-inspection command requiring manual vehicle details, stated concern, an existing checklist, and an in-shop active technician.
- [x] Enforce session, checklist, media, voice, and vehicle-lookup ownership rules for the inspection surfaces used by Check-in, and replace credentialed wildcard CORS with named environment origins.
- [x] Build a responsive, professional Check-in screen with a clear handoff, 44px controls, no default gray block buttons, no ambient assistant, and truthful manual-entry messaging while consent-led scanning remains out of scope.
- [x] Add dashboard container/runtime declarations and non-secret environment templates for the future isolated test release.
- [x] Validate the isolated candidate with focused compilation/lint/build checks, inspect the diff, and commit it without deploying.
