# Architecture

TunnBox is a single Docker image: a FastAPI backend that serves both the REST API (under `/api`)
and the built SvelteKit frontend (static files, everything else). It manages WireGuard by
generating configuration and calling `wg`/`wg-quick`, not by replacing WireGuard.

## Component Overview

```
┌───────────────────────────────────────────────────────────┐
│                      Docker Container                      │
│                                                             │
│  ┌───────────────┐      ┌─────────────────────────────┐    │
│  │   SvelteKit   │◀────▶│         FastAPI (/api)       │    │
│  │   frontend    │      │                               │    │
│  │  (static,     │      │  auth · sessions · MFA        │    │
│  │   served at   │      │  interfaces · peers · share   │    │
│  │   / )         │      │  stats · audit · settings      │    │
│  └───────────────┘      │  background scheduler         │    │
│                          └───────────┬───────────────────┘    │
│                                      │                        │
│                          ┌───────────▼───────────────────┐    │
│                          │      SQLite (WAL mode)         │    │
│                          │  source of truth for interfaces │   │
│                          │  and peers                       │  │
│                          └───────────┬───────────────────┘    │
│                                      │ renders                │
│                          ┌───────────▼───────────────────┐    │
│                          │   WireGuard backend (real/mock) │   │
│                          │   wg / wg-quick, or simulated   │   │
│                          └───────────┬───────────────────┘    │
│                                      │                        │
│                          ┌───────────▼───────────────────┐    │
│                          │   .conf files (WG_CONFIG_PATH)  │   │
│                          └─────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
         │                                    │
     Port 8000                          Port 51820/udp (per interface)
     (Web UI + API)                     (WireGuard)
```

## The Database Is the Source of Truth

Interfaces and peers live in SQLite, not in `.conf` files. Every mutation (create, edit, enable,
disable, rotate keys, delete) writes to the database first, then **renders** the affected
interface's `.conf` file from the current database state. The app never hand-edits an existing
`.conf` file or reads it back to determine current state — the file is a derived artifact, safe
to delete and regenerate at any time by toggling the interface.

## Legacy Import on First Start

At startup, the app scans `WG_CONFIG_PATH` for any `<name>.conf` file that isn't already a known
interface in the database. For each one found, it parses the file and creates a matching
interface (and its peers) in the database — this is how a v1 installation (or any hand-managed
WireGuard setup) upgrades transparently: point TunnBox at an existing `/etc/wireguard`, and it
adopts what's there on first boot. If a legacy `peer_metadata` table exists from a v1 database, it
is consulted to recover peer names and stored private keys (matched by interface name + public
key) before being dropped. Import is idempotent and never overwrites a database row that already
exists — it only fills in interfaces/peers that aren't yet known.

## Background Jobs

A small asyncio scheduler runs registered jobs on independent intervals with error isolation (one
job failing doesn't stop the others):

| Job | Interval | Does |
|-----|----------|------|
| `stats_sampler` | `STATS_SAMPLE_SECONDS` (default 30s) | Polls the WireGuard backend for each active interface, computes rx/tx deltas against the peer's stored cumulative totals (handling counter resets), updates `last_handshake_at`, and writes a `peer_stats` row |
| `peer_expiry` | 60s | Disables any enabled peer whose `expires_at` has passed, re-renders and syncs the interface, audit-logs `peer.auto_disabled` |
| `retention` | 3600s (1h) | Prunes audit log entries, stats samples, expired sessions, and expired share links past their retention windows |
| reconcile | once, at startup | Runs the legacy import, then (real backend only) brings up every interface marked `enabled` and re-renders its config |

## WireGuard Backends

TunnBox talks to WireGuard through a small interface (`WireGuardBackend`) with two
implementations, selected by `WG_BACKEND_MODE`:

- **`real`** — calls the actual `wg` and `wg-quick` binaries (`up`, `down`, `sync` via
  `wg syncconf`, `dump` via `wg show <iface> dump`). Requires Linux with WireGuard available
  (kernel module or the wireguard-go userspace fallback).
- **`mock`** — keeps an in-memory "active" set and generates deterministic, pseudo-random but
  monotonically growing simulated traffic and handshake data per peer. No real network changes
  happen. Used automatically on non-Linux platforms or when the `wg` binary is missing, so the UI
  and API can be developed and tested without a working WireGuard install.
- **`auto`** (default) — picks `real` on Linux with `wg`/`wg-quick` on `PATH`, otherwise `mock`.

Keypairs are generated in Python (X25519 via the `cryptography` package) rather than by shelling
out to `wg genkey`.

## Schema Overview

SQLite, WAL mode, foreign keys on. Migrations are versioned and applied at startup
(`schema_version` table tracks the current version).

| Table | Purpose |
|-------|---------|
| `users` | Accounts: username, bcrypt hash, role, active flag, encrypted TOTP secret, lockout state |
| `recovery_codes` | Hashed MFA recovery codes, one-time use |
| `sessions` | Server-side sessions: hashed refresh token, IP/user agent, sliding + absolute expiry, revocation |
| `refresh_token_history` | Every rotated-out refresh token hash, used to detect reuse (theft) |
| `api_keys` | Hashed API keys, scopes, prefix (for display), expiry, revocation |
| `interfaces` | WireGuard interfaces: encrypted private key, public key, address(es), port, DNS/MTU/scripts, enabled flag |
| `peers` | Peers: encrypted private key (nullable), encrypted PSK, allowed IPs, client-side allowed IPs, keepalive, expiry, cumulative rx/tx |
| `peer_stats` | Time series of rx/tx deltas and online state per peer, indexed by `(peer_id, ts)` |
| `share_links` | Hashed one-time/expiring share tokens for peer configs |
| `audit_logs` | Every mutation: actor, action, target, JSON details, IP, timestamp |
| `settings` | Key-value store for runtime settings (see [Configuration](../getting-started/configuration.md#runtime-settings-settings-page)) |

## Data Flow

### Interface creation
1. `POST /api/interfaces` validates the request (name pattern, CIDR, port range).
2. The backend generates an X25519 keypair, encrypts the private key, and inserts the interface row.
3. The `.conf` is rendered and, if `enabled`, the interface is brought up (real backend) or marked
   active (mock).

### Peer connection
1. `POST /api/interfaces/{name}/peers` generates a keypair and PSK for the peer, resolves
   `allowed_ips` (auto or explicit), and inserts the peer row.
2. The interface's `.conf` is re-rendered; if active, `wg syncconf` applies the change without a
   restart.
3. The user downloads the client config, scans a QR code, or sends a share link — see
   [Peer Management](./peer-management.md).
4. The client connects to `public_endpoint:listen_port`.

### Authentication
1. `POST /api/auth/login` verifies the bcrypt hash; if MFA is enabled, returns `mfa_required` and
   an `mfa_token` instead of a session.
2. On success, a session row is created, an access JWT is issued, and a refresh token is set as an
   httpOnly cookie.
3. `POST /api/auth/refresh` validates and rotates the cookie, extends the session, and issues a
   new access token.

See [Security](./security.md) for the full auth, MFA, and API-key model.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Pydantic v2, SQLite via `aiosqlite` (WAL) |
| Frontend | SvelteKit 2, Svelte 5, Tailwind CSS 4, TypeScript |
| Auth | Server-side sessions, JWT access tokens, bcrypt, TOTP (`pyotp`) |
| Secrets | Fernet (AES-128-CBC + HMAC-SHA256) with PBKDF2-derived keys |
| VPN | WireGuard kernel module, with a wireguard-go userspace fallback |
| Container | Docker, capabilities dropped except `NET_ADMIN`/`SYS_MODULE`/`MKNOD` |

## File System Layout

```
/app/backend/app/       # FastAPI application code
/app/frontend/build/    # Compiled SvelteKit frontend (served as static files)
/app/data/               # Mounted from ./data/app
  tunnbox.db              # SQLite database
  .secret_key             # Generated SECRET_KEY, if you didn't set one
/etc/wireguard/           # Mounted from ./data/wireguard
  wg0.conf, wg1.conf, ... # Rendered interface configs (derived, not authoritative)
```
