# Architecture

TunnBox is a web-based management layer for WireGuard. It does not replace WireGuard — it generates and manages WireGuard configuration files and interacts with the `wg` and `wg-quick` CLI tools.

## Component Overview

```
┌─────────────────────────────────────────────────────┐
│                   Docker Container                   │
│                                                     │
│  ┌──────────────┐     ┌──────────────────────────┐  │
│  │   SvelteKit  │────▶│       FastAPI Backend     │  │
│  │   Frontend   │     │                          │  │
│  │  (Static)    │     │  ┌────────────────────┐  │  │
│  └──────────────┘     │  │   Auth (JWT/bcrypt) │  │  │
│                       │  ├────────────────────┤  │  │
│                       │  │   WireGuard Service │  │  │
│                       │  │   (wg / wg-quick)   │  │  │
│                       │  ├────────────────────┤  │  │
│                       │  │   SQLite Database   │  │  │
│                       │  └────────────────────┘  │  │
│                       └──────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │           WireGuard Kernel Module             │   │
│  │         (via NET_ADMIN capability)            │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
         │                           │
    Port 8000                  Port 51820/udp
    (Web UI)                   (WireGuard VPN)
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | SvelteKit, Tailwind CSS 4, TypeScript |
| Backend | FastAPI (Python), Pydantic |
| Database | SQLite via aiosqlite (async) |
| Authentication | JWT (HS256), bcrypt, httpOnly cookies |
| VPN | WireGuard kernel module, `wg` / `wg-quick` CLI |
| Container | Docker with minimal capabilities |

## Data Flow

### Interface Creation
1. User submits interface form in the UI.
2. Frontend sends `POST /api/interfaces` with name, port, address.
3. Backend validates input (name length, CIDR format, port range).
4. Backend generates a WireGuard keypair using `wg genkey` / `wg pubkey`.
5. Backend writes a `.conf` file to `/etc/wireguard/`.
6. Interface metadata is stored in the database.

### Peer Connection
1. User adds a peer via the UI.
2. Backend generates a keypair for the peer.
3. The peer's public key and allowed IPs are added to the interface's `.conf` file.
4. The private key is encrypted (Fernet + PBKDF2) and stored in the database.
5. If the interface is active, `wg syncconf` applies the change live.
6. User downloads the client config or scans a QR code.
7. The client connects to the server's public endpoint on the WireGuard UDP port.

### Authentication Flow
1. User submits credentials to `POST /api/auth/login`.
2. Backend verifies password against bcrypt hash.
3. Backend issues a short-lived JWT access token (15 min default).
4. Backend issues a refresh token stored in an httpOnly cookie.
5. When the access token expires, the frontend calls `POST /api/auth/refresh`.
6. The backend validates the refresh token cookie, rotates it, and issues a new access token.

## WireGuard Backend Modes

TunnBox uses a strategy pattern for WireGuard operations:

- **Real mode** (`WG_BACKEND_MODE=real`): Calls actual `wg` and `wg-quick` binaries. Requires Linux with the WireGuard kernel module.
- **Mock mode** (`WG_BACKEND_MODE=mock`): Simulates WireGuard operations using the filesystem. Used for development on Windows/macOS.
- **Auto mode** (`WG_BACKEND_MODE=auto`, default): Detects the platform and selects real or mock automatically.

## Database Schema

TunnBox uses five tables:

| Table | Purpose |
|-------|---------|
| `users` | Admin accounts (username, bcrypt password hash) |
| `peer_metadata` | Peer names, encrypted private keys, interface associations |
| `audit_logs` | Timestamped log of all admin actions with IP addresses |
| `refresh_tokens` | Hashed refresh tokens with expiry timestamps |
| `settings` | Key-value store for runtime settings overrides |

## File System Layout

Inside the container:

```
/app/                      # Application code
  backend/app/             # FastAPI application
  frontend/build/          # Compiled SvelteKit frontend
/app/data/                 # Mounted: ./data/app
  tunnbox.db               # SQLite database
/etc/wireguard/            # Mounted: ./data/wireguard
  wg0.conf                 # WireGuard interface configs
  wg1.conf
```

## Security Layers

TunnBox applies defense-in-depth:

1. **Container level**: Minimal capabilities (`NET_ADMIN`, `SYS_MODULE`, `MKNOD`), `no-new-privileges`, resource limits.
2. **Network level**: CORS restrictions, trusted proxy configuration, rate limiting on login.
3. **Application level**: JWT authentication, CSRF protection (optional), security headers (HSTS, CSP, X-Frame-Options).
4. **Data level**: bcrypt for passwords, Fernet encryption for private keys, parameterized SQL queries.
5. **Input level**: Strict validation on interface names, peer names, CIDR addresses, port numbers, and PostUp/PostDown scripts.
