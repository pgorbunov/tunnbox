# API Keys & Automation

TunnBox's UI is a client of its own REST API — anything the UI does, a script can do too, using
an API key instead of a browser session.

## Creating a Key

**Settings > API keys > New key**, or:

```bash
curl -X POST https://vpn.example.com/api/api-keys \
  -H "Authorization: Bearer <session-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "backup-cron", "scopes": ["read"], "expires_at": null}'
```

```json
{
  "id": 7,
  "name": "backup-cron",
  "prefix": "tb_a1b2c3",
  "scopes": ["read"],
  "expires_at": null,
  "last_used_at": null,
  "created_at": "2026-09-24T12:00:00Z",
  "revoked_at": null,
  "key": "tb_a1b2c3d4e5f6...redacted...full-key-shown-once"
}
```

The `key` field is only ever returned in this response. Store it now — TunnBox keeps only its
SHA-256 hash and an 8-character prefix (`tb_a1b2c3`) for display afterward. Creating a key
requires an existing session; **you cannot create an API key using another API key**.

## Scopes

| Scope | Grants |
|-------|--------|
| `read` | Every `GET` endpoint available to the key owner's role |
| `peers:write` | Create, update, delete, enable/disable, rotate keys, and share peers |
| `interfaces:write` | Create, update, delete, and bring interfaces up/down |
| `admin` | Everything an admin session can do through the API |

A key is capped at its owner's role — an `operator`'s key can hold `read`, `peers:write`, and
`interfaces:write`, but never `admin`. Regardless of scope, API keys can never call
`/api/auth/*`, `/api/mfa/*`, or `/api/users/*` (unless the key itself carries `admin`), and can
never create other API keys.

## Using a Key

```bash
curl https://vpn.example.com/api/interfaces \
  -H "Authorization: Bearer tb_a1b2c3d4e5f6..."
```

or

```bash
curl https://vpn.example.com/api/interfaces \
  -H "X-API-Key: tb_a1b2c3d4e5f6..."
```

Every use updates the key's `last_used_at`, visible in **Settings > API keys**.

## Revoking a Key

```bash
curl -X DELETE https://vpn.example.com/api/api-keys/7 \
  -H "Authorization: Bearer <session-access-token>"
```

Revocation is immediate and logged (`apikey.revoked`). Set `expires_at` at creation time instead
of relying on manual revocation for keys used by unattended jobs.

## Example: Create a Peer and Download Its Config

```bash
KEY="tb_a1b2c3d4e5f6..."
BASE="https://vpn.example.com/api"

# Create the peer (needs peers:write)
PEER=$(curl -s -X POST "$BASE/interfaces/wg0/peers" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "ci-runner-01", "allowed_ips": "auto"}')

PEER_ID=$(echo "$PEER" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Download its config (needs read)
curl -s "$BASE/peers/$PEER_ID/config" \
  -H "Authorization: Bearer $KEY" \
  -o ci-runner-01.conf
```

## Example: Scripted Backups

Give a dedicated key `admin` scope (backup/export require admin) and pull a nightly archive from
cron:

```bash
0 3 * * * curl -s -H "Authorization: Bearer $TUNNBOX_BACKUP_KEY" \
  https://vpn.example.com/api/system/backup \
  -o /backups/tunnbox-$(date +\%Y\%m\%d).tar.gz
```

Remember: the backup archive doesn't include `SECRET_KEY` — see
[Backup & Restore](./backup-restore.md#the-secret_key-caveat).

## Rate Limits

API keys are not exempt from the general request handling of their endpoints, but they are not
subject to the login rate limiter or account lockout (those apply to `/api/auth/login*` only).
The public `GET /api/share/{token}` endpoint has its own 20-requests-per-minute-per-IP limit
regardless of authentication.

## Full Endpoint Reference

See [API Reference](../api/endpoints.md) for every endpoint, required role/scope, and response
shapes.
