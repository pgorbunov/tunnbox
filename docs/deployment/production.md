# Production Deployment

For production, run TunnBox behind a reverse proxy with HTTPS.

## Using Caddy (Recommended)

Caddy handles HTTPS automatically using Let's Encrypt.

### 1. Update `docker-compose.yml`

Add the `caddy` service and restrict the TunnBox web port to localhost.

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
      - "127.0.0.1:8000:8000"  # Only listen locally
      - "51820:51820/udp"
    volumes:
      - ./data/wireguard:/etc/wireguard
      - ./data/app:/app/data
      - /lib/modules:/lib/modules:ro
    environment:
      - WG_DEFAULT_ENDPOINT=${WG_DEFAULT_ENDPOINT}
      - SECRET_KEY=${SECRET_KEY}
      - WG_DEFAULT_DNS=${WG_DEFAULT_DNS:-1.1.1.1}
      - CSRF_PROTECTION_ENABLED=true
      - CORS_ORIGINS=https://vpn.yourdomain.com

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

### 2. Create `Caddyfile`

```text
vpn.yourdomain.com {
    reverse_proxy tunnbox:8000
}
```

Replace `vpn.yourdomain.com` with your actual domain. Ensure DNS points to this server.

### 3. Start

```bash
docker compose up -d
```

Caddy obtains an SSL certificate automatically and redirects HTTP to HTTPS.

## Using Nginx

### 1. Install Nginx and Certbot

```bash
apt install nginx certbot python3-certbot-nginx
```

### 2. Create Nginx config

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
```

### 3. Obtain SSL certificate

```bash
certbot --nginx -d vpn.yourdomain.com
```

Certbot modifies the Nginx config to add TLS and sets up auto-renewal.

### 4. Update TunnBox config

When using Nginx as a reverse proxy, bind TunnBox to localhost only:

```yaml
ports:
  - "127.0.0.1:8000:8000"
  - "51820:51820/udp"
```

Set `TRUSTED_PROXIES` to include the Nginx IP (typically `127.0.0.1`).

## Firewall Configuration

### UFW (Ubuntu)

```bash
ufw allow 22/tcp        # SSH
ufw allow 80/tcp        # HTTP (Let's Encrypt / redirect)
ufw allow 443/tcp       # HTTPS
ufw allow 51820/udp     # WireGuard
ufw enable
```

For additional WireGuard interfaces, open their ports too:
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

Docker's built-in health check reports status:
```bash
docker inspect --format='{{.State.Health.Status}}' tunnbox
```

### Logs

Application logs go to stdout/stderr:
```bash
# Follow logs in real time
docker compose logs -f tunnbox

# Last 100 lines
docker compose logs --tail=100 tunnbox
```

Docker log rotation is configured in the compose file (10 MB, 3 files).

### Audit logs

Admin actions are logged in the database. Export them via the API:
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/privacy/export \
  -o audit_export.json
```

### External monitoring

Point an uptime monitor at the health endpoint:
```
GET https://vpn.yourdomain.com/api/health
Expected: {"status": "healthy"}
```

## Security Best Practices

### SSH Hardening
- Disable password authentication; use SSH keys only
- Change the default SSH port (optional)
- Install `fail2ban` for brute-force protection

### System Updates
Keep the host OS updated:
```bash
apt update && apt upgrade -y
```

Enable unattended security updates:
```bash
apt install unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

### Docker Image Updates
See the [Updating guide](../guides/updating.md) for safe update procedures.

### Production Environment Checklist

Refer to the [Configuration — Production Checklist](../getting-started/configuration.md#production-checklist) for a complete list of settings to verify before going live.
