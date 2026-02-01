# Peer Management

Peers are the clients (phones, laptops, other servers) that connect to your WireGuard interface.

## Adding a Peer

1.  Select an Interface (e.g., `wg0`).
2.  Click **"Add Peer"**.
3.  Fill in the details:
    *   **Name**: Friendly name for the device (e.g., "John's iPhone").
    *   **Public Key**: Leave empty to auto-generate.
    *   **Allowed IPs**: The IP address this peer will use (e.g., `10.0.0.2/32`).
4.  Click **Save**.

## Connection Methods

### 📱 Mobile (QR Code)
1.  Click the **QR Code icon** next to a peer.
2.  Open the WireGuard app on your phone.
3.  Select **"Add a tunnel"** -> **"Scan from QR code"**.

### 💻 Desktop (Config File)
1.  Click the **Download icon** next to a peer.
2.  Save the `.conf` file.
3.  Import it into your WireGuard desktop client.

## Monitoring Peers
The dashboard shows:
*   **Status**: Green dot indicates a recent handshake.
*   **Transfer**: Total uploaded/downloaded data.
*   **Last Handshake**: Time since the last successful connection.
