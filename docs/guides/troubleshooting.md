# Troubleshooting

## Container Won't Start

### "Permission denied" or capability errors
The container requires specific Linux capabilities. Ensure your `docker-compose.yml` includes:
```yaml
cap_drop: [ALL]
cap_add: [NET_ADMIN, SYS_MODULE, MKNOD]
```

If running on a VPS with restricted Docker (e.g., some OpenVZ hosts), these capabilities may not be available. TunnBox requires a KVM or bare-metal host.

### "sysctl not allowed"
The container sets kernel parameters for IP forwarding. Some environments block this. Ensure the host allows:
```yaml
sysctls:
  - net.ipv4.ip_forward=1
  - net.ipv4.conf.all.src_valid_mark=1
  - net.ipv6.conf.all.forwarding=1
```

Alternatively, set these on the host directly:
```bash
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1
```

### Container starts but web UI is not accessible
1. Check the container is running: `docker compose ps`
2. Check logs for errors: `docker compose logs tunnbox`
3. Verify the port mapping: `docker compose port tunnbox 8000`
4. Ensure no firewall is blocking port 8000.

### Health check failing
The built-in health check calls `curl -f http://localhost:8000/api/health`. If it fails:
```bash
# Check from inside the container
docker exec tunnbox curl -f http://localhost:8000/api/health
```

If this returns `{"status":"healthy"}`, the issue is with external access (firewall, port mapping).

## Peers Can't Connect

### No handshake at all
1. **Check the endpoint**: Ensure `WG_DEFAULT_ENDPOINT` is set to your server's public IP or domain, not `127.0.0.1` or a private IP.
2. **Check the UDP port**: The WireGuard port (default `51820/udp`) must be open in your firewall and mapped in `docker-compose.yml`.
   ```bash
   # Test from outside the server
   nc -zvu your-server-ip 51820
   ```
3. **Check the interface is UP**: In the TunnBox UI, verify the interface toggle is enabled.
4. **Check the client config**: Download the config again and verify the `Endpoint` line has the correct IP and port.

### Handshake succeeds but no traffic flows
1. **Check AllowedIPs on the client**: For full tunnel, use `0.0.0.0/0, ::/0`. For split tunnel, specify only the VPN subnet (e.g., `10.0.0.0/24`).
2. **Check IP forwarding**: Ensure the container has `net.ipv4.ip_forward=1` set (see docker-compose sysctls).
3. **Check PostUp/PostDown rules**: If you're using NAT (masquerading), verify PostUp iptables rules are correct:
   ```
   PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
   PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
   ```
4. **Check the network interface name inside the container**: The outbound interface might not be `eth0`. Run:
   ```bash
   docker exec tunnbox ip route | grep default
   ```

### Intermittent disconnections
- Set **Persistent Keepalive** to `25` (seconds) on the peer. This is especially important when the client is behind NAT.
- Check if the server has resource limits that are too restrictive.

## DNS Problems

### Clients can connect but can't resolve domains
1. Verify the **DNS** setting on the interface or in server settings. Default is `1.1.1.1`.
2. If using a split tunnel, DNS queries may still go to the client's default resolver. Set the client's `DNS` explicitly in the config.
3. Check that the DNS server is reachable from the VPN subnet.

### DNS leaks
For full-tunnel configurations, ensure the client config has `DNS = 1.1.1.1` (or your preferred resolver) and `AllowedIPs = 0.0.0.0/0, ::/0`.

## Authentication Issues

### "401 Unauthorized" on every request
- Your access token has expired. The frontend should automatically refresh it. If it doesn't, try logging out and back in.
- If the container was restarted without a static `SECRET_KEY`, all tokens are invalidated. Set `SECRET_KEY` in your `.env` to prevent this.

### Locked out — too many login attempts
Login is rate-limited to 5 attempts per minute per IP. Wait 60 seconds and try again.

### Forgot the admin password
There is no password reset mechanism in the UI. To reset:
1. Stop the container: `docker compose down`
2. Delete the database: `rm ./data/app/tunnbox.db`
3. Start the container: `docker compose up -d`
4. Create a new admin account at `http://your-server:8000`

::: warning
Deleting the database removes all users, peer metadata, audit logs, and settings. WireGuard `.conf` files on disk are not affected, but TunnBox will no longer know about the peers in them.
:::

## Interface Errors

### "Interface name already exists"
Each WireGuard interface must have a unique name. Check for existing interfaces in the dashboard.

### "Name too long"
WireGuard interface names are limited to 15 characters (a Linux kernel restriction). Use short names like `wg0`, `wg1`, `office`.

### Interface won't come UP
Check the container logs:
```bash
docker compose logs tunnbox | grep -i error
```

Common causes:
- Another process is using the listen port.
- The address CIDR is invalid.
- The WireGuard kernel module isn't loaded. Check: `docker exec tunnbox lsmod | grep wireguard`

## Performance Issues

### High CPU usage
- Check if the container resource limits are too low. The default is 2 CPUs and 1 GB RAM.
- A large number of peers (hundreds) on a single interface can increase CPU usage during stats polling.

### Database locked errors
SQLite doesn't handle heavy concurrent writes well. For most TunnBox deployments (single admin, occasional changes), this should not be an issue. If you encounter lock errors, ensure only one instance of TunnBox is accessing the database.

## Getting Help

If your issue isn't covered here:
1. Check the container logs: `docker compose logs tunnbox`
2. Check the [FAQ](./faq.md)
3. Open an issue on [GitHub](https://github.com/pgorbunov/tunnbox/issues)
