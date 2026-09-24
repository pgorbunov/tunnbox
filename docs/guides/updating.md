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

- **Existing `.conf` files are imported automatically, and the originals are kept.** Any
  interface under `WG_CONFIG_PATH` not yet known to the database is parsed and imported (interface
  + peers). Before TunnBox ever re-renders a file it imports, it copies the original to
  `<name>.conf.v1.bak` (mode `0600`) in the same directory — so you always have the exact file
  WireGuard was using before the upgrade, even after the app starts rewriting `<name>.conf` itself.
  Each file's import runs in its own transaction and rolls back cleanly on error, leaving that file
  untouched if anything goes wrong.
- **Files using directives TunnBox can't reproduce are skipped, not partially imported.** If an
  interface's `[Interface]` section uses `Table`, `FwMark`, `PreUp`, `PreDown`, or `SaveConfig`, or
  any peer has an `Endpoint` line, that whole file is left alone (not imported, not renamed to
  `.v1.bak`) and a warning is logged with the reason. TunnBox's renderer doesn't support those
  directives, so importing and later re-rendering the file would silently drop them. To migrate
  such a file by hand:
  1. Remove the unsupported line(s) if you don't need them (most setups don't need `PreUp`/
     `PreDown`/`SaveConfig`/`Table`/`FwMark` — `PostUp`/`PostDown` are fully supported), or keep
     the file entirely outside TunnBox (rename it so it doesn't end in `.conf` under
     `WG_CONFIG_PATH`, or move it elsewhere) and manage that interface separately.
  2. Remove a peer's `Endpoint` line — it's a client-config concept, not something a server config
     normally needs; TunnBox generates it in *rendered client* configs from the interface's public
     endpoint, not from a stored server-side peer field.
  3. Once the file has none of the unsupported directives, restart the container (or otherwise
     trigger a rescan) and it will be imported on the next startup.
- **Peer names are recovered from the v1 database** if present. v1 stored names and (for peers
  created through v1) encrypted private keys in a `peer_metadata` table, matched to imported peers
  by interface name + public key. If a matching v1 database is detected (via legacy tables), this
  metadata is used to fill in names and private keys during the same startup import; the legacy
  table is dropped only once every file has imported cleanly. Peers with no matching metadata are
  imported with a placeholder name and no stored private key (their client config can't be
  re-downloaded, but the peer still works — see [Peer Management](./peer-management.md)).
- **User accounts and roles carry over.** v1's `is_admin` flag maps to role `admin`; every other
  v1 user becomes `viewer` (the most restrictive role) — promote anyone who needs to manage
  interfaces/peers to `operator` afterward under **Settings > Users**.
- **v1 audit history is migrated** into the new `audit_logs` table (action names are mapped to
  v2's naming, e.g. `login` → `auth.login`), so your existing audit trail isn't lost.
- **All existing sessions are invalidated.** v1's session/token format is different from v2's; every
  user (including admins) has to log in again after the upgrade. This is expected, not a bug.

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
