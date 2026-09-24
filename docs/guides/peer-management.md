# Peer Management

Peers are the clients (phones, laptops, servers) that connect to a WireGuard interface. Peers
belong to exactly one interface.

## Creating a Peer

From an interface page, click **Add Peer** (`POST /api/interfaces/{name}/peers`):

- **Name** — a friendly label.
- **Allowed IPs** — leave as `"auto"` (or omit) to assign the next free address in the
  interface's subnet(s); or provide a CIDR/list explicitly.
- **Split tunnel** — see below.
- **DNS override** — per-peer `client_dns`, otherwise falls back to the interface's DNS, then the
  global default.
- **Persistent keepalive** — seconds between keepalives (default from the `default_keepalive`
  setting, normally 25). Useful when the peer is behind NAT.
- **Expiry** — none, or a preset (1 day / 7 days / 30 days) / custom date-time.
- **Notes** — free text.

TunnBox generates the peer's keypair and a preshared key server-side; the private key is
encrypted before being stored. You never need to provide a public key yourself.

### Auto IP Assignment

With `allowed_ips: "auto"` (or omitted), TunnBox scans the interface's address CIDR(s) and picks
the next unused host, for both IPv4 and IPv6 when the interface is dual-stack. Check the next
free address ahead of time:

```bash
curl https://vpn.example.com/api/interfaces/wg0/next-ip \
  -H "Authorization: Bearer <token>"
# {"allowed_ips": "10.8.0.2/32"}
```

### Server-Side AllowedIPs Policy

When you set `allowed_ips` explicitly (instead of `"auto"`), it's validated against the
interface's own network:

- Each address must be a **host route inside the interface's subnet(s)** (e.g. `10.8.0.5/32`
  within a `10.8.0.0/24` interface) — this is what the server actually accepts as that peer's
  source address, not the routes the client sends traffic to (that's `client_allowed_ips`, see
  split tunnel below).
- A **wider route** (anything less specific than a single host, e.g. `10.8.0.0/28`) is
  **admin-only** — an operator's request with a non-host route is rejected.
- **`0.0.0.0/0` and `::/0` are never allowed** here, regardless of role — a default route as a
  peer's server-side `allowed_ips` would let that peer claim traffic for the whole interface.
- An address that duplicates or overlaps another peer's already-assigned `allowed_ips` on the
  same interface returns `409 Conflict`.

## Split Tunnel Presets

The peer's own `client_allowed_ips` field controls what the *client* routes through the tunnel
(this is separate from `allowed_ips`, the server-side entry that restricts what source IPs the
server accepts from that peer). The UI offers presets when creating or editing a peer:

| Preset | `client_allowed_ips` |
|--------|----------------------|
| Full tunnel | `0.0.0.0/0, ::/0` — all client traffic goes through the VPN |
| LAN only | `10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16` plus the interface's own subnet |
| Interface subnet only | Just the interface's address CIDR(s) — only VPN-hosted resources are reachable |
| Custom | Any CIDR list you enter |

This is stored per peer and only affects the rendered *client* config — the backend does not
interpret or restrict it further. Full tunnel requires NAT (PostUp/PostDown masquerade rules) on
the interface for clients to actually reach the internet — see
[Interface Management](./interface-management.md#postup-and-postdown-scripts).

## Expiry & Auto-Disable

Set `expires_at` when creating or editing a peer. A background job runs every 60 seconds and
disables (does not delete) any enabled peer whose `expires_at` has passed — the interface config
is re-rendered and, if active, synced live. This is logged as `peer.auto_disabled` with actor
`system`. A disabled peer keeps its data and can be re-enabled and given a new expiry at any time.

## Enable / Disable

`POST /api/peers/{id}/enable` and `POST /api/peers/{id}/disable` toggle a peer without deleting
it. A disabled peer is dropped from the rendered `.conf` (and from a live `wg syncconf`) but its
row, keys, and history stay in the database.

## Key Rotation

`POST /api/peers/{id}/rotate-keys` generates a brand-new keypair and preshared key for the peer,
replacing the old ones. **The peer's existing client config, QR code, and any outstanding share
link immediately stop working** — the client must re-import the new config. Use this if a
device's config was compromised or lost.

## Onboarding: QR, Download, Share Link

After creating a peer (or from its row menu), three equivalent ways to hand the config to the end
user. All three require the **operator** role (or an API key with `peers:write`) — a viewer or a
read-only API key gets `403`, because each one exposes the peer's private key and preshared key.

- **QR code** — `GET /api/peers/{id}/qr` returns a PNG the client scans in the WireGuard app.
- **Download** — `GET /api/peers/{id}/config` returns the `.conf` file as an attachment
  (`<name>.conf`); returns `404` if the peer has no stored private key (e.g. after import from a
  legacy config that didn't include one).
- **Share link** — `POST /api/peers/{id}/share {expires_in_hours?: 24, max_uses?: 1}` creates a
  one-time (by default) link at `/share/<token>`. Anyone with the link can view the peer's QR
  code, download the config, and copy the config text — no TunnBox login required. The link
  expires after `expires_in_hours` or after `max_uses` redemptions, whichever comes first
  (`GET /api/share/{token}` returns `410` once exhausted or expired). Useful for handing a config
  to someone without giving them TunnBox credentials.

All three accept an `?allowed_ips=<override>` query parameter to preview the config under a
different split-tunnel setting without changing the stored value.

## Bulk Actions

Select multiple peers in the table and use the bulk action bar, or call the API directly:

```bash
curl -X POST https://vpn.example.com/api/peers/bulk \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"ids": [12, 13, 14], "action": "enable"}'
# {"affected": 3}
```

`action` is `enable`, `disable`, or `delete`.

## Global Peer Search

The **Peers** page searches across every interface at once:

```bash
curl "https://vpn.example.com/api/peers?q=laptop&status=online&page=1&page_size=25" \
  -H "Authorization: Bearer <token>"
```

Filter by `q` (name match), `interface`, and `status` (`online`, `offline`, `disabled`,
`expired`); paginated. Use `GET /api/interfaces/{name}/peers` instead when you only need one
interface's peers, with `sort`/`order` (`name`, `handshake`, `rx`, `tx`, `created`).

## Monitoring

Each peer reports `status` (`online`, `offline`, `disabled`, `expired`), `endpoint`,
`latest_handshake_at`, and cumulative `rx_total`/`tx_total` that survive interface restarts (the
sampler tracks counter resets and only ever adds positive deltas). Per-peer history is available
via `GET /api/peers/{id}/stats?range=1h|6h|24h|7d|30d`.

## Removing a Peer

`DELETE /api/peers/{id}` removes the peer, its stats history, and any share links permanently.
The config already handed to the client stops working the next time the interface config is
applied. This cannot be undone.
