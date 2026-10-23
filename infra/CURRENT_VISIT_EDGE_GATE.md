# Current Visit public-edge gate

`WORKBAI_ENABLE_CURRENT_VISIT_RELEASE` and `WORKBAI_CURRENT_VISIT_EDGE_VERIFIED` must both remain `false` until the installed test proxy has passed this gate. This is a **counter-only, view-only** pilot route—not an SMS/email delivery route.

## Route contract

The issued private URL is `https://test.workbay.autorepairsolutions.ai/v#<random-secret>`. The secret is a browser fragment and therefore must never be transmitted in an HTTP request target. The browser loads only `GET /v`, then POSTs the fragment in a JSON body to `POST /api/public-current-visit/resolve`. The dashboard BFF sends the resolver body to FastAPI with a server-only resolver credential. No raw secret may be written to access logs, application request URLs, analytics, error reporting, browser history after resolution, or referrers.

The test proxy must have dedicated exact locations for **only** `/v` and `/api/public-current-visit/resolve`, before its generic dashboard location. For both exact routes it must:

1. disable or use a demonstrably redacted access log that excludes request URI, request body, `Referer`, and sensitive headers;
2. overwrite `X-Workbai-Public-Edge-Verified` with `1` and overwrite `X-Workbai-Public-Client-IP` with a trusted, normalized edge-derived address (never append/reuse client `X-Forwarded-For`);
3. clear inbound `X-Forwarded-For`, `X-Real-IP`, and any client-supplied `X-Workbai-Public-*` header before proxying;
4. apply an edge rate limit keyed by that trusted client address, with an explicit trusted upstream/real-IP configuration where a CDN/load balancer is in front of Nginx;
5. apply live-edge `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, and transport headers;
6. route no other `/v/*` or `/api/public-current-visit/*` paths publicly.

The dashboard proxy supplies a unique per-request nonce CSP for `/v` so the Next client can securely hydrate and submit the fragment body; the edge must not add a second `default-src` or `script-src` policy that blocks it. The test Compose `current-visit-cleanup` worker is mandatory whenever this feature is enabled. It deletes rate-limit and minimized access-audit data every five minutes, exits on cleanup failure so Docker restarts it, and exposes a heartbeat health check. The access-audit expiry is conservatively under seven days so healthy cleanup satisfies the seven-day maximum.

## Required proof before enabling

The guarded deployer must: inspect the installed, loaded proxy configuration; verify the exact two locations, explicit variant denies, and rate-limit zone; verify the cleanup worker is healthy; make a counter-only test request; inspect access/error/application logs by search for a known synthetic secret and confirm it is absent; verify a synthetic client-supplied forwarded address cannot alter the application’s rate-limit key; verify direct public resolver requests without the proxy-set edge header get a generic unavailable response; and record the result. Only then may a human set `WORKBAI_CURRENT_VISIT_EDGE_VERIFIED=true` for test.

Do **not** set that flag merely because this template exists. Any configuration change to Nginx, DNS, TLS, real-IP trust, environment secrets, or customer message provider remains an explicit deployment/infrastructure action and is outside this code candidate.
