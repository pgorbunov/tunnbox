# FAQ

## General

### What is TunnBox?
TunnBox is a web-based management interface for WireGuard VPN servers. It provides a UI and REST API to create interfaces, manage peers, and monitor connections — without editing WireGuard config files by hand.

### Does TunnBox replace WireGuard?
No. TunnBox manages WireGuard configuration files and calls the `wg` and `wg-quick` CLI tools. WireGuard itself runs as a kernel module on the host (or in userspace within the container).

### Is TunnBox free?
Yes. TunnBox is open-source software released under the MIT License.

### What platforms does TunnBox support?
TunnBox runs on Linux with Docker. The WireGuard kernel module requires Linux kernel 5.6 or later (or the out-of-tree module on older kernels). For development, a mock backend allows running on Windows and macOS.

## Setup

### Do I need to install WireGuard on the host?
No. The Docker image includes the WireGuard userspace tools. The kernel module is typically already available on modern Linux kernels (5.6+). The container loads it automatically via the `/lib/modules` mount.

### Can I run TunnBox without Docker?
It is designed to run in Docker. Running natively is possible (FastAPI backend + built SvelteKit frontend) but is not officially supported or documented.

### What happens if I don't set SECRET_KEY?
A random key is generated on each startup. This means all user sessions (JWT tokens) are invalidated every time the container restarts. For production, always set a static `SECRET_KEY`.

### Can I use TunnBox with an existing WireGuard setup?
TunnBox manages its own configuration files in `/etc/wireguard/`. It does not read or modify configs created outside of TunnBox. If you have an existing setup, you would need to recreate your interfaces and peers through TunnBox.

## Networking

### What ports need to be open?
- **8000/tcp**: Web UI (or whichever port you map in docker-compose)
- **51820/udp**: WireGuard (default; one port per interface)
- **80/tcp and 443/tcp**: Only if using a reverse proxy for HTTPS

### Can I run multiple WireGuard interfaces?
Yes. Create additional interfaces in the UI with different names and listen ports. Map each additional UDP port in `docker-compose.yml`:
```yaml
ports:
  - "8000:8000"
  - "51820:51820/udp"
  - "51821:51821/udp"
```

### Can peers talk to each other?
By default, no — each peer is assigned a `/32` address and traffic routes through the server. To allow peer-to-peer communication, you would need to configure AllowedIPs on each peer to include the other peers' addresses and ensure IP forwarding is enabled.

### How do I route all client traffic through the VPN?
Set the client's `AllowedIPs` to `0.0.0.0/0, ::/0` and add NAT rules via PostUp/PostDown on the interface:
```
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
```

## Security

### Is the admin panel exposed to the internet?
By default, port 8000 is mapped to all interfaces. For production, restrict it to localhost and put it behind a reverse proxy with HTTPS. See the [Production Deployment](../deployment/production.md) guide.

### Are private keys stored securely?
Peer private keys are encrypted using Fernet symmetric encryption with PBKDF2 key derivation (100,000 iterations) and a random salt per key. Server private keys are stored in the WireGuard `.conf` files.

### Can I enable CSRF protection?
Yes. Set `CSRF_PROTECTION_ENABLED=true` in your `.env` file. This adds CSRF token validation on all state-changing requests (POST, PUT, DELETE).

### How does rate limiting work?
Login attempts are limited to 5 per minute per IP address. This is tracked in memory by default. For distributed deployments, configure `RATE_LIMIT_REDIS_URL` to use Redis.

## Maintenance

### How do I update TunnBox?
See the [Updating guide](./updating.md).

### How do I back up my data?
See the [Backup & Restore guide](./backup-restore.md).

### How do I reset the admin password?
There is no built-in password reset. You must delete the database (`./data/app/tunnbox.db`), restart the container, and create a new admin account. This removes all stored data. See [Troubleshooting](./troubleshooting.md) for details.

### Can I have multiple admin users?
The current version supports a single admin account created during initial setup. Additional user management is not available in the UI.

### Where are the logs?
Application logs are written to stdout/stderr and captured by Docker:
```bash
docker compose logs tunnbox
```
Audit logs (login, interface/peer changes) are stored in the database and can be exported via the API.
