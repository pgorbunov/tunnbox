# Updating TunnBox

## Upgrading from v1

TunnBox v2 rewrote the backend and frontend but reuses the same data directories. Point v2 at
your existing `./data/wireguard` and `./data/app` and it upgrades in place:

1. **Back up first** — copy `./data/` somewhere safe before pulling the new image. See
   [Backup & Restore](./backup-restore.md).
2. Update `docker-compose.yml` and `.env` to v2's shape — compare against the current
   [Configuration reference](../getting-started/configuration.md); some v1 variables (CSRF
   toggles, Redis rate-limit URL) no longer exist, and new ones (`TRUSTED_PROXIES`,
   `WG_ALLOW_CUSTOM_SCRIPTS`, `SESSION_ABSOLUTE_DAYS`, `LOCKOUT_THRESHOLD`/`LOCKOUT_MINUTES`) were
   added.
3. `docker compose pull && docker compose up -d`.

On first start against existing data:

- **Existing `.conf` files are imported automatically.** Any interface under `WG_CONFIG_PATH` not
  yet known to the database is parsed and created, along with its peers. This is safe to run
  against a v1 install's untouched `/etc/wireguard` — TunnBox v2's database was empty until now,
  so every file it finds gets imported once.
- **Peer names are recovered from the v1 database** if present. v1 stored names and (for peers
  created through v1) encrypted private keys in a `peer_metadata` table, matched to imported peers
  by interface name + public key. If a matching v1 database is detected (via legacy tables), this
  metadata is used to fill in names and private keys during the same startup import, then the
  legacy table is dropped. Peers with no matching metadata are imported with a placeholder name
  and no stored private key (their client config can't be re-downloaded, but the peer still works
  — see [Peer Management](./peer-management.md)).
- **All existing sessions are invalidated.** v1's session/token format is different from v2's; every
  user (including admins) has to log in again after the upgrade. This is expected, not a bug.
- User accounts carry over: v1's `is_admin` flag maps to role `admin`; everyone else becomes
  `operator` or should be assigned a role afterward under **Settings > Users**.

After upgrading, log back in, confirm your interfaces and peers look right, and consider enabling
MFA on admin accounts (v1 had no MFA support) — see [First Setup](../getting-started/first-setup.md#enabling-mfa).

## Routine Updates (v2 to v2)

### Pre-built image

```bash
cd /path/to/tunnbox
docker compose pull
docker compose up -d
```

Data in `./data/` persists across the update since it's in mounted volumes, not the container.

### Safer update with a backup

```bash
cd /path/to/tunnbox
docker compose down
tar czf tunnbox-backup-$(date +%Y%m%d).tar.gz ./data
docker compose pull
docker compose up -d
```

Roll back if something goes wrong:

```bash
docker compose down
mv ./data ./data-broken
tar xzf tunnbox-backup-*.tar.gz
docker compose up -d
```

### Built from source

```bash
cd /path/to/tunnbox
git pull
docker compose up -d --build
```

## Checking the Current Version

```bash
curl -H "Authorization: Bearer <token>" https://vpn.example.com/api/system/info
```

Returns `version` (application version) alongside `backend_mode`, `wireguard_version`, and other
system details. The unauthenticated `GET /api/auth/status` also returns `version`.

## Pinning a Version

```yaml
services:
  tunnbox:
    image: pgorbunov/tunnbox:2.0.0
```

## Rollback

1. `docker compose down`
2. Set the image tag back to the previous version in `docker-compose.yml`
3. `docker compose up -d`

If the database schema changed between versions, restore from a pre-update backup instead of just
rolling back the image — migrations only run forward. See
[Backup & Restore](./backup-restore.md).
