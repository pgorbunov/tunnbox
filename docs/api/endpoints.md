# API Reference

TunnBox exposes a REST API under `/api`. Every endpoint returns JSON (except config/QR/backup
downloads). Errors are `{"detail": string, "code"?: string}`.

## Authentication

Every endpoint except the ones marked **public** below requires a principal: a logged-in session
(access token) or an API key.

```
Authorization: Bearer <access-jwt>     # session, from /api/auth/login
Authorization: Bearer tb_<key>         # API key
X-API-Key: tb_<key>                    # API key, alternate header
```

See [Security](../guides/security.md#authentication-model) for the session/refresh model and
[API Keys & Automation](../guides/api-keys-and-automation.md) for key scopes and usage. Endpoints
below are grouped by tag and note the minimum **role** and, where applicable, the **API key
scope** required (`require_role("operator")` accepts operator or admin).

## Base URL & Interactive Docs

```
https://your-server/api
```

- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`
- Raw schema: `/api/openapi.json`

These three stay public even in production.

## Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Bad request / validation error |
| 401 | Not authenticated or token expired |
| 403 | Forbidden — role or scope insufficient |
| 404 | Not found |
| 409 | Conflict (duplicate name/port, last admin, etc.) |
| 410 | Gone — share link expired or exhausted |
| 422 | Request body failed schema validation |
| 423 | Account locked (login only) |
| 429 | Rate limited (`Retry-After` header set) |

## Common Types

```ts
Role = "admin" | "operator" | "viewer"
User = { id, username, role, is_active, totp_enabled, last_login_at, created_at }
Interface = { id, name, public_key, address, listen_port, dns, mtu, post_up, post_down,
              public_endpoint, enabled, is_active, peer_count, online_peer_count,
              rx_total, tx_total, created_at, updated_at }
Peer = { id, interface_id, interface_name, name, public_key, allowed_ips, client_allowed_ips,
         client_dns, persistent_keepalive, enabled, expires_at, notes, has_private_key,
         has_preshared_key, endpoint, latest_handshake_at, is_online, rx_total, tx_total,
         created_at, updated_at, status: "online"|"offline"|"disabled"|"expired" }
Session = { id, ip, user_agent, created_at, last_used_at, expires_at, current }
ApiKey = { id, name, prefix, scopes, expires_at, last_used_at, created_at, revoked_at }
AuditEntry = { id, user_id, username, action, target, details, ip, created_at }
Page<T> = { items: T[], total, page, page_size }
```

---

## auth (`/api/auth`)

| Method & Path | Role | Notes |
|---|---|---|
| `GET /status` | public | `{ setup_required, version }` |
| `POST /setup` | public | `{username, password}` → session. Only when no users exist; `409` otherwise |
| `POST /login` | public, rate limited | `{username, password}` → session, or `{mfa_required: true, mfa_token}` |
| `POST /login/mfa` | public, rate limited | `{mfa_token, code}` → session (`code` = TOTP or recovery code) |
| `POST /refresh` | public (refresh cookie) | Rotates the refresh cookie, returns a new access token |
| `POST /logout` | session | `204`; revokes the current session, clears the cookie |
| `GET /me` | any | Current `User` |
| `PATCH /me/password` | any | `{current_password, new_password}` → `204`; revokes other sessions |
| `GET /sessions` | any | List the caller's sessions |
| `DELETE /sessions` | any | `204`; revoke all sessions except the current one |
| `DELETE /sessions/{id}` | any | `204`; revoke one session |

### Login

```bash
curl -X POST https://vpn.example.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "correct horse battery staple"}' \
  -c cookies.txt
```

If the account has MFA enabled, this returns `{"mfa_required": true, "mfa_token": "..."}` instead
of a session. Complete it with:

```bash
curl -X POST https://vpn.example.com/api/auth/login/mfa \
  -H "Content-Type: application/json" \
  -d '{"mfa_token": "<from previous step>", "code": "123456"}' \
  -c cookies.txt
```

Both return `{ access_token, token_type: "bearer", expires_in, user }` and set the `tb_refresh`
httpOnly cookie (path `/api/auth`).

## mfa (`/api/mfa`)

Session principals only — API keys cannot call these.

| Method & Path | Notes |
|---|---|
| `POST /setup` | `{password}` → `{secret, otpauth_uri, qr_svg}`; not enabled yet |
| `POST /enable` | `{code, password}` → `{recovery_codes: string[]}` (10 codes, shown once) |
| `POST /disable` | `{password, code}` → `204` |
| `POST /recovery-codes` | `{password}` → `{recovery_codes: string[]}` (regenerate) |

A TOTP `code` cannot be reused within its time step, and the `mfa_token` from `/api/auth/login` is
single-use; failed codes count toward account lockout the same as failed passwords. See
[Security — multi-factor authentication](../guides/security.md#multi-factor-authentication).

## api-keys (`/api/api-keys`)

Session principals only.

| Method & Path | Notes |
|---|---|
| `GET /` | Caller's keys; admin: `?all=true` for everyone's |
| `POST /` | `{name, scopes: string[], expires_at?}` → `ApiKey & {key: string}` (plaintext shown once) |
| `DELETE /{id}` | `204`; revoke |

## users (`/api/users`) — admin only

| Method & Path | Notes |
|---|---|
| `GET /` | List users |
| `POST /` | `{username, password, role}` → `User` |
| `PATCH /{id}` | `{role?, is_active?, password?}` → `User`; can't demote/disable yourself or remove the last active admin |
| `DELETE /{id}` | `204`; same guards |
| `POST /{id}/mfa/reset` | `204`; admin clears a user's MFA |

## interfaces (`/api/interfaces`)

| Method & Path | Role | Scope | Notes |
|---|---|---|---|
| `GET /` | viewer | `read` | List interfaces |
| `POST /` | operator | `interfaces:write` | `201 Interface` |
| `GET /{name}` | viewer | `read` | |
| `PATCH /{name}` | operator | `interfaces:write` | Restarts if address/port/mtu/scripts change while active |
| `DELETE /{name}` | operator | `interfaces:write` | `204`; brings down, deletes conf + peers |
| `POST /{name}/up` | operator | `interfaces:write` | |
| `POST /{name}/down` | operator | `interfaces:write` | |
| `GET /{name}/config` | admin | `admin` | `text/plain` server `.conf`, contains the private key |
| `GET /{name}/stats` | viewer | `read` | `?range=1h\|6h\|24h\|7d\|30d` |
| `GET /{name}/peers` | viewer | `read` | `?q=&status=&sort=name\|handshake\|rx\|tx\|created&order=asc\|desc` |
| `POST /{name}/peers` | operator | `peers:write` | `201 Peer` |
| `GET /{name}/next-ip` | viewer | `read` | `{allowed_ips}` |

## peers

| Method & Path | Role | Scope | Notes |
|---|---|---|---|
| `GET /api/peers` | viewer | `read` | Global search: `?q=&interface=&status=&page=&page_size=` → `Page<Peer>` |
| `POST /api/peers/bulk` | operator | `peers:write` | `{ids: int[], action: "enable"\|"disable"\|"delete"}` → `{affected: int}` |
| `GET /api/peers/{id}` | viewer | `read` | |
| `PATCH /api/peers/{id}` | operator | `peers:write` | |
| `DELETE /api/peers/{id}` | operator | `peers:write` | `204` |
| `POST /api/peers/{id}/enable` | operator | `peers:write` | |
| `POST /api/peers/{id}/disable` | operator | `peers:write` | |
| `POST /api/peers/{id}/rotate-keys` | operator | `peers:write` | New keypair + PSK; old client config stops working |
| `GET /api/peers/{id}/config` | operator | `peers:write` | `text/plain`, attachment `<name>.conf`; `?allowed_ips=` override; `404` if no stored private key. Requires operator/`peers:write` because it exposes the private key and PSK |
| `GET /api/peers/{id}/qr` | operator | `peers:write` | `image/png`; same override param and requirement |
| `POST /api/peers/{id}/share` | operator | `peers:write` | `{expires_in_hours?: 24, max_uses?: 1}` → `{url_path, token, expires_at, max_uses}` |
| `GET /api/peers/{id}/stats` | viewer | `read` | Same shape as interface stats |

### Create a peer with auto IP assignment

```bash
curl -X POST https://vpn.example.com/api/interfaces/wg0/peers \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice'"'"'s laptop", "allowed_ips": "auto", "expires_at": null}'
```

### Download a config with an API key

```bash
curl https://vpn.example.com/api/peers/42/config \
  -H "Authorization: Bearer tb_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" \
  -o alice-laptop.conf
```

## share (`/api/share`) — public, rate limited (20/min per IP)

| Method & Path | Notes |
|---|---|
| `GET /{token}` | `{peer_name, interface_name, expires_at, remaining_uses, config, qr_png_base64}`; increments uses; `404`/`410` when invalid, expired, or exhausted; audit-logs `peer.share_used` |

## stats (`/api/stats`)

| Method & Path | Role | Scope |
|---|---|---|
| `GET /overview?range=24h` | viewer | `read` |

Returns `{interfaces_total, interfaces_active, peers_total, peers_online, peers_disabled, peers_expiring_7d, rx_total, tx_total, series: [{ts, rx, tx}], top_peers: [...] (5), recent_activity: AuditEntry[] (10)}`.

## audit (`/api/audit`) — operator role, `read` scope

| Method & Path | Notes |
|---|---|
| `GET /` | `?page&page_size&action&username&q&from&to` → `Page<AuditEntry>` |
| `GET /actions` | Distinct action names in use |
| `GET /export.csv` | Same filters, `text/csv` |

## settings (`/api/settings`)

| Method & Path | Role | Notes |
|---|---|---|
| `GET /` | viewer | `{public_endpoint, default_dns, default_mtu, default_keepalive, default_client_allowed_ips, audit_retention_days, stats_retention_days, ui_refresh_seconds, custom_scripts_allowed}` |
| `PATCH /` | admin | Partial update; validated (`public_endpoint` hostname/IP without port, `default_dns` a list of IPs, `default_mtu` 1280–1500) |

## system (`/api/system`)

| Method & Path | Role | Notes |
|---|---|---|
| `GET /health` | public | `{status: "ok"}`; also served at `/api/health` |
| `GET /info` | viewer | `{version, backend_mode, wireguard_version, kernel_module, python_version, os, uptime_seconds, database_size_bytes, config_path, hostname}` |
| `GET /backup` | admin | `application/gzip` tar of DB + rendered configs; audited |
| `GET /export` | admin | JSON export of users/interfaces/peers/settings/audit, no secrets; audited |

---

See also: [API Keys & Automation](../guides/api-keys-and-automation.md),
[Security — authentication model](../guides/security.md#authentication-model).
