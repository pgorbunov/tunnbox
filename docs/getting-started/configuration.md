# Configuration

TunnBox has two layers of configuration:

- **Environment variables** — deployment-level settings (secrets, paths, ports, session
  lifetimes, rate limits). Set in `.env` or `docker-compose.yml`. Changing these requires a
  restart.
- **Runtime settings** — day-to-day defaults (public endpoint, DNS, retention). Edited live in
  the UI under **Settings**, stored in the database. No restart required.

## Environment Variables

Names are case-insensitive and can be set in `.env` (loaded automatically) or directly in
`docker-compose.yml`.

### Application

| Variable | Default | Notes |
|----------|---------|-------|
| `SECRET_KEY` | *(none — auto-generated)* | Root secret for signing sessions and encrypting stored private keys. Precedence: the environment variable wins if set; otherwise the app reads `<data dir>/.secret_key` (next to the database, `./data/app/.secret_key` in the default container layout) if it exists, or creates one there (mode `0600`) and reuses it on every subsequent start. Both the entrypoint script and the app itself implement this fallback, so it works whether or not `SECRET_KEY` was exported before `uvicorn` starts. **Set a static value in production** — see the warning below. |
| `APP_HOST` | `0.0.0.0` | Interface the app binds to inside the container. |
| `APP_PORT` | `8000` | Port the app listens on inside the container. |
| `DEBUG` | `false` | Enables verbose error responses (stack traces in JSON). Never enable in production. |
| `LOG_FORMAT` | `text` | `json` for structured (one-line JSON) logs. |

### Database

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_PATH` | `./data/tunnbox.db` | Path to the SQLite file (inside the container this is under `/app/data`, mounted from `./data/app`). |
| `DATABASE_URL` | *(none)* | Legacy `sqlite+aiosqlite:///...` connection string from v1. If set, it is converted to `DATABASE_PATH` automatically; prefer `DATABASE_PATH` for new installs. |

### WireGuard

| Variable | Default | Notes |
|----------|---------|-------|
| `WG_CONFIG_PATH` | `/etc/wireguard` | Directory for rendered `.conf` files. In mock mode, falls back to `./data/wireguard` if this path is not writable. |
| `WG_BACKEND_MODE` | `auto` | `auto` (real on Linux with `wg`/`wg-quick` installed, otherwise mock), `real`, or `mock`. |
| `WG_DEFAULT_ENDPOINT` | `""` | Seeds the runtime setting `public_endpoint` on first start. After that, edit it in Settings instead. |
| `WG_DEFAULT_DNS` | `1.1.1.1` | Seeds the runtime setting `default_dns` on first start. |
| `WG_ALLOW_CUSTOM_SCRIPTS` | `false` | Allows **admins only** to set arbitrary `PostUp`/`PostDown` commands on interfaces (operators can never set them, regardless of this flag). These run as root inside the container. Leave `false` unless you specifically need commands beyond iptables. |

### Sessions & Auth

| Variable | Default | Notes |
|----------|---------|-------|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Lifetime of the in-memory access token (JWT). |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Idle session lifetime; extended on each use (sliding window). |
| `SESSION_ABSOLUTE_DAYS` | `30` | Hard cap on session age, regardless of activity. |
| `LOGIN_RATE_LIMIT` | `10/minute` | Login attempts allowed per IP, e.g. `10/minute`, `5/hour`. |
| `LOCKOUT_THRESHOLD` | `8` | Failed logins for one username before it is locked. |
| `LOCKOUT_MINUTES` | `15` | Lockout duration once the threshold is hit. |

### Reverse Proxy & Cookies

| Variable | Default | Notes |
|----------|---------|-------|
| `TRUSTED_PROXIES` | `""` | Comma-separated IPs/CIDRs allowed to set `X-Forwarded-For` / `X-Forwarded-Proto`. Required for correct client IPs and `COOKIE_SECURE=auto` behind a proxy. |
| `CORS_ORIGINS` | empty unless `DEBUG=true` (then the dev origins `http://localhost:5173`, `http://127.0.0.1:5173`) | Comma-separated list of allowed CORS origins. In production (`DEBUG=false`), leave unset unless the frontend is served from a different origin than the API — the app and its API share an origin by default, so no CORS origins are needed there. |
| `COOKIE_SECURE` | `auto` | `auto` sets the `Secure` cookie flag when the request is HTTPS (directly, or via `X-Forwarded-Proto` from a trusted proxy); `true`/`false` force the flag. |

### Stats

| Variable | Default | Notes |
|----------|---------|-------|
| `STATS_SAMPLE_SECONDS` | `30` | How often the background sampler polls the WireGuard backend for peer counters. |
| `STATS_RETENTION_DAYS` | `90` | How long raw `peer_stats` samples are kept before the retention job prunes them. |

::: warning SECRET_KEY
If `SECRET_KEY` is not set and no `./data/app/.secret_key` file exists, one is generated and
persisted automatically by the Docker entrypoint — you do not need to set it manually, but you
must keep `./data/app/` on persistent storage. If you delete or lose that file (or the
environment variable, if you did set one) without keeping a copy, **every session is invalidated
and every private key and MFA secret stored in the database becomes undecryptable.** Back up
`./data/app/.secret_key` alongside your database. See [Backup & Restore](../guides/backup-restore.md).
:::

## Runtime Settings (Settings page)

These are stored in the database (`settings` table) and editable by an **admin** under
**Settings > General / Data**. `GET /api/settings` returns them; any role can read, only admin
can `PATCH`.

| Setting | Default | Notes |
|---------|---------|-------|
| `public_endpoint` | seeded from `WG_DEFAULT_ENDPOINT` | Public IP or hostname clients connect to. Validated as a hostname or IP without a port. |
| `default_dns` | seeded from `WG_DEFAULT_DNS` | Default DNS server(s) for new peers, comma-separated. |
| `default_mtu` | `null` | Default interface MTU (1280–1500) when an interface doesn't set its own. |
| `default_keepalive` | `25` | Default `PersistentKeepalive` for new peers. |
| `default_client_allowed_ips` | `0.0.0.0/0, ::/0` | Default client-side `AllowedIPs` for new peers (full tunnel). |
| `audit_retention_days` | `90` | How long audit log entries are kept. |
| `stats_retention_days` | `90` | How long stats samples are kept (mirrors `STATS_RETENTION_DAYS` but editable at runtime). |
| `ui_refresh_seconds` | `10` | Polling interval the frontend uses for dashboard/interface/peer lists. |
| `custom_scripts_allowed` | — | Read-only reflection of `WG_ALLOW_CUSTOM_SCRIPTS`; not settable from the UI. |

## Docker Compose Reference

### Ports

| Mapping | Purpose |
|---------|---------|
| `8000:8000` | Web UI and API |
| `51820:51820/udp` | WireGuard (map one host port per interface) |

### Volumes

| Mount | Purpose |
|-------|---------|
| `./data/wireguard:/etc/wireguard` | Rendered WireGuard `.conf` files |
| `./data/app:/app/data` | SQLite database and `.secret_key` |
| `/lib/modules:/lib/modules:ro` | Kernel modules, read-only, for loading the WireGuard module |

### Capabilities

```yaml
cap_drop: [ALL]
cap_add: [NET_ADMIN, SYS_MODULE, MKNOD]
security_opt: [no-new-privileges:true]
```

### Health Check

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

## Production Checklist

- [ ] `WG_DEFAULT_ENDPOINT` (or the `public_endpoint` runtime setting) points at your public IP or domain
- [ ] `SECRET_KEY` is set to a static value (`openssl rand -hex 32`), or `./data/app/.secret_key` is on durable, backed-up storage
- [ ] Web UI port is bound to `127.0.0.1` and reverse-proxied with HTTPS — see [Production Deployment](../deployment/production.md)
- [ ] `TRUSTED_PROXIES` includes your reverse proxy's IP/CIDR
- [ ] `CORS_ORIGINS` matches your real domain if the frontend is served from elsewhere
- [ ] Data directories (`./data/`) are on persistent storage and backed up
- [ ] MFA is enabled on the admin account
