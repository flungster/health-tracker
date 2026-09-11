# ADR: M22a — Cookie session auth for browser subresources

Status: accepted (decision made with the user 2026-09-11)
Milestone: M22a

## Context

Activity images (M22b–c) are rendered by the SPA as `<img>` tags. A browser
subresource request (`<img>`, CSS, fonts) **cannot set request headers**, so it
cannot carry the `Authorization: Bearer <jwt>` header that every API endpoint
accepts. Images are owner-scoped (a user must not be able to fetch another
user's photos by guessing a uuid), so the serving endpoint needs authentication.

## Decisions

### The session JWT is mirrored into an HttpOnly cookie

- `POST /auth/login` and `POST /auth/register` keep returning the token in the
  JSON body (no change for API clients) **and** set it as a cookie:
  `ht_session=<jwt>; Path=/api/v1; HttpOnly; SameSite=Lax`
  (+ `Secure` when `SESSION_COOKIE_SECURE=true`). Max-Age mirrors the token TTL.
- Token resolution (`get_current_user`) tries the `Authorization: Bearer`
  header first, then falls back to the cookie. **Bearer stays primary** — every
  existing client behaves exactly as before; the cookie is purely additive.
- `POST /auth/logout` (new, 204) expires the cookie; the SPA calls it
  best-effort on logout. The bearer token itself is stateless and stays valid
  until its expiry — logging out ends the *cookie* session (browser
  subresources), not token validity. Accepted trade-off: no server-side token
  revocation is introduced in this milestone.

### Why not the alternatives (considered with the user)

- **Query-param JWT** (`<img src="...?token=<jwt>"`): least code, but puts a
  long-lived (30-day) token in URLs — browser history, logs, `Referer`
  leakage. Rejected on that basis.
- **Short-lived signed URLs**: more secure than a query JWT, but needs a
  signing scheme plus an expiring store for something the cookie gets for free.

### Security analysis of the chosen design

- **HttpOnly**: page scripts (XSS) cannot read or copy the token.
- **SameSite=Lax**: cross-site *subrequests* (fetch/XHR/img from another
  origin) do not send the cookie, so a malicious site cannot call the JSON API
  with the victim's session (the classic CSRF path). Lax only relaxes that for
  top-level GET navigations — which here are read-only app pages. The image
  `<img>` is same-origin, so it sends the cookie as intended.
- **Path=/api/v1**: the cookie is never sent to non-API routes (static assets).
- **Secure** flag off by default for plain-HTTP homelab deployments; enabling
  TLS (reverse proxy) should set `SESSION_COOKIE_SECURE=true`.

## Consequences

- One shared resolver now accepts header or cookie on **all** endpoints. The
  SameSite=Lax analysis above is what makes that safe; if a future endpoint
  needs stricter semantics, scope the fallback there rather than removing it.
- Logout is partially effective (cookie only) until token TTL — documented in
  the endpoint docstring and `docs/api.md`.
