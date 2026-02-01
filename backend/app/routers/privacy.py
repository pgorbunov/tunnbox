from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.dependencies import get_current_user
from app.models.user import UserResponse
from app.database import get_db, add_audit_log
import aiosqlite
import json
from datetime import datetime
from io import BytesIO

router = APIRouter()


@router.get("/export")
async def export_all_data(current_user: UserResponse = Depends(get_current_user)):
    """Export all non-sensitive data as JSON (admin-only)"""
    # Only admins can export data
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    async for db in get_db():
        # Collect data from all tables
        export_data = {
            "metadata": {
                "export_date": datetime.utcnow().isoformat(),
                "version": "1.0.0",
                "exported_by": current_user.username
            },
            "users": [],
            "peer_metadata": [],
            "audit_logs": [],
            "settings": {}
        }

        # Export users (exclude passwords)
        async with db.execute("SELECT id, username, is_admin, created_at FROM users") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                export_data["users"].append({
                    "id": row[0],
                    "username": row[1],
                    "is_admin": bool(row[2]),
                    "created_at": row[3]
                })

        # Export peer metadata (exclude private keys)
        async with db.execute(
            "SELECT id, interface_name, public_key, name, created_at FROM peer_metadata"
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                export_data["peer_metadata"].append({
                    "id": row[0],
                    "interface_name": row[1],
                    "public_key": row[2],
                    "name": row[3],
                    "created_at": row[4]
                })

        # Export audit logs
        async with db.execute(
            "SELECT id, user_id, action, details, ip_address, created_at FROM audit_logs"
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                export_data["audit_logs"].append({
                    "id": row[0],
                    "user_id": row[1],
                    "action": row[2],
                    "details": row[3],
                    "ip_address": row[4],
                    "created_at": row[5]
                })

        # Export settings (exclude sensitive values like email passwords)
        async with db.execute("SELECT key, value FROM settings") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                key, value = row[0], row[1]
                # Skip sensitive settings
                if key not in ["email_password", "smtp_password"]:
                    export_data["settings"][key] = value

        # Add audit log entry
        await add_audit_log(
            current_user.id,
            "data_export",
            f"Exported all data (users: {len(export_data['users'])}, peers: {len(export_data['peer_metadata'])}, logs: {len(export_data['audit_logs'])})"
        )

    # Convert to JSON
    json_content = json.dumps(export_data, indent=2)
    json_bytes = BytesIO(json_content.encode('utf-8'))

    # Generate filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"tunnbox_export_{timestamp}.json"

    # Return as downloadable file
    return StreamingResponse(
        json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
