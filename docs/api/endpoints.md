# API Reference

TunnBox provides a RESTful API for automation and integration. All endpoints use JSON.

## Authentication

All endpoints require a Bearer token unless noted otherwise.

```
Authorization: Bearer <access_token>
```

Obtain a token by calling `POST /api/auth/login`.

## Base URL

```
http://your-server:8000/api
```

## Interactive Documentation

Start the server and visit:
- **Swagger UI**: `http://your-server:8000/api/docs`
- **ReDoc**: `http://your-server:8000/api/redoc`
- **OpenAPI Schema**: `http://your-server:8000/api/openapi.json`

---

## Health Check

### `GET /api/health`

No authentication required.

```bash
curl http://localhost:8000/api/health
```

```json
{"status": "healthy"}
```

---

## Authentication

### `POST /api/auth/setup`

Create the initial admin account. Only works when no users exist.

```bash
curl -X POST http://localhost:8000/api/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "securepassword"}'
```

```json
{"id": 1, "username": "admin", "is_admin": true}
```

### `GET /api/auth/check-setup`

Check if initial setup is needed. No authentication required.

```bash
curl http://localhost:8000/api/auth/check-setup
```

```json
{"setup_required": true}
```

### `POST /api/auth/login`

Authenticate and receive an access token. Uses OAuth2 form encoding.

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=admin&password=securepassword"
```

```json
{"access_token": "eyJ...", "token_type": "bearer"}
```

A refresh token is set as an httpOnly cookie in the response.

### `POST /api/auth/refresh`

Refresh the access token using the cookie-based refresh token.

```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  --cookie "refresh_token=<token>"
```

```json
{"access_token": "eyJ...", "token_type": "bearer"}
```

### `POST /api/auth/logout`

Invalidate the refresh token.

```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer <token>"
```

### `GET /api/auth/me`

Get the current user.

```bash
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <token>"
```

```json
{"id": 1, "username": "admin", "is_admin": true}
```

### `PATCH /api/auth/password`

Change the current user's password.

```bash
curl -X PATCH http://localhost:8000/api/auth/password \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "oldpass", "new_password": "newpass123"}'
```

Password must be at least 8 characters.

---

## Interfaces

### `GET /api/interfaces`

List all WireGuard interfaces.

```bash
curl http://localhost:8000/api/interfaces \
  -H "Authorization: Bearer <token>"
```

```json
[
  {
    "name": "wg0",
    "listen_port": 51820,
    "address": "10.0.0.1/24",
    "public_key": "abc123...",
    "is_active": true,
    "peer_count": 5,
    "active_peer_count": 2,
    "total_transfer_rx": 1048576,
    "total_transfer_tx": 2097152,
    "dns": "1.1.1.1",
    "post_up": "",
    "post_down": ""
  }
]
```

### `POST /api/interfaces`

Create a new interface. Returns `201 Created`.

```bash
curl -X POST http://localhost:8000/api/interfaces \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "wg0",
    "listen_port": 51820,
    "address": "10.0.0.1/24",
    "dns": "1.1.1.1"
  }'
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `name` | string | yes | Max 15 chars, alphanumeric + `_` `-` |
| `listen_port` | integer | yes | 1–65535 |
| `address` | string | yes | CIDR notation (e.g., `10.0.0.1/24`) |
| `dns` | string | no | IP or hostname |
| `post_up` | string | no | Requires `WG_ALLOW_CUSTOM_SCRIPTS=true` for non-iptables commands |
| `post_down` | string | no | Same as post_up |

### `GET /api/interfaces/{name}`

Get a specific interface.

```bash
curl http://localhost:8000/api/interfaces/wg0 \
  -H "Authorization: Bearer <token>"
```

### `PUT /api/interfaces/{name}`

Update an interface.

```bash
curl -X PUT http://localhost:8000/api/interfaces/wg0 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"dns": "8.8.8.8", "listen_port": 51821}'
```

### `DELETE /api/interfaces/{name}`

Delete an interface and all its peers. Returns `204 No Content`.

```bash
curl -X DELETE http://localhost:8000/api/interfaces/wg0 \
  -H "Authorization: Bearer <token>"
```

### `POST /api/interfaces/{name}/up`

Bring an interface up.

```bash
curl -X POST http://localhost:8000/api/interfaces/wg0/up \
  -H "Authorization: Bearer <token>"
```

```json
{"message": "Interface wg0 is now up"}
```

### `POST /api/interfaces/{name}/down`

Bring an interface down.

```bash
curl -X POST http://localhost:8000/api/interfaces/wg0/down \
  -H "Authorization: Bearer <token>"
```

### `GET /api/interfaces/{name}/stats`

Get real-time statistics for an interface and its peers.

```bash
curl http://localhost:8000/api/interfaces/wg0/stats \
  -H "Authorization: Bearer <token>"
```

```json
{
  "name": "wg0",
  "is_active": true,
  "peer_count": 3,
  "total_transfer_rx": 1048576,
  "total_transfer_tx": 2097152,
  "peers": [
    {
      "public_key": "abc...",
      "endpoint": "203.0.113.1:51820",
      "latest_handshake": 1706140800,
      "transfer_rx": 524288,
      "transfer_tx": 1048576
    }
  ]
}
```

---

## Peers

### `GET /api/interfaces/{interface_name}/peers`

List all peers for an interface.

```bash
curl http://localhost:8000/api/interfaces/wg0/peers \
  -H "Authorization: Bearer <token>"
```

```json
[
  {
    "name": "My Laptop",
    "public_key": "xyz...",
    "allowed_ips": "10.0.0.2/32",
    "endpoint": "203.0.113.1:54321",
    "latest_handshake": 1706140800,
    "transfer_rx": 524288,
    "transfer_tx": 1048576,
    "is_online": true,
    "persistent_keepalive": 25
  }
]
```

### `POST /api/interfaces/{interface_name}/peers`

Add a new peer. Returns `201 Created`.

```bash
curl -X POST http://localhost:8000/api/interfaces/wg0/peers \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Laptop",
    "allowed_ips": "auto",
    "persistent_keepalive": 25
  }'
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `name` | string | yes | Max 64 chars |
| `allowed_ips` | string | yes | CIDR or `"auto"` for next available IP |
| `persistent_keepalive` | integer | no | 0–65535 seconds (default: 25) |

### `GET /api/interfaces/{interface_name}/peers/{public_key}`

Get a specific peer.

### `PUT /api/interfaces/{interface_name}/peers/{public_key}`

Update a peer.

```bash
curl -X PUT http://localhost:8000/api/interfaces/wg0/peers/xyz... \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Work Laptop", "persistent_keepalive": 30}'
```

### `DELETE /api/interfaces/{interface_name}/peers/{public_key}`

Remove a peer. Returns `204 No Content`.

```bash
curl -X DELETE http://localhost:8000/api/interfaces/wg0/peers/xyz... \
  -H "Authorization: Bearer <token>"
```

### `GET /api/interfaces/{interface_name}/peers/config/{public_key}`

Download a peer's WireGuard client configuration file.

```bash
curl http://localhost:8000/api/interfaces/wg0/peers/config/xyz... \
  -H "Authorization: Bearer <token>" \
  -o peer.conf
```

Returns a `.conf` file (content-type: `text/plain`) ready to import into any WireGuard client.

### `POST /api/interfaces/{interface_name}/peers/qr/{public_key}`

Generate a signed QR token for secure QR code display. The token expires in 5 minutes.

```bash
curl -X POST http://localhost:8000/api/interfaces/wg0/peers/qr/xyz... \
  -H "Authorization: Bearer <token>"
```

```json
{"qr_token": "eyJ..."}
```

### `POST /api/qr-image`

Get a QR code PNG image using a signed token.

```bash
curl -X POST http://localhost:8000/api/qr-image \
  -H "Content-Type: application/json" \
  -d '{"token": "eyJ..."}' \
  -o qrcode.png
```

Returns a PNG image. No authentication header required — the signed token serves as authorization.

### `GET /api/interfaces/{interface_name}/next-ip`

Get the next available IP address in the interface's subnet.

```bash
curl http://localhost:8000/api/interfaces/wg0/next-ip \
  -H "Authorization: Bearer <token>"
```

```json
{"next_ip": "10.0.0.2/32"}
```

---

## Settings

### `GET /api/settings`

Get server settings (merges environment config with database overrides).

```bash
curl http://localhost:8000/api/settings \
  -H "Authorization: Bearer <token>"
```

```json
{
  "public_endpoint": "203.0.113.1",
  "wg_default_dns": "1.1.1.1",
  "wg_config_path": "/etc/wireguard"
}
```

### `PATCH /api/settings`

Update server settings. Admin only.

```bash
curl -X PATCH http://localhost:8000/api/settings \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"public_endpoint": "vpn.example.com"}'
```

### `GET /api/settings/retention`

Get data retention settings.

```json
{"enabled": true, "logs_retention_days": 90}
```

### `PATCH /api/settings/retention`

Update data retention settings. Admin only.

```bash
curl -X PATCH http://localhost:8000/api/settings/retention \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "logs_retention_days": 30}'
```

`logs_retention_days` must be between 1 and 365.

### `GET /api/settings/timezone`

Get the user's timezone preference.

```json
{"timezone": "UTC"}
```

### `PATCH /api/settings/timezone`

Update timezone preference.

```bash
curl -X PATCH http://localhost:8000/api/settings/timezone \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"timezone": "America/New_York"}'
```

---

## Privacy / Data Export

### `GET /api/privacy/export`

Export all non-sensitive data as a JSON file. Admin only.

```bash
curl http://localhost:8000/api/privacy/export \
  -H "Authorization: Bearer <token>" \
  -o export.json
```

The export includes users (no passwords), peer metadata (no private keys), audit logs, and settings. An audit log entry is created for the export itself.

---

## System

### `GET /api/system/info`

Get version and system information.

```bash
curl http://localhost:8000/api/system/info \
  -H "Authorization: Bearer <token>"
```

```json
{
  "frontend_version": "1.0.0",
  "backend_version": "1.0.0",
  "wireguard_version": "1.0.20210914",
  "docker_version": "24.0.7",
  "os_name": "Linux",
  "os_version": "6.1.0",
  "python_version": "3.11.6",
  "database_type": "sqlite",
  "github_url": "https://github.com/pgorbunov/tunnbox",
  "documentation_url": "https://pgorbunov.github.io/tunnbox",
  "license": "MIT"
}
```

---

## Error Responses

All errors return JSON with a `detail` field:

```json
{"detail": "Not authenticated"}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request (validation error) |
| 401 | Not authenticated or token expired |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 409 | Conflict (e.g., duplicate interface name) |
| 422 | Validation error (Pydantic) |
| 429 | Rate limited (too many login attempts) |
| 500 | Internal server error |
