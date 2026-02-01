# Installation

## System Requirements

| Requirement | Minimum |
|-------------|---------|
| OS | Linux with kernel 5.6+ (Ubuntu 22.04+ recommended) |
| Docker | Docker Engine 20.10+ with Docker Compose v2 |
| RAM | 256 MB (512 MB recommended) |
| Disk | 100 MB for the application + space for logs |
| CPU | 1 core (2 recommended) |

### Required Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 8000 | TCP | Web UI and API |
| 51820 | UDP | WireGuard (default; one per interface) |

If using a reverse proxy for HTTPS, you also need ports 80 and 443 TCP.

### Required Kernel Features

- WireGuard kernel module (built into kernel 5.6+, or install `wireguard-dkms` on older kernels)
- IP forwarding support (`net.ipv4.ip_forward`)

## Quick Start (Docker Image)

You do **not** need to clone the repository to run TunnBox.

### 1. Create a Project Directory

```bash
mkdir tunnbox && cd tunnbox
```

### 2. Create `docker-compose.yml`

Create a file named `docker-compose.yml` with the following content:

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

### 3. Configure and Start

```bash
# Download example .env configuration
curl -o .env https://raw.githubusercontent.com/pgorbunov/tunnbox/main/.env.example

# Edit .env file — set WG_DEFAULT_ENDPOINT to your public IP
nano .env

# Start the server
docker compose up -d
```

### 4. Verify the Installation

```bash
# Check the container is running
docker compose ps

# Check health endpoint
curl http://localhost:8000/api/health
# Expected: {"status":"healthy"}

# View logs for any errors
docker compose logs tunnbox
```

Open `http://your-server:8000` to create your admin account. See [First Setup](./first-setup.md) for a walkthrough.

---

## Build from Source

If you prefer to build the image yourself or contribute to development.

### 1. Clone the repository

```bash
git clone https://github.com/pgorbunov/tunnbox.git
cd tunnbox
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env  # Set WG_DEFAULT_ENDPOINT
```

### 3. Build and Start

```bash
docker compose up -d --build
```

### 4. Verify

```bash
docker compose ps
curl http://localhost:8000/api/health
```

---

## Development Setup (Windows/macOS)

TunnBox supports a **Mock Backend** for developing the UI on non-Linux systems.

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend Setup (Mock Mode)

The backend automatically switches to `mock` mode on non-Linux systems.

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` to view the app.

---

## Docker Commands Reference

```bash
# View logs (follow mode)
docker compose logs -f tunnbox

# Stop the service
docker compose down

# Restart
docker compose restart

# Check resource usage
docker stats tunnbox
```

## Next Steps

- [Configuration](./configuration.md) — All environment variables
- [First Setup](./first-setup.md) — Create your admin account and first VPN interface
