from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator
from app.dependencies import get_current_user
from app.database import get_all_settings, set_setting, add_audit_log
from app.config import get_settings
from app.models.user import UserResponse
import re

router = APIRouter(prefix="/api/settings", tags=["settings"])

config = get_settings()


class ServerSettings(BaseModel):
    """Server settings model"""
    public_endpoint: str = Field(default="", description="Public hostname or IP address (no port)")
    wg_default_dns: str = Field(default="1.1.1.1", description="DNS server for client configurations")
    wg_config_path: str = Field(description="WireGuard configuration directory (read-only)")

    @validator('wg_default_dns')
    def validate_dns(cls, v):
        """Validate DNS format (IP address or comma-separated IPs)"""
        if not v:
            return v

        # Split by comma and validate each DNS server
        dns_servers = [dns.strip() for dns in v.split(',')]

        for dns in dns_servers:
            # Basic IP address validation
            parts = dns.split('.')
            if len(parts) != 4:
                raise ValueError(f'Invalid DNS format: {dns}. Expected IPv4 address')
            try:
                for part in parts:
                    num = int(part)
                    if num < 0 or num > 255:
                        raise ValueError(f'Invalid DNS format: {dns}. Octets must be 0-255')
            except ValueError:
                raise ValueError(f'Invalid DNS format: {dns}. Expected IPv4 address')

        return v

    @validator('public_endpoint')
    def validate_endpoint(cls, v):
        """Validate endpoint format (hostname or IP, no port)"""
        if not v:
            return v

        # Reject if it contains a port
        if ':' in v:
            raise ValueError('Public endpoint should not include port. Port is set per-interface.')

        # Basic validation: allow alphanumeric, dots, dashes, underscores (hostname or IP)
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('Invalid hostname or IP address')

        return v


class ServerSettingsUpdate(BaseModel):
    """Model for updating server settings"""
    public_endpoint: str | None = None
    wg_default_dns: str | None = None

    @validator('wg_default_dns')
    def validate_dns(cls, v):
        """Validate DNS format"""
        if v is None:
            return v
        return ServerSettings.validate_dns(v)

    @validator('public_endpoint')
    def validate_endpoint(cls, v):
        """Validate endpoint format"""
        if v is None:
            return v
        return ServerSettings.validate_endpoint(v)


class DataRetentionSettings(BaseModel):
    """Data retention policy settings"""
    enabled: bool = False
    logs_retention_days: int = Field(default=90, ge=1, le=365)


class TimezonePreference(BaseModel):
    """User timezone preference"""
    timezone: str = Field(default="UTC")


@router.get("", response_model=ServerSettings)
async def get_server_settings(current_user: dict = Depends(get_current_user)):
    """Get server settings (combines env config with database overrides)"""
    # Get database overrides
    db_settings = await get_all_settings()
    
    # Get public_endpoint and handle migration from old format
    public_endpoint = db_settings.get('public_endpoint', config.wg_default_endpoint)
    
    # MIGRATION: Strip port from old endpoint values (e.g., "vpn.example.com:51820" -> "vpn.example.com")
    if public_endpoint and ':' in public_endpoint:
        # Remove port from old value
        public_endpoint = public_endpoint.rsplit(':', 1)[0]
        # Update database with migrated value
        await set_setting('public_endpoint', public_endpoint)
    
    # Merge with config defaults
    return ServerSettings(
        public_endpoint=public_endpoint,
        wg_default_dns=db_settings.get('wg_default_dns', config.wg_default_dns),
        wg_config_path=config.wg_config_path
    )


@router.patch("", response_model=ServerSettings)
async def update_server_settings(
    settings: ServerSettingsUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update server settings (only admin users)"""
    # Only admins can update settings
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Update database with provided values
    if settings.public_endpoint is not None:
        await set_setting('public_endpoint', settings.public_endpoint)
        await add_audit_log(
            current_user.id,
            "settings_update",
            f"Updated public endpoint to: {settings.public_endpoint}"
        )

    if settings.wg_default_dns is not None:
        await set_setting('wg_default_dns', settings.wg_default_dns)
        await add_audit_log(
            current_user.id,
            "settings_update",
            f"Updated default DNS to: {settings.wg_default_dns}"
        )

    # Return updated settings
    db_settings = await get_all_settings()

    # Get public_endpoint and handle migration from old format (same as GET)
    public_endpoint = db_settings.get('public_endpoint', config.wg_default_endpoint)
    if public_endpoint and ':' in public_endpoint:
        public_endpoint = public_endpoint.rsplit(':', 1)[0]
        await set_setting('public_endpoint', public_endpoint)

    return ServerSettings(
        public_endpoint=public_endpoint,
        wg_default_dns=db_settings.get('wg_default_dns', config.wg_default_dns),
        wg_config_path=config.wg_config_path
    )


@router.get("/retention", response_model=DataRetentionSettings)
async def get_retention_settings(current_user: dict = Depends(get_current_user)):
    """Get data retention settings"""
    db_settings = await get_all_settings()

    return DataRetentionSettings(
        enabled=db_settings.get('data_retention_enabled', 'false').lower() == 'true',
        logs_retention_days=int(db_settings.get('data_retention_logs_days', '90'))
    )


@router.patch("/retention", response_model=DataRetentionSettings)
async def update_retention_settings(
    settings: DataRetentionSettings,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update data retention settings (admin-only)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Update settings
    await set_setting('data_retention_enabled', 'true' if settings.enabled else 'false')
    await set_setting('data_retention_logs_days', str(settings.logs_retention_days))

    await add_audit_log(
        current_user.id,
        "settings_update",
        f"Updated data retention: enabled={settings.enabled}, days={settings.logs_retention_days}"
    )

    return settings


@router.get("/timezone", response_model=TimezonePreference)
async def get_timezone_preference(current_user: UserResponse = Depends(get_current_user)):
    """Get user timezone preference"""
    db_settings = await get_all_settings()

    # Store timezone per-user in settings table with key: "user_{id}_timezone"
    timezone_key = f"user_{current_user.id}_timezone"
    timezone = db_settings.get(timezone_key, 'UTC')

    return TimezonePreference(timezone=timezone)


@router.patch("/timezone", response_model=TimezonePreference)
async def update_timezone_preference(
    preference: TimezonePreference,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update user timezone preference"""
    timezone_key = f"user_{current_user.id}_timezone"
    await set_setting(timezone_key, preference.timezone)

    await add_audit_log(
        current_user.id,
        "settings_update",
        f"Updated timezone preference to: {preference.timezone}"
    )

    return preference
