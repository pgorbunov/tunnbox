#!/bin/bash
set -euo pipefail

echo "========================================"
echo "  TunnBox - Starting..."
echo "========================================"

DATA_DIR="/app/data"
mkdir -p "$DATA_DIR" /etc/wireguard
chmod 700 /etc/wireguard

# Ensure /dev/net/tun exists (required for wireguard-go userspace fallback)
if [ ! -c /dev/net/tun ]; then
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200 || echo "[WARN] Could not create /dev/net/tun (missing MKNOD capability?)"
fi

# SECRET_KEY: use the env var if provided, otherwise generate once and persist it.
# The key signs sessions and encrypts stored private keys, so it must be stable across restarts.
if [ -z "${SECRET_KEY:-}" ]; then
    if [ -f "$DATA_DIR/.secret_key" ]; then
        export SECRET_KEY
        SECRET_KEY=$(cat "$DATA_DIR/.secret_key")
        echo "[INFO] Loaded SECRET_KEY from $DATA_DIR/.secret_key"
    else
        export SECRET_KEY
        SECRET_KEY=$(openssl rand -hex 32)
        (umask 077 && echo "$SECRET_KEY" > "$DATA_DIR/.secret_key")
        echo "[INFO] Generated a new SECRET_KEY and stored it in $DATA_DIR/.secret_key"
    fi
fi

# Public endpoint: auto-detect if not configured (only used to seed the setting on first run).
if [ -z "${WG_DEFAULT_ENDPOINT:-}" ] || [ "${WG_DEFAULT_ENDPOINT}" = "YOUR_SERVER_IP" ]; then
    echo "[WARN] WG_DEFAULT_ENDPOINT is not set; trying to detect the public IP..."
    DETECTED=$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)
    if [ -n "$DETECTED" ]; then
        export WG_DEFAULT_ENDPOINT="$DETECTED"
        echo "[INFO] Using detected endpoint: $WG_DEFAULT_ENDPOINT"
    else
        export WG_DEFAULT_ENDPOINT=""
        echo "[WARN] Could not detect the public IP. Set it later under Settings > General."
    fi
fi

# Kernel networking prerequisites
sysctl -w net.ipv4.ip_forward=1 > /dev/null 2>&1 || true
sysctl -w net.ipv6.conf.all.forwarding=1 > /dev/null 2>&1 || true

# NAT for VPN clients on the container's primary interface
PRIMARY_IFACE=$(ip route | awk '/default/ {print $5; exit}')
PRIMARY_IFACE=${PRIMARY_IFACE:-eth0}
echo "[INFO] Configuring NAT on $PRIMARY_IFACE"
iptables -t nat -C POSTROUTING -o "$PRIMARY_IFACE" -j MASQUERADE 2>/dev/null || \
    iptables -t nat -A POSTROUTING -o "$PRIMARY_IFACE" -j MASQUERADE 2>/dev/null || \
    echo "[WARN] Could not configure iptables NAT (missing NET_ADMIN?)"
if command -v ip6tables >/dev/null 2>&1; then
    ip6tables -t nat -C POSTROUTING -o "$PRIMARY_IFACE" -j MASQUERADE 2>/dev/null || \
        ip6tables -t nat -A POSTROUTING -o "$PRIMARY_IFACE" -j MASQUERADE 2>/dev/null || true
fi

# Existing WireGuard configs are owned by the application: it imports them into its database on
# first start and brings every enabled interface up itself, so nothing is started here.

echo "[INFO] Starting TunnBox on http://${APP_HOST:-0.0.0.0}:${APP_PORT:-8000}"
echo "========================================"

cd /app/backend
exec uvicorn app.main:app \
    --host "${APP_HOST:-0.0.0.0}" \
    --port "${APP_PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips='*'
