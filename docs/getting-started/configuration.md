# Configuration

Configuration is managed primarily through environment variables in your `.env` file or `docker-compose.yml`.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WG_DEFAULT_ENDPOINT` | **Required.** Server's public IP or domain name. | - |
| `WG_BACKEND_MODE` | `real` (Linux), `mock` (Windows/Mac), or `auto`. | `auto` |
| `SECRET_KEY` | JWT secret key. If empty, one is auto-generated on restart. | random |
| `WG_DEFAULT_DNS` | DNS server for VPN clients. | `1.1.1.1` |
| `APP_PORT` | Port the web UI listens on internally. | `8000` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token lifetime. | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime. | `7` |
| `CORS_ORIGINS` | Comma-separated list of allowed origins. | - |

> **Security Note**: For production, always set a static `SECRET_KEY`. If you rely on the auto-generated one, all user sessions will be invalidated whenever the container restarts. You can generate one with `openssl rand -hex 32`.

## Docker Compose Configuration

### Ports

*   `8000:8000`: The Web UI port.
*   `51820:51820/udp`: The standard WireGuard UDP port.

**Custom WireGuard Port**:
To use a different port (e.g., 12345), update the ports mapping:
```yaml
ports:
  - "8000:8000"
  - "12345:51820/udp"
```

### Volumes

*   `./data/wireguard`: Stores WireGuard configuration files (`wg0.conf`, keys).
*   `./data/app`: Stores the application database (`tunnbox.db`).
*   `/lib/modules`: Read-only mount required for the container to manage kernel modules.

### Capabilities (Security)

We use minimal capabilities for security:

```yaml
cap_drop: [ALL]
cap_add:
  - NET_ADMIN   # Required for network interface management
  - SYS_MODULE  # Required for kernel module loading
  - MKNOD
```
