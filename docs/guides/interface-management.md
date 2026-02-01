# Interface Management

Interfaces are WireGuard virtual network devices. Each interface has its own subnet, listen port, and set of peers.

## Creating an Interface

1. Navigate to the **Dashboard** or **Interfaces** page.
2. Click **New Interface**.
3. Fill in the details:
   - **Name**: A unique name, up to 15 characters (e.g., `wg0`, `office`). Only alphanumeric characters, `-`, and `_` are allowed.
   - **Listen Port**: The UDP port WireGuard listens on (e.g., `51820`). Must be unique per interface and mapped in `docker-compose.yml`.
   - **Address**: The server's IP in the VPN subnet in CIDR notation (e.g., `10.0.0.1/24`).
   - **DNS**: Optional DNS server for peers (defaults to server setting).
4. Click **Save**.

The interface is created in a DOWN state. Click the toggle switch to bring it UP.

::: tip
Reserved names (`lo`, `localhost`, `default`, `all`) are blocked to prevent conflicts with system interfaces.
:::

## Bringing Interfaces Up and Down

- **Toggle switch** in the UI, or via the API:
  ```bash
  # Bring up
  curl -X POST http://localhost:8000/api/interfaces/wg0/up \
    -H "Authorization: Bearer <token>"

  # Bring down
  curl -X POST http://localhost:8000/api/interfaces/wg0/down \
    -H "Authorization: Bearer <token>"
  ```
- Bringing an interface UP runs `wg-quick up`.
- Bringing it DOWN runs `wg-quick down`.
- Adding or removing peers on a running interface uses `wg syncconf` for live updates without downtime.

## PostUp and PostDown Scripts

PostUp and PostDown are shell commands executed when an interface comes up or goes down. The most common use case is NAT masquerading for full-tunnel VPN.

### Default behavior (WG_ALLOW_CUSTOM_SCRIPTS=false)

When custom scripts are disabled (the default), only `iptables` and `ip6tables` commands are allowed. Dangerous patterns (`;`, `&&`, `||`, `$()`, backticks, `curl`, `wget`, etc.) are blocked.

Example — enable NAT so peers can access the internet:

```
PostUp:   iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown: iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
```

`%i` is replaced by WireGuard with the interface name.

::: warning
The outbound interface inside the container may not be `eth0`. Check with:
```bash
docker exec tunnbox ip route | grep default
```
:::

### Custom scripts (WG_ALLOW_CUSTOM_SCRIPTS=true)

Set `WG_ALLOW_CUSTOM_SCRIPTS=true` in your `.env` to allow arbitrary commands. This is a security risk — only enable it if you need commands beyond iptables.

## Running Multiple Interfaces

You can create multiple interfaces, each with its own subnet and port. This is useful for:
- Separating user groups (e.g., `wg-employees` and `wg-contractors`)
- Different network policies per interface
- Isolating traffic

For each additional interface, map its UDP port in `docker-compose.yml`:

```yaml
ports:
  - "8000:8000"
  - "51820:51820/udp"   # wg0
  - "51821:51821/udp"   # wg1
  - "51822:51822/udp"   # wg2
```

Use non-overlapping subnets for each interface (e.g., `10.0.0.0/24`, `10.0.1.0/24`, `10.0.2.0/24`).

## Port Forwarding

To forward a specific port from the VPN to a peer, use PostUp/PostDown rules:

```
PostUp:   iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 8080 -j DNAT --to-destination 10.0.0.2:8080
PostDown: iptables -t nat -D PREROUTING -i eth0 -p tcp --dport 8080 -j DNAT --to-destination 10.0.0.2:8080
```

This forwards port 8080 on the server to peer `10.0.0.2`. Requires `WG_ALLOW_CUSTOM_SCRIPTS=true` if using non-iptables commands.

## Monitoring

The dashboard shows per-interface statistics:
- **Status**: UP or DOWN
- **Peer count**: Total and currently connected
- **Transfer**: Total bytes received and transmitted

For detailed per-peer stats, use the stats endpoint:
```bash
curl http://localhost:8000/api/interfaces/wg0/stats \
  -H "Authorization: Bearer <token>"
```

## Deleting an Interface

Deleting an interface removes:
- The WireGuard `.conf` file
- All associated peer metadata from the database
- The kernel interface (if it was UP)

This action cannot be undone. Client configs that reference this interface will stop working.
