# Security Guide

## Authentication Model

TunnBox recognizes two kinds of **principals**: a logged-in user session, or an API key. Every
request is authenticated as one or the other.

```
Authorization: Bearer <access-jwt>     # session
Authorization: Bearer tb_<key>         # API key
X-API-Key: tb_<key>                    # API key, alternate header
```

### Sessions: access token + refresh cookie

- **Access token** — a short-lived JWT (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 15 minutes),
  held only in memory by the frontend (never `localStorage`). It carries the user id, session id,
  role, and expiry.
- **Refresh token** — 32 random bytes, delivered as an httpOnly, `SameSite=Strict` cookie
  (`tb_refresh`, path `/api/auth`), never readable by JavaScript. Only its SHA-256 hash is
  stored in the `sessions` table.
- Calling `POST /api/auth/refresh` rotates the refresh token, extends `expires_at` (sliding,
  capped by `SESSION_ABSOLUTE_DAYS`), and issues a new access token. **Reuse of an
  already-rotated refresh token revokes the entire session** — a signal that the cookie was
  stolen and replayed.
- `POST /api/auth/refresh` also checks, when the request carries an `Origin` or `Referer` header,
  that its host matches the request's `Host` header, and returns `403` otherwise. This is the
  app's CSRF defence for the one cookie-based endpoint; everything else uses the bearer token,
  which a third-party site cannot read or attach automatically.
- Sessions can be listed and revoked individually or in bulk: `GET /api/auth/sessions`,
  `DELETE /api/auth/sessions/{id}`, `DELETE /api/auth/sessions` (revoke all but the current one).
- Changing your password revokes every *other* session. Deactivating a user revokes all of their
  sessions and API keys.

### Multi-Factor Authentication

TOTP-based MFA with recovery codes. Setting up or changing MFA always requires re-entering your
current password, not just an active session:

1. `POST /api/mfa/setup {password}` — verifies your password, then generates a TOTP secret
   (stored encrypted, not yet enabled) and returns `secret`, `otpauth_uri`, and `qr_svg`.
2. `POST /api/mfa/enable {code, password}` — verifying your password and a 6-digit code turns MFA
   on and returns 10 single-use **recovery codes** (`xxxx-xxxx` format), shown once.
3. From then on, `POST /api/auth/login` with correct credentials returns
   `{"mfa_required": true, "mfa_token": "<jwt>"}` (HTTP 200, no session yet) instead of a session.
   The `mfa_token` is a purpose-scoped JWT valid for 5 minutes, and **single-use**: once it's been
   consumed by a login/MFA attempt (successful or not — see below) it cannot be replayed.
4. `POST /api/auth/login/mfa {mfa_token, code}` completes login. `code` accepts either a 6-digit
   TOTP code or a recovery code. A TOTP code is checked against a ±1 time-step window but **cannot
   be reused within the same time step** once it has been accepted, closing a narrow
   replay/interception window. Each recovery code works once.
5. `POST /api/mfa/recovery-codes {password}` regenerates the set (invalidating the old ones).
6. `POST /api/mfa/disable {password, code}` turns MFA off.

**Failed MFA codes count toward account lockout** the same as failed passwords — repeatedly
guessing TOTP codes or recovery codes locks the account for `LOCKOUT_MINUTES` after
`LOCKOUT_THRESHOLD` failures, same as password brute-forcing. See
[Lockout & Rate Limiting](#lockout--rate-limiting).

**Lost MFA device:** a user without access to their authenticator or recovery codes cannot self
-recover. An admin can clear their MFA via `POST /api/users/{id}/mfa/reset` (Settings > Users),
after which the user can log in with just their password and set MFA up again. If the locked-out
account *is* the only admin, reset the password with the CLI (below) — password reset does not
require or touch MFA, but if the admin is genuinely locked out of both, the only path is a
database-level fix.

### Roles

| Role | Can do |
|------|--------|
| `admin` | Everything: users, API keys, all interfaces/peers, settings, backups, audit |
| `operator` | Create/edit/delete interfaces and peers, read audit log, manage their own password/MFA/sessions |
| `viewer` | Read-only (`GET`) access, plus their own password/MFA/sessions |

::: warning Peer config, QR and share links require operator
`GET /api/peers/{id}/config`, `GET /api/peers/{id}/qr`, and `POST /api/peers/{id}/share` all
require the **operator** role (or an API key with the `peers:write` scope), not just `viewer`/
`read`, even though they're read-style operations. A viewer or a read-only API key gets `403`.
This is because a peer's config download exposes its private key and preshared key — the same
bar as any other write to that peer.
:::

`require_role("operator")` in the API accepts operator *or* admin. Roles are enforced per
endpoint; there is no per-interface or per-peer scoping — any operator or admin can manage any
interface.

### API Keys

Created under **Settings > API keys** (`POST /api/api-keys {name, scopes[], expires_at?}`).
The plaintext key (`tb_...`) is shown exactly once at creation; only its SHA-256 hash and an
8-character prefix are stored. Users see and manage their own keys; an admin can list everyone's
with `?all=true`.

Scopes:

| Scope | Grants |
|-------|--------|
| `read` | All `GET` endpoints available to the key's role |
| `peers:write` | Create/update/delete/enable/disable/rotate/share peers |
| `interfaces:write` | Create/update/delete/up/down interfaces |
| `admin` | Everything an admin session can do via API key |

A key can never exceed its owner's role — an operator's key cannot hold `admin`. API keys can
never call `/api/auth/*`, `/api/mfa/*`, `/api/users/*` (unless the key has `admin` scope), or
create other API keys; those require a real session. Revoke a key with
`DELETE /api/api-keys/{id}`.

See [API Keys & Automation](./api-keys-and-automation.md) for usage examples.

### Lockout & Rate Limiting

- **Login rate limit** — `LOGIN_RATE_LIMIT` (default `10/minute`) per client IP, tracked in an
  in-memory sliding window. Exceeding it returns `429` with `Retry-After`.
- **Account lockout** — after `LOCKOUT_THRESHOLD` failed attempts (default 8) for one username,
  that account is locked for `LOCKOUT_MINUTES` (default 15); login returns `423` with
  `"Account temporarily locked"`. A successful login resets the failure counter.
- Unknown usernames still run a bcrypt comparison against a fixed dummy hash, so login timing
  doesn't reveal whether an account exists.
- The public share-link endpoint (`GET /api/share/{token}`) is separately rate limited to 20
  requests/minute per IP.

## Password Policy

10–128 characters, must not equal the username, and must not be one of a small built-in list of
common weak passwords. Enforced on setup, user creation, password change, and the CLI's
`reset-password`.

## Resetting a Password from the Command Line

If nobody can log in (lost MFA and lost admin credentials, or you just need to recover an
account), reset a password from inside the running container:

```bash
docker exec -it tunnbox python -m app.cli reset-password <username>
```

You'll be prompted for a new password (entered twice, validated against the policy above). This
also clears any lockout, reactivates the account, and revokes all of that user's existing
sessions. Other admin CLI commands:

```bash
docker exec -it tunnbox python -m app.cli create-admin <username>   # create a new admin user
docker exec -it tunnbox python -m app.cli list-users                # list users, roles, MFA status
```

## Encryption at Rest

- **Peer and interface private keys**, and **MFA secrets**, are encrypted with Fernet
  (AES-128-CBC + HMAC-SHA256), keyed by PBKDF2-SHA256 over `SECRET_KEY` with a random salt per
  value, stored as `base64(salt):ciphertext`.
- The encryption key is derived entirely from `SECRET_KEY`. **Losing `SECRET_KEY` (or the
  generated `./data/app/.secret_key` file) makes every encrypted private key and MFA secret in
  the database permanently undecryptable** — sessions signed with the old key are also
  invalidated. Keep `SECRET_KEY` (or `.secret_key`) backed up alongside the database; see
  [Backup & Restore](./backup-restore.md).
- Passwords are hashed with bcrypt, never encrypted or logged.

## Security Headers & CSP

Set on every response:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `Cross-Origin-Resource-Policy` | `same-origin` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (only when the request is HTTPS) |

The app's Content-Security-Policy has no `'unsafe-inline'` for scripts: `script-src` allows
`'self'` plus SHA-256 hashes of the frontend's own inline `<script>` blocks, computed at startup
from `frontend/build/index.html`. `/api/docs`, `/api/redoc` and `/api/openapi.json` get a relaxed
CSP so Swagger UI's CDN assets can load; they stay publicly reachable without authentication.

There is no separate CSRF token or middleware — mutation endpoints require a bearer token (which
a third-party page cannot obtain), and the one cookie-authenticated endpoint,
`POST /api/auth/refresh`, checks `Origin`/`Referer` against `Host` instead.

## Reverse Proxy Configuration

Running behind Nginx, Caddy, or any reverse proxy requires two settings so the app sees real
client IPs and issues correctly-flagged cookies:

- **`TRUSTED_PROXIES`** — comma-separated IPs/CIDRs of your proxy. Without it, TunnBox ignores
  `X-Forwarded-For`/`X-Forwarded-Proto` entirely (treating the proxy's own IP as the client, and
  the connection as plain HTTP), which breaks rate limiting/lockout accuracy and
  `COOKIE_SECURE=auto`.
- **`COOKIE_SECURE`** — `auto` (default) sets the refresh cookie's `Secure` flag only when the
  request is HTTPS, either directly or via `X-Forwarded-Proto: https` from a trusted proxy. If
  your proxy terminates TLS and `TRUSTED_PROXIES` isn't set correctly, the cookie may never be
  marked `Secure`, or (worse) always required `Secure` when you're testing over plain HTTP. Set it
  explicitly (`true`/`false`) if `auto` doesn't behave as expected for your setup.

**How `X-Forwarded-For` is parsed:** the header is only trusted at all when the directly
connecting peer's IP matches `TRUSTED_PROXIES`. The list of hops in the header is then walked
**right-to-left**, skipping every hop that is itself a trusted proxy, and the first hop found that
is *not* trusted is taken as the real client IP. This matters with more than one proxy in the
chain (e.g. a CDN in front of your own reverse proxy): list every hop you actually trust in
`TRUSTED_PROXIES`, or an untrusted (attacker-controlled) address earlier in the header could be
picked up as the client IP. A single reverse proxy directly in front of TunnBox (the common case)
only needs that proxy's own IP/CIDR in `TRUSTED_PROXIES`.

See [Production Deployment](../deployment/production.md#trusted_proxies-and-cookie_secure) for
full proxy examples.

## Audit Logging

Every mutation is recorded in `audit_logs`, with the action name, target, a JSON `details` blob,
the actor's IP, and timestamp. The actor is a username, `system` for background jobs (e.g. peer
auto-disable), or `api-key:<name>` when performed via an API key.

Representative action names: `auth.login`, `auth.login_failed`, `auth.locked`, `auth.logout`,
`auth.setup`, `auth.mfa_enabled`, `auth.mfa_disabled`, `auth.password_changed`,
`auth.session_revoked`, `apikey.created`, `apikey.revoked`, `user.created`, `user.updated`,
`user.deleted`, `interface.created`, `interface.updated`, `interface.deleted`, `interface.up`,
`interface.down`, `peer.created`, `peer.updated`, `peer.deleted`, `peer.enabled`,
`peer.disabled`, `peer.auto_disabled`, `peer.keys_rotated`, `peer.config_downloaded`,
`peer.share_created`, `peer.share_used`, `settings.updated`, `system.backup`, `system.export`.

Query, filter, and export it (operator role or above) at **Audit** in the UI, or
`GET /api/audit`, `GET /api/audit/actions`, `GET /api/audit/export.csv`.

## Input Validation

| Input | Rule |
|-------|------|
| Interface name | `^[a-zA-Z0-9_=+.-]{1,15}$`, and not `all`, `default`, or `lo` |
| Listen port | 1–65535, unique per interface |
| Address | Valid CIDR (IPv4 and/or IPv6, comma-separated) |
| Peer name | Non-empty, reasonable length |
| Persistent keepalive | 0–65535 seconds |
| PostUp / PostDown | Rejected unless `WG_ALLOW_CUSTOM_SCRIPTS=true`, **and only an admin can set them even then** — an operator's request to set `post_up`/`post_down` is rejected regardless of the flag |
| Password | 10–128 chars, not the username, not a common weak password |
| Peer `allowed_ips` | Must be host routes inside the interface's own subnet(s); wider routes are admin-only and `0.0.0.0/0`/`::/0` are never allowed; overlapping or already-assigned addresses return `409`. See [Peer Management](./peer-management.md#server-side-allowed-ips-policy). |

## Container Security

```yaml
cap_drop: [ALL]
cap_add: [NET_ADMIN, SYS_MODULE, MKNOD]
security_opt: [no-new-privileges:true]
```

- `NET_ADMIN` — manage WireGuard interfaces and iptables NAT rules
- `SYS_MODULE` — load the WireGuard kernel module if not already loaded
- `MKNOD` — create `/dev/net/tun` for the wireguard-go userspace fallback

Resource limits and JSON log rotation are set in the default `docker-compose.yml`.

## Recommendations

1. Keep `SECRET_KEY` (or `./data/app/.secret_key`) static and backed up.
2. Put TunnBox behind a reverse proxy with HTTPS and set `TRUSTED_PROXIES` accordingly — see
   [Production Deployment](../deployment/production.md).
3. Enable MFA on every admin and operator account.
4. Use scoped API keys with the minimum scope needed, and set expiries on long-lived automation
   keys.
5. Review the audit log periodically for `auth.login_failed` and `auth.locked` entries.
6. Take regular backups, including `SECRET_KEY`/`.secret_key` — see
   [Backup & Restore](./backup-restore.md).
7. Keep the image updated — see [Updating](./updating.md).
