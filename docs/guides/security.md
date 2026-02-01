# Security Guide

## Authentication
TunnBox uses JSON Web Tokens (JWT) for stateless authentication.
*   **Access Tokens**: Short-lived (default 15 mins).
*   **Refresh Tokens**: Long-lived (default 7 days), stored in HTTP-only cookies.

## Container Security
The Docker container is designed with least privilege in mind.

### Capabilities
We drop ALL capabilities and add only what is strictly necessary:
*   `NET_ADMIN`: To manage network interfaces (WireGuard).
*   `SYS_MODULE`: To load the WireGuard kernel module (if not loaded).
*   `MKNOD`: Create devices.

### Non-Root User
The application inside the container runs as a non-root user (where possible) or drops privileges for the web server process.

## HTTP Security Headers
The following headers are enforced by the backend:
*   `Strict-Transport-Security` (HSTS)
*   `Content-Security-Policy` (CSP)
*   `X-Frame-Options: DENY`
*   `X-XSS-Protection`

## Audit Logging
Important actions (login, interface changes, key viewing) are logged to the database for security review.
Admin users can export these logs via the Privacy settings.
