# FAQ

## General

### What is TunnBox?
A self-hosted web UI and REST API for managing WireGuard VPN servers — interfaces, peers,
monitoring, and onboarding — without editing config files by hand.

### Does TunnBox replace WireGuard?
No. It manages WireGuard configuration and calls `wg`/`wg-quick`. WireGuard itself runs as a
kernel module (or the wireguard-go userspace fallback) inside the container.

### Is TunnBox free?
Yes, MIT licensed.

### What platforms does it run on?
Linux with Docker for production (kernel 5.6+ for the built-in WireGuard module). A mock backend
lets the app run — with simulated stats, no real networking — on Windows/macOS for development.

## Setup

### Do I need WireGuard installed on the host?
No. The image includes the userspace tools; the kernel module, if present on the host, is loaded
via the `/lib/modules` mount.

### What happens if I don't set SECRET_KEY?
The Docker entrypoint generates one on first start and persists it to
`./data/app/.secret_key`, so restarts don't invalidate sessions as long as that file survives on
your mounted volume. Set `SECRET_KEY` explicitly (or make sure `.secret_key` is backed up) — see
[Configuration](../getting-started/configuration.md) and
[Security — encryption at rest](./security.md#encryption-at-rest).

### Can I use TunnBox with an existing WireGuard setup?
Yes — point `WG_CONFIG_PATH` at your existing `/etc/wireguard`. On first start, any `.conf` file
not already known to TunnBox is imported (interface + peers) automatically. See
[Architecture — legacy import](./architecture.md#legacy-import-on-first-start).

### I'm upgrading from TunnBox v1 — what changes?
See the [Updating guide](./updating.md#upgrading-from-v1): existing configs and peer names import
automatically, but all sessions are invalidated (everyone logs in again), and new security
features (MFA, roles, API keys, lockout) are opt-in from there.

## Networking

### What ports need to be open?
- `8000/tcp` — Web UI/API (or whatever host port you map it to)
- `51820/udp` — WireGuard, one UDP port per interface
- `80/tcp`, `443/tcp` — only if a reverse proxy handles HTTPS

### Can I run multiple WireGuard interfaces?
Yes. Create additional interfaces with distinct names, ports, and subnets, and map each port in
`docker-compose.yml`. See [Interface Management](./interface-management.md#running-multiple-interfaces).

### Can peers talk to each other?
By default no — each gets a `/32`/`/128` address and traffic routes through the server. Enabling
peer-to-peer requires custom `AllowedIPs`/routing beyond what the UI configures automatically.

### How do I route all client traffic through the VPN?
Use the **Full tunnel** split-tunnel preset on the peer, and add NAT PostUp/PostDown rules on the
interface (requires `WG_ALLOW_CUSTOM_SCRIPTS=true`). See
[Peer Management — split tunnel](./peer-management.md#split-tunnel-presets) and
[Interface Management — PostUp/PostDown](./interface-management.md#postup-and-postdown-scripts).

## Security

### Is the admin panel exposed to the internet by default?
The default `docker-compose.yml` maps port 8000 on all interfaces. For production, bind it to
`127.0.0.1` and put it behind a reverse proxy with HTTPS — see
[Production Deployment](../deployment/production.md).

### Are private keys stored securely?
Yes — peer and interface private keys and MFA secrets are encrypted at rest (Fernet, PBKDF2-derived
key from `SECRET_KEY`). See [Security — encryption at rest](./security.md#encryption-at-rest).

### Does TunnBox support MFA?
Yes — TOTP-based MFA with recovery codes, per user. See
[First Setup — enabling MFA](../getting-started/first-setup.md#enabling-mfa) and
[Security — multi-factor authentication](./security.md#multi-factor-authentication).

### Can I have multiple users with different permission levels?
Yes — roles are `admin`, `operator`, and `viewer`. Admins manage users under **Settings > Users**.
See [Security — roles](./security.md#roles).

### How does rate limiting work?
Login attempts are limited per IP (`LOGIN_RATE_LIMIT`, default `10/minute`), and repeated failures
against one username trigger a temporary account lockout (`LOCKOUT_THRESHOLD`/`LOCKOUT_MINUTES`).
See [Security — lockout & rate limiting](./security.md#lockout--rate-limiting).

## Automation

### Can I automate TunnBox without logging in through the UI?
Yes — create a scoped API key under **Settings > API keys** and call the same REST API the UI
uses. See [API Keys & Automation](./api-keys-and-automation.md).

## Maintenance

### How do I update TunnBox?
See [Updating](./updating.md).

### How do I back up my data?
See [Backup & Restore](./backup-restore.md) — and don't forget `SECRET_KEY`/`.secret_key`.

### How do I reset the admin password?
```bash
docker exec -it tunnbox python -m app.cli reset-password admin
```
No data loss, no downtime. See [Security](./security.md#resetting-a-password-from-the-command-line).

### Where are the logs?
```bash
docker compose logs tunnbox
```
Set `LOG_FORMAT=json` for structured logs. Audit logs (logins, config changes) live in the
database and are viewable/exportable under **Audit** or via `GET /api/audit`.
