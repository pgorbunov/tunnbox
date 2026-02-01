# Peer Management

Peers are the clients (phones, laptops, servers) that connect to your WireGuard interfaces.

## Adding a Peer

1. Select an interface (e.g., `wg0`).
2. Click **Add Peer**.
3. Fill in the details:
   - **Name**: A friendly label for the device (e.g., "John's iPhone"). Up to 64 characters.
   - **Allowed IPs**: Set to `auto` to automatically assign the next available IP, or specify a CIDR manually (e.g., `10.0.0.5/32`).
   - **Persistent Keepalive**: Seconds between keepalive packets (default: 25). Set to 0 to disable. Useful for peers behind NAT.
4. Click **Save**.

TunnBox automatically generates a keypair for the peer. The private key is encrypted and stored in the database.

### Auto IP Assignment

When `allowed_ips` is set to `auto`, TunnBox calculates the next available IP in the interface's subnet. For example, if the interface address is `10.0.0.1/24`, the first peer gets `10.0.0.2/32`, the next gets `10.0.0.3/32`, and so on.

You can check the next available IP via the API:
```bash
curl http://localhost:8000/api/interfaces/wg0/next-ip \
  -H "Authorization: Bearer <token>"
```

## Connection Methods

### Mobile (QR Code)

1. Click the **QR Code** icon next to a peer.
2. Open the **WireGuard** app on your phone (available for iOS and Android).
3. Tap **Add a tunnel** > **Scan from QR code**.
4. Scan the QR code displayed in TunnBox.

The QR code is generated securely — the private key is never exposed in the URL. A signed JWT token with a 5-minute expiry is used to authorize the QR image request.

### Desktop (Config File)

1. Click the **Download** icon next to a peer.
2. Save the `.conf` file.
3. Import it into the WireGuard client:
   - **Windows/macOS**: Open WireGuard app > **Import tunnel(s) from file**
   - **Linux**: Copy to `/etc/wireguard/` and run `wg-quick up <name>`

### Manual Configuration

If you need to configure a client manually, download the config file and note these fields:
- `[Interface]` section: `PrivateKey`, `Address`, `DNS`
- `[Peer]` section: `PublicKey` (server's), `AllowedIPs`, `Endpoint`, `PersistentKeepalive`

## Full Tunnel vs Split Tunnel

### Full tunnel (route all traffic through VPN)

Set the client's `AllowedIPs` to `0.0.0.0/0, ::/0`. All traffic goes through the VPN. You must also configure NAT on the interface (see [Interface Management — PostUp/PostDown](./interface-management.md#postup-and-postdown-scripts)).

### Split tunnel (only VPN subnet)

Set `AllowedIPs` to just the VPN subnet (e.g., `10.0.0.0/24`). Only traffic destined for the VPN network goes through the tunnel. Internet traffic uses the client's normal connection.

## Monitoring Peers

The dashboard shows:
- **Status**: Green indicator = handshake within the last 180 seconds (online).
- **Transfer**: Total bytes uploaded and downloaded.
- **Last Handshake**: Timestamp of the most recent successful handshake.
- **Endpoint**: The peer's public IP and port (visible only when connected).

## Updating a Peer

You can change a peer's name, allowed IPs, or persistent keepalive. If the interface is active, changes are applied live using `wg syncconf`.

```bash
curl -X PUT http://localhost:8000/api/interfaces/wg0/peers/<public_key> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name", "persistent_keepalive": 30}'
```

## Removing a Peer

Removing a peer:
- Deletes the peer from the WireGuard config
- Removes peer metadata and encrypted private key from the database
- If the interface is active, the change is applied immediately

The client's config file will no longer work after removal.

## Mobile Setup Walkthrough

### iOS
1. Install **WireGuard** from the App Store.
2. In TunnBox, add a peer for the device.
3. Click the QR code icon and scan it with the WireGuard app.
4. Toggle the tunnel ON in the WireGuard app.
5. Optionally enable "On-Demand" activation under tunnel settings.

### Android
1. Install **WireGuard** from Google Play or F-Droid.
2. In TunnBox, add a peer for the device.
3. Tap the **+** button in the WireGuard app > **Scan from QR code**.
4. Scan the QR code from TunnBox.
5. Toggle the tunnel ON.

### Troubleshooting Mobile Connections
- Ensure `WG_DEFAULT_ENDPOINT` is set to a publicly reachable IP or domain.
- If on cellular, some carriers block UDP traffic on non-standard ports. Try using port `443` or `53` for WireGuard.
- Set `PersistentKeepalive` to `25` to maintain the connection behind mobile NAT.
