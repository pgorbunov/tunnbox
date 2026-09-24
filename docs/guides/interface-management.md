# Interface Management

Interfaces are WireGuard virtual network devices. Each has its own address(es), listen port, and
set of peers. TunnBox's database is the source of truth for interfaces — the `.conf` file under
`WG_CONFIG_PATH` is always *rendered* from the database, never edited by hand or read back except
at startup (see [Architecture](./architecture.md)).

## Creating an Interface

`POST /api/interfaces { name, address, listen_port, dns?, mtu?, post_up?, post_down?, public_endpoint?, enabled?: true }`

- **Name** — up to 15 characters, `^[a-zA-Z0-9_=+.-]{1,15}$`; `all`, `default`, and `lo` are
  reserved.
- **Address** — CIDR notation, e.g. `10.8.0.1/24`; comma-separate for dual-stack,
  e.g. `10.8.0.1/24, fd00:8::1/64`.
- **Listen Port** — UDP port, unique across interfaces, must be mapped in `docker-compose.yml`.
- **DNS**, **MTU**, **public endpoint override** — optional; each falls back to the global
  setting when unset.
- **PostUp / PostDown** — only accepted when `WG_ALLOW_CUSTOM_SCRIPTS=true`; see below.
- **Enabled** — defaults to `true`. On the real backend, TunnBox brings an enabled interface up
  itself (there's no separate "bring it up after creating" step, and the app also reconciles
  enabled interfaces at startup — see [Architecture](./architecture.md)).

## Editing an Interface

`PATCH /api/interfaces/{name}` accepts any of the create fields. What happens next depends on
which fields changed:

- Changing **`address`, `listen_port`, `mtu`, `post_up`, or `post_down`** while the interface is
  active triggers a **restart** (`wg-quick down` + `wg-quick up`) after re-rendering the config —
  these can't be applied to a running interface without one.
- Changing **`enabled`** brings the interface up or down accordingly.
- Any other field change (DNS, public endpoint override) just re-renders the config; if the
  interface is active, it's applied live with `wg syncconf` rather than a restart.

Adding, removing, enabling or disabling a **peer** on an already-active interface is always
applied live via `wg syncconf` — no restart.

## Bringing Interfaces Up and Down

```bash
curl -X POST https://vpn.example.com/api/interfaces/wg0/up   -H "Authorization: Bearer <token>"
curl -X POST https://vpn.example.com/api/interfaces/wg0/down -H "Authorization: Bearer <token>"
```

`up` runs `wg-quick up`; `down` runs `wg-quick down`. Both are idempotent — bringing up an
already-active interface or bringing down an already-inactive one is a no-op rather than an
error. In mock mode, these toggle an in-memory active flag with simulated stats instead of
touching the real network stack.

## PostUp and PostDown Scripts

PostUp/PostDown commands run when an interface comes up or goes down — typically NAT masquerade
rules for full-tunnel clients. Setting them requires **both** an admin role **and**
`WG_ALLOW_CUSTOM_SCRIPTS=true`:

- **Role** — only an **admin** can set `post_up`/`post_down` on an interface, whether creating or
  editing it. An operator's request to set either field is rejected outright, even when
  `WG_ALLOW_CUSTOM_SCRIPTS=true` — there's no way for a non-admin to add PostUp/PostDown, since
  they run as root.
- **`WG_ALLOW_CUSTOM_SCRIPTS=false`** (default) — the fields are rejected outright for everyone;
  no one can set `post_up`/`post_down` while this is off.
- **`WG_ALLOW_CUSTOM_SCRIPTS=true`** — an admin can set arbitrary commands, which run as **root**
  inside the container. Only enable this if you understand the risk.

If `WG_ALLOW_CUSTOM_SCRIPTS` is turned back off after scripts were already saved on an interface
(rather than removed), they are **not deleted** from the database, but are **silently omitted**
from the rendered `.conf` the next time it's regenerated — the interface comes up without them,
and a warning is logged once per interface. Turning the flag back on makes them take effect again
without needing to re-enter them.

Typical NAT setup once enabled:

```
PostUp   = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
```

`%i` is substituted by WireGuard with the interface name. Check the container's outbound
interface name first — it may not be `eth0`:

```bash
docker exec tunnbox ip route | grep default
```

Setting either `post_up` or `post_down` on an interface always triggers a restart when the
interface is active (see above), regardless of whether custom scripts are enabled.

## Server Config Download

`GET /api/interfaces/{name}/config` returns the rendered server `.conf` as plain text, including
the interface's **private key** — restricted to **admin** only. Useful for manual inspection or
migrating a single interface elsewhere.

## Running Multiple Interfaces

Create additional interfaces with unique names and non-overlapping subnets, and map each
interface's UDP port in `docker-compose.yml`:

```yaml
ports:
  - "8000:8000"
  - "51820:51820/udp"   # wg0
  - "51821:51821/udp"   # wg1
```

## Monitoring

Interfaces report `is_active`, `peer_count`, `online_peer_count`, and cumulative `rx_total`/
`tx_total`. Historical series (1h–30d, bucketed) are at
`GET /api/interfaces/{name}/stats?range=1h|6h|24h|7d|30d`.

## Deleting an Interface

`DELETE /api/interfaces/{name}` brings it down (if active), deletes its rendered `.conf`, and
deletes all of its peers and their history from the database. This cannot be undone; the UI
requires typing the interface's name to confirm.
