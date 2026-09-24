# Production Deployment

Run TunnBox behind a reverse proxy that terminates HTTPS, and bind the web UI port to
`127.0.0.1` so it's only reachable through the proxy.

TunnBox brings its own interfaces up — on the real backend, any interface marked `enabled` is
started by the app itself at startup and after being created or edited. There's no separate
`wg-quick up` step to run yourself; the entrypoint script only prepares the container
(NAT/sysctls/tun device) and starts the app.

## Using Caddy (Recommended)

Caddy handles HTTPS automatically via Let's Encrypt.

### 1. `docker-compose.yml`

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
      - "127.0.0.1:8000:8000"   # only reachable through the proxy
      - "51820:51820/udp"
    volumes:
      - ./data/wireguard:/etc/wireguard
      - ./data/app:/app/data
      - /lib/modules:/lib/modules:ro
    environment:
      - WG_DEFAULT_ENDPOINT=${WG_DEFAULT_ENDPOINT}
      - SECRET_KEY=${SECRET_KEY}
      - WG_DEFAULT_DNS=${WG_DEFAULT_DNS:-1.1.1.1}
      # Trust the docker bridge network the caddy container is on, so X-Forwarded-For/-Proto
      # are honored for real client IPs and correct Secure-cookie behavior.
      - TRUSTED_PROXIES=172.16.0.0/12
      - COOKIE_SECURE=auto

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

### 2. `Caddyfile`

```text
vpn.yourdomain.com {
    reverse_proxy tunnbox:8000
}
```

Replace `vpn.yourdomain.com` and point DNS at this server.

### 3. Start

```bash
docker compose up -d
```

## Using Nginx

### 1. Install Nginx and Certbot

```bash
apt install nginx certbot python3-certbot-nginx
```

### 2. Nginx config

```nginx
# /etc/nginx/sites-available/tunnbox
server {
    listen 80;
    server_name vpn.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/tunnbox /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d vpn.yourdomain.com
```

### 3. Bind TunnBox to localhost and trust the proxy

```yaml
ports:
  - "127.0.0.1:8000:8000"
  - "51820:51820/udp"
environment:
  - TRUSTED_PROXIES=127.0.0.1
  - COOKIE_SECURE=auto
```

## TRUSTED_PROXIES and COOKIE_SECURE

Both matter as soon as TLS is terminated in front of TunnBox:

- **`TRUSTED_PROXIES`** — comma-separated IPs/CIDRs of the proxy. Without it, TunnBox ignores
  `X-Forwarded-For`/`X-Forwarded-Proto` and sees every request as coming from the proxy's own IP
  over plain HTTP — this breaks per-client rate limiting/lockout and `COOKIE_SECURE=auto`.
- **`COOKIE_SECURE`** — `auto` (default) marks the refresh cookie `Secure` only when the request
  is HTTPS, directly or via a trusted proxy's `X-Forwarded-Proto`. Force `true`/`false` if `auto`
  isn't behaving as expected for your setup (e.g. testing over plain HTTP with a proxy in front).

See [Security — reverse proxy configuration](../guides/security.md#reverse-proxy-configuration)
for the full explanation.

## Firewall Configuration

### UFW (Ubuntu)

```bash
ufw allow 22/tcp        # SSH
ufw allow 80/tcp        # HTTP (ACME / redirect)
ufw allow 443/tcp       # HTTPS
ufw allow 51820/udp     # WireGuard
ufw enable
```

Open additional UDP ports for extra interfaces:
```bash
ufw allow 51821/udp
```

### iptables

```bash
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p udp --dport 51820 -j ACCEPT
```

## Monitoring

### Container health

```bash
docker inspect --format='{{.State.Health.Status}}' tunnbox
```

### Logs

```bash
docker compose logs -f tunnbox            # follow
docker compose logs --tail=100 tunnbox    # last 100 lines
```

Set `LOG_FORMAT=json` for machine-parseable logs. Rotation is configured in the default
`docker-compose.yml` (10 MB × 3 files).

### Audit logs

```bash
curl -H "Authorization: Bearer <token>" \
  "https://vpn.yourdomain.com/api/audit/export.csv" \
  -o audit.csv
```

Operator role or above; see [Security — audit logging](../guides/security.md#audit-logging).

### External uptime monitoring

```
GET https://vpn.yourdomain.com/api/health
Expected: {"status": "ok"}
```

## Security Best Practices

- **SSH** — key-only auth, `fail2ban`, non-default port if you like.
- **System updates** — `apt update && apt upgrade -y`; consider `unattended-upgrades`.
- **Image updates** — see the [Updating guide](../guides/updating.md).
- **Backups** — include `SECRET_KEY`/`.secret_key`; see
  [Backup & Restore](../guides/backup-restore.md).
- Full checklist: [Configuration — production checklist](../getting-started/configuration.md#production-checklist).
