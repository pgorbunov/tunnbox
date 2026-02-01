# Production Deployment

For production environments, we recommend running TunnBox behind a secure reverse proxy with HTTPS.

## Using Caddy (Recommended)

Caddy is an easy-to-use web server that handles HTTPS automatically using Let's Encrypt.

### 1. Update `docker-compose.yml`

Add the `caddy` service and restrict the TunnBox web port to localhost.

```yaml
services:
  tunnbox:
    # ... existing config ...
    ports:
      - "127.0.0.1:8000:8000"  # Only listen internally
      - "51820:51820/udp"      # WireGuard port must stay public

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

Create a file named `Caddyfile` in your project root:

```text
vpn.yourdomain.com {
    reverse_proxy tunnbox:8000
}
```

Replace `vpn.yourdomain.com` with your actual domain.

### 3. Start

```bash
docker compose up -d
```

Caddy will automatically obtain an SSL certificate and redirect HTTP to HTTPS.

## Security Best Practices

### 1. SSH Hardening
Ensure your host server is secure. Disable password login and use SSH keys.

### 2. Firewall (UFW)
Configure UFW to allow only necessary ports:

```bash
ufw allow 22/tcp        # SSH
ufw allow 80/tcp        # HTTP (for Let's Encrypt)
ufw allow 443/tcp       # HTTPS
ufw allow 51820/udp     # WireGuard
ufw enable
```

### 3. Updates
Keep your Docker image updated:

```bash
docker compose pull
docker compose up -d
```
