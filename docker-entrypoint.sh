#!/bin/bash
set -e

echo "========================================"
echo "  Tunnbox - Starting..."
echo "========================================"

# Ensure /dev/net/tun exists (required for wireguard-go)
if [ ! -d /dev/net ]; then
    mkdir -p /dev/net
fi
if [ ! -c /dev/net/tun ]; then
    mknod /dev/net/tun c 10 200
fi

# Generate SECRET_KEY if not set (SEC-027)
if [ -z "$SECRET_KEY" ]; then
    echo "[INFO] Generating random SECRET_KEY..."
    export SECRET_KEY=$(openssl rand -hex 32)
    # Store key to file for persistence
    echo "$SECRET_KEY" > /app/data/.secret_key
    chmod 600 /app/data/.secret_key
    echo "[INFO] SECRET_KEY generated and stored securely"
    # DO NOT log the actual key value
elif [ -f /app/data/.secret_key ]; then
    # Load existing key from file
    export SECRET_KEY=$(cat /app/data/.secret_key)
    echo "[INFO] Loaded existing SECRET_KEY from file"
fi

# Check if WG_DEFAULT_ENDPOINT is set (SEC-030)
if [ -z "$WG_DEFAULT_ENDPOINT" ]; then
    echo "[WARN] WG_DEFAULT_ENDPOINT is not set!"
    echo "[WARN] Attempting to auto-detect public IP..."
    # Use HTTPS and add timeout for security (SEC-030)
    export WG_DEFAULT_ENDPOINT=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || echo "YOUR_SERVER_IP")
    if [ "$WG_DEFAULT_ENDPOINT" = "YOUR_SERVER_IP" ]; then
        echo "[ERROR] Failed to detect public IP. Please set WG_DEFAULT_ENDPOINT environment variable."
    else
        echo "[INFO] Using endpoint: $WG_DEFAULT_ENDPOINT"
    fi
fi

# Enable IP forwarding (required for WireGuard)
echo "[INFO] Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1 > /dev/null 2>&1 || true
sysctl -w net.ipv6.conf.all.forwarding=1 > /dev/null 2>&1 || true

# Set up iptables for NAT (SEC-031: auto-detect interface)
echo "[INFO] Configuring iptables..."
# Auto-detect primary network interface
PRIMARY_IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
if [ -z "$PRIMARY_IFACE" ]; then
    echo "[WARN] Could not detect primary network interface, defaulting to eth0"
    PRIMARY_IFACE="eth0"
else
    echo "[INFO] Detected primary interface: $PRIMARY_IFACE"
fi
iptables -t nat -C POSTROUTING -o "$PRIMARY_IFACE" -j MASQUERADE 2>/dev/null || \
    iptables -t nat -A POSTROUTING -o "$PRIMARY_IFACE" -j MASQUERADE 2>/dev/null || true

# Start any existing WireGuard interfaces (SEC-032: add validation)
echo "[INFO] Starting existing WireGuard interfaces..."
for conf in /etc/wireguard/*.conf; do
    if [ -f "$conf" ]; then
        iface=$(basename "$conf" .conf)

        # Validate config file permissions (SEC-032)
        PERMS=$(stat -c "%a" "$conf" 2>/dev/null || stat -f "%Lp" "$conf" 2>/dev/null)
        if [ "$PERMS" != "600" ] && [ "$PERMS" != "400" ]; then
            echo "[WARN] Config $conf has insecure permissions ($PERMS), setting to 600"
            chmod 600 "$conf"
        fi

        # Validate config file ownership
        if [ "$(stat -c "%u" "$conf" 2>/dev/null || stat -f "%u" "$conf" 2>/dev/null)" != "0" ]; then
            echo "[WARN] Config $conf not owned by root, fixing ownership"
            chown root:root "$conf"
        fi

        # Validate config syntax (SEC-032)
        echo "[INFO] Validating config: $iface"
        if ! wg-quick strip "$conf" > /dev/null 2>&1; then
            echo "[ERROR] Invalid WireGuard config: $conf"
            continue
        fi

        # Start interface with proper error logging
        echo "[INFO] Bringing up interface: $iface"
        if ! wg-quick up "$iface" 2>&1; then
            echo "[ERROR] Failed to start interface: $iface"
        else
            echo "[INFO] Successfully started interface: $iface"
        fi
    fi
done

echo "[INFO] Starting Tunnbox server..."
echo "[INFO] Web UI: http://0.0.0.0:${APP_PORT}"
echo "========================================"

# Start the FastAPI application
cd /app/backend
exec uvicorn app.main:app \
    --host "${APP_HOST}" \
    --port "${APP_PORT}" \
    --proxy-headers \
    --forwarded-allow-ips='*'
