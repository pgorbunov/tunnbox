# Backup & Restore

TunnBox stores data in two locations that should be backed up regularly.

## What to Back Up

| Path (on host) | Contents |
|----------------|----------|
| `./data/app/tunnbox.db` | SQLite database — users, peer metadata, audit logs, settings, encrypted private keys |
| `./data/wireguard/` | WireGuard `.conf` files — interface configs and peer public keys |

Both directories are Docker volume mounts defined in `docker-compose.yml`.

## Manual Backup

### Quick backup (recommended)

Stop the container to ensure a consistent snapshot, then copy the data directory:

```bash
docker compose down
tar czf tunnbox-backup-$(date +%Y%m%d).tar.gz ./data
docker compose up -d
```

### Live backup (without downtime)

SQLite supports safe reads while the application is running. Copy the database using `sqlite3`:

```bash
docker exec tunnbox sqlite3 /app/data/tunnbox.db ".backup '/app/data/tunnbox-backup.db'"
cp ./data/app/tunnbox-backup.db ./tunnbox-db-backup.db
rm ./data/app/tunnbox-backup.db

# Also copy WireGuard configs
cp -r ./data/wireguard ./wireguard-backup
```

### Automated backup with cron

Add a cron job for daily backups:

```bash
crontab -e
```

```
0 3 * * * cd /path/to/tunnbox && docker compose exec -T tunnbox sqlite3 /app/data/tunnbox.db ".backup '/app/data/tunnbox-backup.db'" && tar czf /backups/tunnbox-$(date +\%Y\%m\%d).tar.gz ./data && rm ./data/app/tunnbox-backup.db
```

## Data Export (JSON)

TunnBox has a built-in data export feature accessible to admin users:

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/privacy/export \
  -o tunnbox_export.json
```

This exports users (without password hashes), peer metadata (without private keys), audit logs, and settings as a JSON file. It is useful for auditing and record-keeping but is **not sufficient for a full restore** because it excludes secrets.

## Restore

### Full restore from tar backup

1. Stop the running instance:
   ```bash
   docker compose down
   ```

2. Remove existing data (or move it aside):
   ```bash
   mv ./data ./data-old
   ```

3. Extract the backup:
   ```bash
   tar xzf tunnbox-backup-20250101.tar.gz
   ```

4. Start the container:
   ```bash
   docker compose up -d
   ```

5. Verify by logging in and checking your interfaces and peers.

### Restore to a new server (migration)

1. Install Docker and Docker Compose on the new server.

2. Create the project directory and copy your `docker-compose.yml`, `.env`, and `Caddyfile` (if using a reverse proxy).

3. Copy the backup archive to the new server and extract it:
   ```bash
   scp tunnbox-backup-20250101.tar.gz newserver:/path/to/tunnbox/
   ssh newserver
   cd /path/to/tunnbox
   tar xzf tunnbox-backup-20250101.tar.gz
   ```

4. Update `.env` on the new server:
   - Set `WG_DEFAULT_ENDPOINT` to the new server's public IP.
   - Keep the same `SECRET_KEY` so existing tokens remain valid.

5. Start the container:
   ```bash
   docker compose up -d
   ```

6. Update DNS records if using a domain name for the endpoint.

7. Clients may need to update their configs if the server IP changed. If you used a domain name for `WG_DEFAULT_ENDPOINT`, and DNS is updated, clients will reconnect automatically.

## What the Backup Contains

| Data | In DB? | In .conf files? | In JSON export? |
|------|--------|-----------------|-----------------|
| User accounts | Yes | No | Yes (no passwords) |
| Peer names | Yes | No | Yes |
| Peer private keys (encrypted) | Yes | No | No |
| Peer public keys | Yes | Yes | Yes |
| Interface configs | No | Yes | No |
| Server private keys | No | Yes | No |
| Audit logs | Yes | No | Yes |
| Settings | Yes | No | Yes |

::: warning
The JSON export does not include private keys or password hashes. It cannot be used to fully restore a TunnBox instance. Always use file-level backups for disaster recovery.
:::
