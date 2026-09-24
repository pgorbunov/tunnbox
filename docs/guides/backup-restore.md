# Backup & Restore

## What to Back Up

| Path (on host) | Contents |
|-----------------|----------|
| `./data/app/tunnbox.db` | SQLite database: users, sessions, API keys, interfaces, peers (keys encrypted), audit log, stats, settings |
| `./data/app/.secret_key` | The generated root secret, **only present if you didn't set `SECRET_KEY` yourself** |
| `./data/wireguard/` | Rendered WireGuard `.conf` files (regenerable from the database, but convenient to keep) |

## Backup from the App (Settings > Data)

An admin can download a full backup from the UI (**Settings > Data > Download backup**), or
directly:

```bash
curl -H "Authorization: Bearer <token>" \
  https://vpn.example.com/api/system/backup \
  -o tunnbox-backup-$(date +%Y%m%d).tar.gz
```

### What the archive contains

`GET /api/system/backup` returns a `.tar.gz` with:

- `tunnbox.db` — a consistency-safe copy of the live database (taken with SQLite's `.backup`, so
  it's safe to run without stopping the container)
- `wireguard/<name>.conf` — every interface's currently rendered config file

**It does not include `SECRET_KEY` / `.secret_key`.** Since private keys and MFA secrets in
`tunnbox.db` are encrypted with a key derived from `SECRET_KEY`, this omission matters — see the
warning below.

This action is audit-logged as `system.backup`.

### JSON export (not a backup)

`GET /api/system/export` (admin only, audited as `system.export`) returns users (no password
hashes), interfaces (no private keys), peers (no keys), settings, and audit log as JSON. It's
useful for record-keeping or migrating data into another system, but **cannot be used to restore
TunnBox** — it deliberately excludes every secret.

## Manual (File-Level) Backup

Stop the container for a guaranteed-consistent snapshot of the whole data directory (including
`.secret_key`, which the API backup omits):

```bash
docker compose down
tar czf tunnbox-backup-$(date +%Y%m%d).tar.gz ./data
docker compose up -d
```

For a live backup without downtime, use the same approach as the API endpoint plus a manual copy
of the secret key file:

```bash
docker exec tunnbox sqlite3 /app/data/tunnbox.db ".backup '/app/data/tunnbox-backup.db'"
docker cp tunnbox:/app/data/tunnbox-backup.db ./tunnbox-db-backup.db
docker exec tunnbox rm /app/data/tunnbox-backup.db
cp -r ./data/wireguard ./wireguard-backup
cp ./data/app/.secret_key ./secret_key-backup   # if it exists
```

## The SECRET_KEY Caveat

**A backup is useless for a full restore unless you also have the exact `SECRET_KEY` (or
`.secret_key` file) that was in use when it was taken.** Peer and interface private keys, PSKs,
and MFA secrets are encrypted with a key derived from `SECRET_KEY`. Restore the database with a
*different* key and:

- Every existing session becomes invalid (users must log in again — expected either way).
- Every stored private key, preshared key, and MFA secret **fails to decrypt**. Peers lose their
  private keys (client configs can no longer be regenerated for them, only new peers can be
  created), and MFA-enabled users are locked out of their second factor.

There is no way to recover encrypted values without the original key. Always back up
`SECRET_KEY`'s value (if you set one explicitly) or the `./data/app/.secret_key` file (if you let
TunnBox generate one) **together with** `tunnbox.db`, and keep them in the same place.

## Restore

### From a tar.gz backup

```bash
docker compose down
mv ./data ./data-old                 # keep the old data instead of deleting it
tar xzf tunnbox-backup-20260101.tar.gz
docker compose up -d
```

### From the API backup (`system/backup` archive)

The API archive doesn't include `.secret_key`, so restore it alongside your existing
`SECRET_KEY`/`.secret_key` — don't let a fresh container generate a new one:

```bash
docker compose down
tar xzf tunnbox-backup-20260101.tar.gz -C ./data/app --strip-components=0 tunnbox.db
mkdir -p ./data/wireguard
tar xzf tunnbox-backup-20260101.tar.gz -C ./data/wireguard --strip-components=1 wireguard
# Ensure ./data/app/.secret_key (or SECRET_KEY in .env) matches what the backup was taken with.
docker compose up -d
```

### Migrating to a new server

1. Install Docker and Docker Compose on the new host.
2. Copy `docker-compose.yml`, `.env` (with the same `SECRET_KEY`, if you set one), and any
   reverse-proxy config.
3. Copy the backup archive and, if you relied on the auto-generated key,
   `./data/app/.secret_key` as well.
4. Extract into `./data/`, update `WG_DEFAULT_ENDPOINT` (or the `public_endpoint` setting) to the
   new server's address, and `docker compose up -d`.
5. Update DNS if you use a hostname for the endpoint. Clients using a hostname reconnect
   automatically once DNS propagates; clients pinned to a raw IP need new configs.

## Reference

| Data | In DB? | In `.conf` files? | In API backup? | In JSON export? |
|------|--------|--------------------|-----------------|-------------------|
| User accounts, roles | Yes | No | Yes | Yes (no password hashes) |
| Sessions, API keys | Yes | No | Yes | No |
| Peer/interface private keys (encrypted) | Yes | No (server `.conf` has the interface's) | Yes (encrypted, needs `SECRET_KEY`) | No |
| Public keys, peer names | Yes | Yes | Yes | Yes |
| Audit log | Yes | No | Yes | Yes |
| Settings | Yes | No | Yes | Yes |
| `SECRET_KEY` / `.secret_key` | N/A | N/A | **No** | No |

::: warning
Neither the API backup nor the JSON export includes `SECRET_KEY`. Keep it separately, and treat
losing it as equivalent to losing every stored secret.
:::
