# Troubleshooting

## Container Won't Start

### "Permission denied" or capability errors
Ensure `docker-compose.yml` includes:
```yaml
cap_drop: [ALL]
cap_add: [NET_ADMIN, SYS_MODULE, MKNOD]
```
Some restricted hosts (certain OpenVZ VPS providers) don't permit these. TunnBox needs a KVM or
bare-metal host, or a provider that allows them.

### "sysctl not allowed"
```yaml
sysctls:
  - net.ipv4.ip_forward=1
  - net.ipv4.conf.all.src_valid_mark=1
  - net.ipv6.conf.all.forwarding=1
```
If the host blocks this, set the sysctls on the host directly instead:
```bash
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1
```

### Web UI not reachable
1. `docker compose ps` — confirm the container is running.
2. `docker compose logs tunnbox` — check for startup errors.
3. `docker compose port tunnbox 8000` — confirm the port mapping.
4. Confirm no host firewall is blocking the port.

### Health check failing
```bash
docker exec tunnbox curl -f http://localhost:8000/api/health
# {"status": "ok"}
```
If this succeeds but external access doesn't, the problem is firewall/port-mapping, not the app.

## Peers Can't Connect

### No handshake at all
1. **Endpoint** — the `public_endpoint` setting (or `WG_DEFAULT_ENDPOINT`) must be a publicly
   reachable IP or hostname, not `127.0.0.1` or a private address (unless the client is on the
   same LAN).
2. **UDP port** — the interface's listen port must be open in your firewall and mapped in
   `docker-compose.yml`. Test from outside: `nc -zvu your-server-ip 51820`.
3. **Interface state** — confirm it shows active in the UI or `is_active: true` from
   `GET /api/interfaces/{name}`.
4. **Client config** — re-download it; if it was generated before an endpoint change, the old
   `Endpoint` line is stale.

### Handshake succeeds but no traffic flows
1. **Client `AllowedIPs`** — full tunnel needs `0.0.0.0/0, ::/0`; split tunnel needs the actual
   routes you want (see [Peer Management — split tunnel](./peer-management.md#split-tunnel-presets)).
2. **IP forwarding** — confirm the container has `net.ipv4.ip_forward=1` (see sysctls above).
3. **NAT rules** — for full tunnel, the interface needs PostUp/PostDown masquerade rules, which
   require `WG_ALLOW_CUSTOM_SCRIPTS=true`. See
   [Interface Management](./interface-management.md#postup-and-postdown-scripts).
4. **Outbound interface name** — the container's default route interface might not be `eth0`:
   ```bash
   docker exec tunnbox ip route | grep default
   ```

### Intermittent disconnections
Set `PersistentKeepalive` to `25` on the peer — important when the client is behind NAT.

## DNS Problems

- Confirm the interface or peer DNS setting (falls back to the global `default_dns` setting).
- On split tunnel, DNS queries may still go to the client's normal resolver unless `DNS` is set
  explicitly in the client config.
- For full tunnel, verify the client config has both `DNS = ...` and
  `AllowedIPs = 0.0.0.0/0, ::/0` to avoid leaks.

## Authentication Issues

### "401 Unauthorized" on every request
The access token expired; the frontend refreshes it automatically on a 401. If it keeps
happening, log out and back in. If the container restarted **without** a static `SECRET_KEY` and
without a persisted `./data/app/.secret_key`, every session is invalidated — see
[Configuration](../getting-started/configuration.md#environment-variables).

### Locked out — too many login attempts
- Too many requests from your IP → `429`, rate-limited by `LOGIN_RATE_LIMIT` (default
  `10/minute`). Wait and retry.
- Too many failed attempts for one **username** → `423 "Account temporarily locked"`, locked for
  `LOCKOUT_MINUTES` (default 15). A correct login after the lockout window resets the counter.

### Lost MFA device
- If someone else still has admin access, they can clear your MFA:
  `POST /api/users/{id}/mfa/reset` (**Settings > Users**). You then log in with just your
  password and can set MFA up again.
- If the locked-out account is the only admin and you also can't reset via the UI, reset the
  password from the CLI (this doesn't touch MFA, but combined with a manual database check it's
  the escape hatch):
  ```bash
  docker exec -it tunnbox python -m app.cli reset-password admin
  ```
  See [Security — resetting a password](./security.md#resetting-a-password-from-the-command-line).

### Cookies not set / login doesn't stick behind a reverse proxy
This is almost always `TRUSTED_PROXIES` or `COOKIE_SECURE` not matching your proxy setup:
- If `TRUSTED_PROXIES` doesn't include your proxy's IP/CIDR, TunnBox doesn't trust
  `X-Forwarded-Proto`, so `COOKIE_SECURE=auto` treats the request as plain HTTP and may not set the
  `Secure` flag your browser expects over HTTPS (or vice versa, depending on your proxy).
- Set `TRUSTED_PROXIES` to your proxy's IP or CIDR (e.g. `172.16.0.0/12` for the default Docker
  bridge, or your proxy container's IP), and if `auto` still misbehaves, force
  `COOKIE_SECURE=true` (when you're always behind HTTPS) or `false` (only for local/testing setups
  without TLS).
- See [Security — reverse proxy configuration](./security.md#reverse-proxy-configuration) and
  [Production Deployment](../deployment/production.md).

### Forgot the admin password
```bash
docker exec -it tunnbox python -m app.cli reset-password <username>
```
This resets the password, clears any lockout, and revokes that user's other sessions — no data is
lost. There's no need to delete the database.

## Interface Errors

### "Interface name already exists" / port already in use
Names and listen ports must be unique across interfaces. Check existing interfaces in the
dashboard or `GET /api/interfaces`.

### "Name too long" / invalid name
Interface names must match `^[a-zA-Z0-9_=+.-]{1,15}$` (a Linux kernel limit) and can't be `all`,
`default`, or `lo`.

### Interface won't come up
```bash
docker compose logs tunnbox | grep -i error
```
Common causes: the listen port is already in use by something else, the address CIDR is invalid,
or the WireGuard kernel module isn't loaded (`docker exec tunnbox lsmod | grep wireguard`).

## Performance

### High CPU
Check container resource limits (default 2 CPUs / 1 GB). A large number of peers increases stats
sampling cost; `STATS_SAMPLE_SECONDS` can be raised to reduce polling frequency.

### Database locked errors
SQLite (WAL mode) handles TunnBox's normal load fine. If you see lock errors, make sure only one
container instance is pointed at the same `./data/app/tunnbox.db`.

## Getting Help

1. `docker compose logs tunnbox`
2. Check the [FAQ](./faq.md)
3. Open an issue on [GitHub](https://github.com/pgorbunov/tunnbox/issues)
