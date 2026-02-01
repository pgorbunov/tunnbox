# First Setup

After installing TunnBox, follow this guide to get your VPN up and running.

## Step 1: Create the Admin Account

When you first open TunnBox in your browser (`http://your-server:8000`), you'll see the setup screen.

1. Enter a **username** for the admin account.
2. Enter a **password** (minimum 8 characters).
3. Click **Create Account**.

This endpoint is only available when no users exist in the database. Once an admin account is created, the setup page is disabled permanently.

::: tip
You can verify the setup status programmatically:
```bash
curl http://your-server:8000/api/auth/check-setup
# Returns: {"setup_required": true} or {"setup_required": false}
```
:::

## Step 2: Log In

After creating the admin account, log in with your credentials. You'll be taken to the dashboard.

## Step 3: Configure Server Settings

Before creating interfaces, verify your server settings:

1. Navigate to **Settings** in the sidebar.
2. Confirm the **Public Endpoint** is set to your server's public IP or domain. This is the address clients will connect to.
3. Confirm the **Default DNS** is appropriate (default: `1.1.1.1`).

## Step 4: Create Your First Interface

1. Click **New Interface** on the dashboard.
2. Fill in the fields:
   - **Name**: `wg0` (or any name up to 15 characters)
   - **Listen Port**: `51820` (must match the port exposed in `docker-compose.yml`)
   - **Address**: `10.0.0.1/24` (the server's IP within the VPN subnet)
   - **DNS**: `1.1.1.1` (optional, inherited from server settings)
3. Click **Save**.
4. Click the **toggle switch** to bring the interface UP.

::: warning
The listen port must match the UDP port mapped in your `docker-compose.yml`. If you mapped `51820:51820/udp`, use port `51820`.
:::

## Step 5: Add Your First Peer

1. Select the interface you just created.
2. Click **Add Peer**.
3. Fill in:
   - **Name**: A friendly label (e.g., "My Laptop")
   - **Allowed IPs**: Set to `auto` to automatically assign the next available IP
4. Click **Save**.

## Step 6: Connect the Client

### Mobile (QR Code)
1. Click the **QR Code** icon next to the peer.
2. Open the WireGuard app on your phone.
3. Tap **Add a tunnel** > **Scan from QR code**.

### Desktop (Config File)
1. Click the **Download** icon next to the peer.
2. Save the `.conf` file.
3. Import it into the WireGuard desktop client.

## Step 7: Verify the Connection

After connecting the client:

1. Check the peer status on the TunnBox dashboard — a green indicator shows a recent handshake.
2. On the client, verify connectivity:
   ```bash
   # Ping the VPN server
   ping 10.0.0.1

   # Check your public IP (if routing all traffic through VPN)
   curl ifconfig.me
   ```

## Next Steps

- [Interface Management](/guides/interface-management) — PostUp/PostDown scripts, multiple interfaces
- [Peer Management](/guides/peer-management) — Bulk operations, mobile setup details
- [Security Guide](/guides/security) — Harden your installation
- [Production Deployment](/deployment/production) — Set up HTTPS with a reverse proxy
