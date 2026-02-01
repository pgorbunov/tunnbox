# Interface Management

Interfaces are the core virtual network devices that WireGuard uses. TunnBox allows you to manage multiple interfaces easily.

## Creating an Interface

1.  Navigate to the **Dashboard** or **Interfaces** page.
2.  Click the **"New Interface"** button.
3.  Fill in the details:
    *   **Name**: A unique name (e.g., `wg0`).
    *   **Private Key**: Leave empty to auto-generate (Recommended).
    *   **Listen Port**: The UDP port (Default: `51820`).
    *   **Address**: The IP address for the server in the VPN subnet (e.g., `10.0.0.1/24`).
4.  Click **Save**.

## Managing Interfaces

From the interface list, you can:
*   **Toggle Status**: Click the toggle switch to bring the interface UP or DOWN.
*   **Edit**: Change IP addresses or ports.
*   **Delete**: Remove the interface and all associated peers.

> **Note**: TunnBox requires the container to have `NET_ADMIN` capabilities to actually modify network interfaces on the host.
