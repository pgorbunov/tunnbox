# TunnBox

A modern, polished web application to manage WireGuard VPN servers. Built with FastAPI and SvelteKit.

![Dashboard Screenshot](docs/screenshot.png)

## Features

- **Interface Management**: Create, configure, and monitor WireGuard interfaces
- **Peer Management**: Add, edit, and remove peers with automatic key generation
- **QR Code Generation**: Scan-to-connect QR codes for mobile clients
- **Real-time Stats**: Monitor bandwidth usage and connection status
- **Secure Authentication**: JWT-based auth with refresh tokens
- **Modern UI**: Beautiful dark-mode interface with responsive design
- **Cross-Platform Development**: Includes a Mock backend for safe local development on Windows/macOS

---

## Quick Start (Pre-built Docker Image)

The easiest way to run TunnBox is using the official Docker image. You do **not** need to clone the repository.

### 1. Setup Directory
Create a directory for your VPN server:

```bash
mkdir tunnbox && cd tunnbox
```

### 2. Create `docker-compose.yml`
Save the following content to `docker-compose.yml`:

```yaml
services:
  tunnbox:
    image: pgorbunov/tunnbox:latest
    container_name: tunnbox
    restart: unless-stopped
    cap_drop: [ALL]
    cap_add: [NET_ADMIN, SYS_MODULE, MKNOD]
    security_opt: [no-new-privileges:true]
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv4.conf.all.src_valid_mark=1
      - net.ipv6.conf.all.forwarding=1
    ports:
      - "8000:8000"
      - "51820:51820/udp"
    volumes:
      - ./data/wireguard:/etc/wireguard
      - ./data/app:/app/data
      - /lib/modules:/lib/modules:ro
    environment:
      - WG_DEFAULT_ENDPOINT=${WG_DEFAULT_ENDPOINT:-YOUR_SERVER_IP}
      - WG_DEFAULT_DNS=1.1.1.1
```

### 3. Configure Environment

Download the example environment file:

```bash
curl -o .env https://raw.githubusercontent.com/pgorbunov/tunnbox/main/.env.example
```

Edit the file to set `WG_DEFAULT_ENDPOINT` (required) and `SECRET_KEY` (recommended):

```bash
# Generate a secure key (copy the output)
openssl rand -hex 32

# Open .env to edit
nano .env
```

### 4. Start the Server

```bash
docker compose up -d
```

Open `http://your-server:8000` to create your admin account.

---

## Build from Source (Advanced)

If you prefer to build the image yourself or contribute to development:

### Prerequisites

- Ubuntu 22.04+ (or Linux kernel 5.6+)
- Docker and Docker Compose

### Compile & Run

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/pgorbunov/tunnbox.git
    cd tunnbox
    ```

2.  **Configure Environment:**
    ```bash
    cp .env.example .env
    nano .env # Set WG_DEFAULT_ENDPOINT
    ```

3.  **Start with Build:**
    ```bash
    docker compose up -d --build
    ```

### Docker Commands

```bash
# View logs
docker compose logs -f

# Stop service
docker compose down

# Restart
docker compose restart
```

### Data Persistence

All data is stored in `./data` in your project directory:

- `./data/wireguard/` - WireGuard configs
- `./data/app/` - Application database

---

## Configuration

### Environment Variables

Configure via `.env` file or docker-compose environment:

| Variable | Description | Default |
|----------|-------------|---------|
| `WG_DEFAULT_ENDPOINT` | **Required.** Server's public IP or domain | - |
| `WG_BACKEND_MODE` | `real` (Linux), `mock` (Windows/Mac), or `auto` | `auto` |
| `SECRET_KEY` | JWT secret key (auto-generated if empty) | random |
| `WG_DEFAULT_DNS` | DNS server for VPN clients | `1.1.1.1` |
| `APP_PORT` | Web UI port | `8000` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token expiration | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token expiration | `7` |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | - |

> **Note on `SECRET_KEY`**: If slightly undefined, a secure key is auto-generated on startup. However, this means **all user sessions will be invalidated** whenever the container restarts. For production, set a static `SECRET_KEY`.

### Custom WireGuard Port

To use a different WireGuard port, edit `docker-compose.yml`:

```yaml
ports:
  - "8000:8000"
  - "12345:51820/udp"  # Change 12345 to your port
```

---

## Production Deployment with HTTPS

### Using Caddy (Recommended)

1. Update `docker-compose.yml` to add Caddy:

```yaml
services:
  tunnbox:
    # ... existing config ...
    ports:
      - "127.0.0.1:8000:8000"  # Only listen locally
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

2. Create `Caddyfile`:

```
vpn.yourdomain.com {
    reverse_proxy tunnbox:8000
}
```

3. Restart:

```bash
docker compose up -d
```

---

## Development Setup

The project now supports **cross-platform development**. You can develop the UI and backend logic on Windows or macOS using the **Mock Backend**.

### Prerequisites

*   Python 3.10+
*   Node.js 18+

### 1. Backend Setup

The backend automatically detects if you are on Linux or not. If not, it switches to `mock` mode, where WireGuard commands are simulated and config files are written to `./data/wireguard/` locally.

**Linux/macOS:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run server
uvicorn app.main:app --host 0.0.0.0 --reload
```

**Windows (PowerShell):**
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run server
uvicorn app.main:app --host 0.0.0.0 --reload
```

### 2. Frontend Setup

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` to view the app.

---

## Tech Stack

### Backend

- **FastAPI** - Modern Python web framework
- **SQLite** - Lightweight database (via `aiosqlite`)
- **Pydantic** - Data validation
- **python-jose** - JWT handling

### Frontend

- **SvelteKit** - Fast, modern web framework
- **Tailwind CSS 4** - Utility-first CSS
- **Lucide Icons** - Icon set
- **TypeScript** - Type safety

---

## Security Features

### Authentication & Authorization
- All API routes require authentication except `/api/auth/login` and `/api/auth/setup`
- Passwords hashed with bcrypt (salt rounds: 12)
- JWT access tokens expire after 15 minutes (configurable)
- Refresh tokens stored in httpOnly cookies
- Rate limiting on login endpoint (5 attempts per minute)
- First-run setup creates admin account securely

### HTTP Security Headers
- `X-Content-Type-Options: nosniff` - Prevents MIME sniffing
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-XSS-Protection: 1; mode=block` - XSS protection
- `Strict-Transport-Security` - Forces HTTPS (when behind proxy)
- `Content-Security-Policy` - Restricts resource loading

### Input Validation
- All user inputs validated with Pydantic models
- Interface/peer names restricted to alphanumeric characters
- File path traversal prevention
- SQL injection prevention via parameterized queries

### Container Security
- Runs with minimal required capabilities (`NET_ADMIN`, `SYS_MODULE`)
- No privileged mode required
- Dedicated volumes for data isolation
- Non-root user inside container

---


## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.