# Updating TunnBox

## Pre-built Docker Image

### Standard update

```bash
cd /path/to/tunnbox

# Pull the latest image
docker compose pull

# Restart with the new image
docker compose up -d
```

Docker will automatically stop the old container and start the new one. Data in `./data/` is preserved because it's stored in mounted volumes, not inside the container.

### Safe update with backup

```bash
cd /path/to/tunnbox

# Back up data first
docker compose down
tar czf tunnbox-backup-$(date +%Y%m%d).tar.gz ./data
docker compose pull
docker compose up -d
```

If something goes wrong, restore from the backup:
```bash
docker compose down
rm -rf ./data
tar xzf tunnbox-backup-*.tar.gz
docker compose up -d
```

## Built from Source

If you built TunnBox from the repository:

```bash
cd /path/to/tunnbox

# Pull latest code
git pull

# Rebuild and restart
docker compose up -d --build
```

## Checking the Current Version

Open the TunnBox UI and check the footer, or query the API:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/system/info
```

This returns `frontend_version`, `backend_version`, and other system details.

## Pinning a Specific Version

To avoid unexpected changes, pin a specific image tag instead of `latest`:

```yaml
services:
  tunnbox:
    image: pgorbunov/tunnbox:1.0.0
```

## Rollback

If an update causes issues:

1. Stop the container: `docker compose down`
2. Edit `docker-compose.yml` to use the previous image tag.
3. Start: `docker compose up -d`

If the database schema changed in the new version, restoring from a pre-update backup may be necessary.
