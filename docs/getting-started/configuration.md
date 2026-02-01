# Configuration

Configuration is managed through environment variables in your `.env` file or `docker-compose.yml`.

## Environment Variables

### Application

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_HOST` | IP address the application binds to | `0.0.0.0` |
| `APP_PORT` | Port the web UI listens on | `8000` |
| `DEBUG` | Enable debug mode (verbose logging, relaxed security) | `false` |
| `DATABASE_URL` | SQLite connection string | `sqlite+aiosqlite:///./data/tunnbox.db` |

### WireGuard

| Variable | Description | Default |
|----------|-------------|---------|
| `WG_DEFAULT_ENDPOINT` | **Required.** Server's public IP or domain name. Clients connect to this address. | — |
| `WG_DEFAULT_DNS` | DNS server assigned to VPN clients | `1.1.1.1` |
| `WG_CONFIG_PATH` | Directory for WireGuard `.conf` files | `/etc/wireguard` |
| `WG_BACKEND_MODE` | `real` (Linux), `mock` (dev), or `auto` (detect platform) | `auto` |
| `WG_I_PREFER_BUGGY_USERSPACE_TO_POLISHED_KERNEL` | Force WireGuard userspace mode (required in Docker/WSL2) | `1` |
| `WG_ALLOW_CUSTOM_SCRIPTS` | Allow arbitrary PostUp/PostDown commands. **Security risk** — only iptables allowed when `false`. | `false` |

### Authentication

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key. **Set this in production.** Generate with `openssl rand -hex 32`. | Auto-generated |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime in minutes | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime in days | `7` |

::: warning
If `SECRET_KEY` is not set, a random key is generated on each container start. This means **all user sessions are invalidated** on every restart. Always set a static key in production.
:::

### Security

| Variable | Description | Default |
|----------|-------------|---------|
| `CSRF_PROTECTION_ENABLED` | Enable CSRF token validation on state-changing requests | `false` |
| `RATE_LIMIT_ENABLED` | Enable login rate limiting (5 attempts/min per IP) | `true` |
| `RATE_LIMIT_REDIS_URL` | Redis URL for distributed rate limiting. In-memory if not set. | — |
| `TRUSTED_PROXIES` | Comma-separated IPs trusted for `X-Forwarded-For` header | `127.0.0.1,172.17.0.1` |
| `CORS_ORIGINS` | Comma-separated allowed origins for CORS | `http://localhost:5173,http://127.0.0.1:5173` |

## Docker Compose Configuration

### Ports

| Mapping | Purpose |
|---------|---------|
| `8000:8000` | Web UI and API |
| `51820:51820/udp` | WireGuard default interface |

**Custom WireGuard port**: Change the host-side port while keeping the container port:
```yaml
ports:
  - "8000:8000"
  - "12345:51820/udp"  # Clients connect to port 12345
```

**Multiple interfaces**: Map additional UDP ports:
```yaml
ports:
  - "8000:8000"
  - "51820:51820/udp"
  - "51821:51821/udp"
```

### Volumes

| Mount | Purpose |
|-------|---------|
| `./data/wireguard:/etc/wireguard` | WireGuard config files and keys |
| `./data/app:/app/data` | SQLite database (`tunnbox.db`) |
| `/lib/modules:/lib/modules:ro` | Kernel modules (read-only, for WireGuard module loading) |

### Capabilities

The container drops all capabilities and adds only what is required:

| Capability | Purpose |
|------------|---------|
| `NET_ADMIN` | Manage network interfaces (WireGuard) |
| `SYS_MODULE` | Load the WireGuard kernel module |
| `MKNOD` | Create device nodes |

### Sysctls

Required kernel parameters set inside the container:

```yaml
sysctls:
  - net.ipv4.ip_forward=1              # Route IPv4 traffic between interfaces
  - net.ipv4.conf.all.src_valid_mark=1  # Required for WireGuard policy routing
  - net.ipv6.conf.all.forwarding=1      # Route IPv6 traffic (if using IPv6)
```

### Resource Limits

The default `docker-compose.yml` includes resource constraints:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 1G
    reservations:
      cpus: '0.5'
      memory: 256M
```

### Health Check

The container includes a built-in health check:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

## Production Checklist

Before deploying to production, verify:

- [ ] `WG_DEFAULT_ENDPOINT` is set to your public IP or domain
- [ ] `SECRET_KEY` is set to a static value (`openssl rand -hex 32`)
- [ ] Web UI port (8000) is behind a reverse proxy with HTTPS (see [Production Deployment](../deployment/production.md))
- [ ] `CSRF_PROTECTION_ENABLED=true`
- [ ] WireGuard UDP port(s) are open in your firewall
- [ ] `CORS_ORIGINS` is set to your actual domain (e.g., `https://vpn.yourdomain.com`)
- [ ] Data directories (`./data/`) are on persistent storage
- [ ] Backups are configured (see [Backup & Restore](../guides/backup-restore.md))
