# TunnBox

A modern web application for managing WireGuard VPN servers. Built with FastAPI and SvelteKit.

![Dashboard Screenshot](docs/screenshot.png)

## Features

- **Interface Management** — Create, configure, and monitor multiple WireGuard interfaces
- **Peer Management** — Add peers with automatic key generation and IP assignment
- **QR Code Generation** — Secure scan-to-connect QR codes for mobile clients
- **Real-time Stats** — Monitor bandwidth usage and connection status per peer
- **Secure Authentication** — JWT with refresh token rotation, bcrypt passwords, rate limiting
- **Audit Logging** — Track all admin actions with timestamps and IP addresses
- **Encrypted Key Storage** — Peer private keys encrypted at rest with Fernet/PBKDF2
- **Modern UI** — Dark-mode SvelteKit interface with responsive design

## Quick Start

```bash
# Create project directory
mkdir tunnbox && cd tunnbox

# Download config files
curl -o docker-compose.yml https://raw.githubusercontent.com/pgorbunov/tunnbox/main/docker-compose.yml
curl -o .env https://raw.githubusercontent.com/pgorbunov/tunnbox/main/.env.example

# Configure (required: set WG_DEFAULT_ENDPOINT to your public IP)
nano .env

# Start
docker compose up -d
```

Open `http://your-server:8000` and create your admin account.

### Requirements

- Linux with kernel 5.6+ (Ubuntu 22.04+ recommended)
- Docker Engine 20.10+ with Docker Compose v2

### Required Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 8000 | TCP | Web UI |
| 51820 | UDP | WireGuard |

## Configuration

Key environment variables (set in `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `WG_DEFAULT_ENDPOINT` | **Required.** Server's public IP or domain | — |
| `SECRET_KEY` | JWT signing key. Set for production. Generate: `openssl rand -hex 32` | Auto-generated |
| `WG_DEFAULT_DNS` | DNS server for VPN clients | `1.1.1.1` |
| `CSRF_PROTECTION_ENABLED` | CSRF token validation | `false` |
| `WG_ALLOW_CUSTOM_SCRIPTS` | Allow arbitrary PostUp/PostDown commands | `false` |

See the [full configuration reference](docs/getting-started/configuration.md) for all variables.

## Production Deployment

For production, put TunnBox behind a reverse proxy with HTTPS. Example with Caddy:

```yaml
# Add to docker-compose.yml
services:
  tunnbox:
    ports:
      - "127.0.0.1:8000:8000"  # Localhost only
      - "51820:51820/udp"

  caddy:
    image: caddy:latest
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on:
      - tunnbox

volumes:
  caddy_data:
```

```text
# Caddyfile
vpn.yourdomain.com {
    reverse_proxy tunnbox:8000
}
```

See the [production deployment guide](docs/deployment/production.md) for Nginx setup, firewall rules, and monitoring.

## Data Persistence

All data is stored in `./data/`:

| Path | Contents |
|------|----------|
| `./data/wireguard/` | WireGuard config files and keys |
| `./data/app/` | SQLite database (users, peers, audit logs) |

Back up this directory regularly. See the [backup guide](docs/guides/backup-restore.md).

## Documentation

Full documentation is in the [`docs/`](docs/) directory, or view it online once deployed.

- [Installation](docs/getting-started/installation.md)
- [First Setup](docs/getting-started/first-setup.md)
- [Configuration](docs/getting-started/configuration.md)
- [API Reference](docs/api/endpoints.md)
- [Security](docs/guides/security.md)
- [Troubleshooting](docs/guides/troubleshooting.md)

## Development

```bash
# Backend (auto-detects mock mode on non-Linux)
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLite (aiosqlite), Pydantic |
| Frontend | SvelteKit, Tailwind CSS 4, TypeScript |
| Auth | JWT (HS256), bcrypt, httpOnly cookies |
| VPN | WireGuard kernel module |
| Deployment | Docker with minimal capabilities |

## License

MIT License — See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome. Please open a pull request or file an issue on [GitHub](https://github.com/pgorbunov/tunnbox/issues).
