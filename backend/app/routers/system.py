"""System information endpoints."""
from fastapi import APIRouter, Depends
import platform
import sys
import subprocess
from pydantic import BaseModel
from app.routers.auth import get_current_user
from app.models.user import UserResponse

router = APIRouter()


class SystemInfo(BaseModel):
    """System information response model."""
    # Version information
    frontend_version: str
    backend_version: str
    wireguard_version: str | None
    docker_version: str | None

    # System information
    os_name: str
    os_version: str
    python_version: str
    database_type: str

    # Links
    github_url: str
    documentation_url: str

    # License
    license: str


def get_command_version(command: str, args: list[str] = ["--version"]) -> str | None:
    """Get version from a command line tool."""
    try:
        result = subprocess.run(
            [command] + args,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Get first line of output and clean it up
            version = result.stdout.strip().split('\n')[0]
            return version
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return None


@router.get("/api/system/info", response_model=SystemInfo)
async def get_system_info(current_user: UserResponse = Depends(get_current_user)):
    """Get system information and versions."""

    # Get WireGuard version
    wg_version = get_command_version("wg", ["--version"])

    # Get Docker version (if running in container)
    docker_version = get_command_version("docker", ["--version"])

    # Get OS information
    os_name = platform.system()
    os_version = platform.release()

    # Get Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    return SystemInfo(
        frontend_version="1.0.0",  # TODO: Read from package.json
        backend_version="1.0.0",   # TODO: Read from version file
        wireguard_version=wg_version,
        docker_version=docker_version,
        os_name=os_name,
        os_version=os_version,
        python_version=python_version,
        database_type="SQLite",  # Currently using SQLite
        github_url="https://github.com/pgorbunov/tunnbox",
        documentation_url="https://github.com/pgorbunov/tunnbox/blob/main/README.md",
        license="MIT"
    )
