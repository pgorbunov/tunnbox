# First Setup

TunnBox's setup wizard runs the first time you open the app, and only while the database has no
users. It has three steps: **create the admin account**, **confirm the endpoint**, and **create
your first interface**.

## Step 1: Create the Admin Account

Open `http://your-server:8000` in a browser. Because no users exist yet, you land on `/setup`.

1. Choose a **username** and **password**.
   - Password must be 10–128 characters, must not equal the username, and must not be one of a
     small list of common weak passwords.
2. Submit the form.

This calls `POST /api/auth/setup`, which only succeeds when no users exist (it returns `409` if
an admin has already been created). It creates the first user with role `admin` and logs you in
immediately — no separate login step.

::: tip
Check setup status without logging in:
```bash
curl http://your-server:8000/api/auth/status
# {"setup_required": true, "version": "2.0.0"}
```
:::

## Step 2: Confirm the Server Endpoint

The wizard prefills the public endpoint from `WG_DEFAULT_ENDPOINT` (or the auto-detected public
IP set by the Docker entrypoint). Confirm or correct it — this is the address WireGuard clients
will connect to, so it must be reachable from the internet, not `127.0.0.1` or a private IP
unless clients are on the same LAN.

This value is the `public_endpoint` runtime setting (`GET`/`PATCH /api/settings`), editable later
under **Settings > General**.

## Step 3: Create Your First Interface

The wizard's last step opens the interface creation form (also reachable later at
`/interfaces?new=1`).

1. **Name** — e.g. `wg0`. Up to 15 characters, `^[a-zA-Z0-9_=+.-]{1,15}$`, and not one of the
   reserved names `all`, `default`, `lo`.
2. **Address** — the server's IP inside the VPN subnet, in CIDR notation, e.g. `10.8.0.1/24`
   (IPv4 and/or IPv6, comma-separated for dual-stack).
3. **Listen Port** — the UDP port WireGuard listens on, e.g. `51820`. Must be unique across
   interfaces and match a port mapped in `docker-compose.yml`.
4. Optional: DNS, MTU, endpoint override, PostUp/PostDown (only editable when
   `WG_ALLOW_CUSTOM_SCRIPTS=true`).

Submitting calls `POST /api/interfaces`. The interface is created enabled by default; on the real
backend the app brings it up itself — you don't need to run `wg-quick` manually. See
[Interface Management](../guides/interface-management.md).

From here, add your first peer from the interface page — see
[Peer Management](../guides/peer-management.md) for onboarding via QR code, download, or share
link.

## Enabling MFA

Once you're logged in, enable TOTP multi-factor authentication for the admin account:

1. Go to **Settings > Security**.
2. Click **Enable MFA**. This calls `POST /api/mfa/setup`, which returns a secret, an
   `otpauth://` URI, and a QR code (`qr_svg`) — scan it with an authenticator app (Google
   Authenticator, Authy, 1Password, etc.). The secret is stored encrypted but MFA is not yet
   required at this point.
3. Enter the 6-digit code from your app to confirm (`POST /api/mfa/enable`). TunnBox returns 10
   **recovery codes** — store them somewhere safe. Each is single-use and lets you sign in if you
   lose your authenticator device.
4. From then on, login is two steps: password, then a 6-digit code (or a recovery code in
   `xxxx-xxxx` format).

See [Security](../guides/security.md#multi-factor-authentication) for the full MFA and recovery
model, and what to do if you lose your device.

## Next Steps

- [Interface Management](../guides/interface-management.md) — multiple interfaces, PostUp/PostDown
- [Peer Management](../guides/peer-management.md) — onboarding, split tunnel, expiry, bulk actions
- [Security](../guides/security.md) — sessions, MFA, roles, API keys, hardening
- [Production Deployment](../deployment/production.md) — HTTPS via a reverse proxy
