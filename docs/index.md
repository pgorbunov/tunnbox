---
layout: home

hero:
  name: "TunnBox"
  text: "WireGuard VPN, simplified."
  tagline: A self-hosted management UI for creating interfaces, managing peers, and sharing configs — all from your browser.
  image:
    src: /logo.svg
    alt: TunnBox Logo
  actions:
    - theme: brand
      text: Get Started
      link: /getting-started/installation
    - theme: alt
      text: View on GitHub
      link: https://github.com/pgorbunov/tunnbox

features:
  - icon: 🔧
    title: Manage
    details: Multiple WireGuard interfaces with IPv4/IPv6 subnets, live up/down, automatic peer IP assignment, split tunnelling presets, expiry with auto-disable, and bulk actions.
  - icon: 👥
    title: Onboard
    details: One-click peer onboarding — QR code, .conf download, or a one-time share link — with generated keypairs and preshared keys.
  - icon: 📊
    title: Observe
    details: Live per-peer status and transfer counters, historical bandwidth charts, a dashboard with top talkers and expiring peers, and a searchable audit log.
  - icon: 🔒
    title: Secure by Default
    details: Short-lived sessions with rotating refresh cookies, TOTP MFA with recovery codes, roles and scoped API keys, lockout, strict CSP, and encryption at rest.
---
