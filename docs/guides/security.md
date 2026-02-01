# Security Guide

## Authentication

TunnBox uses JSON Web Tokens (JWT) for stateless authentication.

### Access Tokens
- Algorithm: HS256
- Lifetime: 15 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- Sent in the `Authorization: Bearer <token>` header
- Contains: username, user ID, expiration timestamp

### Refresh Tokens
- Random URL-safe string (not a JWT)
- Lifetime: 7 days (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`)
- Stored in an **httpOnly cookie** (not accessible to JavaScript)
- Cookie flags: `httponly=True`, `secure=True` (in production), `samesite=lax`
- Hashed with bcrypt before storage in the database
- **Token rotation**: Each refresh issues a new token and invalidates the old one

### Login Rate Limiting
- 5 login attempts per minute per IP address
- Tracked in memory by default
- For distributed setups, configure `RATE_LIMIT_REDIS_URL` to use Redis
- IP detection respects `X-Forwarded-For` when the client IP is in `TRUSTED_PROXIES`
- Returns HTTP 429 when exceeded

## CSRF Protection

CSRF protection is available but **disabled by default** (`CSRF_PROTECTION_ENABLED=false`).

When enabled:
- A CSRF token is set as a cookie (readable by JavaScript, `samesite=strict`, 24-hour expiry)
- State-changing requests (POST, PUT, DELETE) must include the token in the `X-CSRF-Token` header
- Token validation uses constant-time comparison (HMAC) to prevent timing attacks
- Exempt endpoints: login, setup, health check, API docs, GET/HEAD/OPTIONS requests

To enable:
```
CSRF_PROTECTION_ENABLED=true
```

## Private Key Encryption

Peer private keys are encrypted at rest in the database using:
- **Algorithm**: Fernet (AES-128-CBC + HMAC-SHA256)
- **Key derivation**: PBKDF2-SHA256 with 100,000 iterations
- **Salt**: 16 random bytes per key (unique per peer)
- **Storage format**: `base64(salt):base64(ciphertext)`

The encryption key is derived from the application's `SECRET_KEY`. Changing the `SECRET_KEY` will make existing encrypted keys unrecoverable.

## Security Headers

The backend sets the following headers on all responses:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (HTTPS only) |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'` |

## Audit Logging

All significant actions are logged to the `audit_logs` database table:

| Action | When |
|--------|------|
| `login` | Successful login |
| `logout` | User logout |
| `password_change` | Password updated |
| `create_interface` | Interface created |
| `update_interface` | Interface settings changed |
| `delete_interface` | Interface removed |
| `interface_up` | Interface brought up |
| `interface_down` | Interface brought down |
| `add_peer` | Peer added |
| `update_peer` | Peer settings changed |
| `remove_peer` | Peer deleted |
| `data_export` | Data exported via API |
| `settings_update` | Server settings changed |

Each log entry includes: user ID, action name, details, client IP address, and timestamp.

Audit logs can be exported by admins via `GET /api/privacy/export`.

## Container Security

### Minimal Capabilities
```yaml
cap_drop: [ALL]
cap_add:
  - NET_ADMIN    # Manage WireGuard network interfaces
  - SYS_MODULE   # Load WireGuard kernel module
  - MKNOD        # Create device nodes
```

### Privilege Escalation Prevention
```yaml
security_opt: [no-new-privileges:true]
```

### Resource Limits
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 1G
```

### Log Rotation
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

## Input Validation

| Input | Validation |
|-------|-----------|
| Interface name | Alphanumeric, `_`, `-`. Max 15 chars. No reserved names. |
| Peer name | Alphanumeric, `_`, `-`, space. Max 64 chars. |
| Listen port | Integer 1–65535 |
| Address | Valid CIDR notation (IPv4 or IPv6) |
| DNS | Valid IPv4 address or hostname |
| Persistent keepalive | Integer 0–65535 |
| PostUp/PostDown | Only iptables/ip6tables unless `WG_ALLOW_CUSTOM_SCRIPTS=true`. Blocks shell metacharacters. |
| Password | Minimum 8 characters |

## PostUp/PostDown Script Safety

By default (`WG_ALLOW_CUSTOM_SCRIPTS=false`), PostUp and PostDown commands are restricted:
- Only `iptables` and `ip6tables` commands are allowed
- Blocked patterns: `;`, `&&`, `||`, `|`, backticks, `$`, `curl`, `wget`, `nc`, `python`, `bash`, `sh`, `rm`, `chmod`

Set `WG_ALLOW_CUSTOM_SCRIPTS=true` only if you understand the risks and need custom commands.

## Recommendations

1. **Set a static `SECRET_KEY`** — Prevents session invalidation on restart and is required for private key decryption to survive restarts.
2. **Use HTTPS** — Put TunnBox behind a reverse proxy (Caddy or Nginx) with TLS. See [Production Deployment](../deployment/production.md).
3. **Enable CSRF protection** — Set `CSRF_PROTECTION_ENABLED=true` in production.
4. **Restrict CORS origins** — Set `CORS_ORIGINS` to your actual domain.
5. **Configure trusted proxies** — Set `TRUSTED_PROXIES` to your reverse proxy's IP for accurate rate limiting.
6. **Regular backups** — See [Backup & Restore](./backup-restore.md).
7. **Keep updated** — See [Updating](./updating.md).
