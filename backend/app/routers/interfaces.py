from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.dependencies import get_current_user
from app.database import add_audit_log
from app.models.user import UserResponse
from app.models.interface import InterfaceCreate, InterfaceUpdate, InterfaceResponse
from app.services.wireguard import get_wireguard_service

router = APIRouter()
wg_service = get_wireguard_service()


@router.get("", response_model=list[InterfaceResponse])
async def list_interfaces(current_user: UserResponse = Depends(get_current_user)):
    """List all WireGuard interfaces."""
    interface_names = await wg_service.discover_interfaces()
    interfaces = []

    for name in interface_names:
        interface = await wg_service.get_interface(name)
        if interface:
            interfaces.append(interface)

    return interfaces


@router.post("", response_model=InterfaceResponse, status_code=status.HTTP_201_CREATED)
async def create_interface(
    request: Request,
    config: InterfaceCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Create a new WireGuard interface."""
    try:
        interface = await wg_service.create_interface(config)

        await add_audit_log(
            current_user.id,
            "create_interface",
            f"Created interface {config.name}",
            request.client.host if request.client else None,
        )

        return interface
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Check server configuration.",
        )


@router.get("/{name}", response_model=InterfaceResponse)
async def get_interface(
    name: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a specific interface's details."""
    interface = await wg_service.get_interface(name)
    if not interface:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interface {name} not found",
        )
    return interface


@router.put("/{name}", response_model=InterfaceResponse)
async def update_interface(
    name: str,
    request: Request,
    updates: InterfaceUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Update an interface's settings."""
    interface = await wg_service.get_interface(name)
    if not interface:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interface {name} not found",
        )

    # For now, we'll need to manually update the config
    # This is a simplified version - a full implementation would
    # parse and update the config file
    from app.services.config_parser import ConfigParser
    from app.config import get_settings

    settings = get_settings()
    config_path = f"{settings.wg_config_path}/{name}.conf"

    config = await ConfigParser.parse_config(config_path)

    if updates.listen_port is not None:
        config["interface"]["listenport"] = str(updates.listen_port)
    if updates.address is not None:
        config["interface"]["address"] = updates.address
    if updates.dns is not None:
        config["interface"]["dns"] = updates.dns
    if updates.post_up is not None:
        config["interface"]["postup"] = updates.post_up
    if updates.post_down is not None:
        config["interface"]["postdown"] = updates.post_down
    if updates.public_endpoint is not None:
        config["interface"]["public_endpoint"] = updates.public_endpoint

    await ConfigParser.write_config(config_path, config)

    await add_audit_log(
        current_user.id,
        "update_interface",
        f"Updated interface {name}",
        request.client.host if request.client else None,
    )

    return await wg_service.get_interface(name)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interface(
    name: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete an interface."""
    interface = await wg_service.get_interface(name)
    if not interface:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interface {name} not found",
        )

    try:
        await wg_service.delete_interface(name)

        await add_audit_log(
            current_user.id,
            "delete_interface",
            f"Deleted interface {name}",
            request.client.host if request.client else None,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{name}/up", status_code=status.HTTP_200_OK)
async def bring_interface_up(
    name: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
):
    """Bring an interface up."""
    interface = await wg_service.get_interface(name)
    if not interface:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interface {name} not found",
        )

    try:
        await wg_service.toggle_interface(name, up=True)

        await add_audit_log(
            current_user.id,
            "interface_up",
            f"Brought interface {name} up",
            request.client.host if request.client else None,
        )

        return {"message": f"Interface {name} is now up"}
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{name}/down", status_code=status.HTTP_200_OK)
async def bring_interface_down(
    name: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
):
    """Bring an interface down."""
    interface = await wg_service.get_interface(name)
    if not interface:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interface {name} not found",
        )

    try:
        await wg_service.toggle_interface(name, up=False)

        await add_audit_log(
            current_user.id,
            "interface_down",
            f"Brought interface {name} down",
            request.client.host if request.client else None,
        )

        return {"message": f"Interface {name} is now down"}
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{name}/stats")
async def get_interface_stats(
    name: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get real-time stats for an interface."""
    status = await wg_service.get_interface_status(name)
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if status is None else status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Interface {name} not found or not active",
        )

    total_rx = sum(p.get("transfer_rx", 0) for p in status.get("peers", []))
    total_tx = sum(p.get("transfer_tx", 0) for p in status.get("peers", []))

    return {
        "name": name,
        "is_active": status.get("is_active", False),
        "peer_count": len(status.get("peers", [])),
        "total_transfer_rx": total_rx,
        "total_transfer_tx": total_tx,
        "peers": [
            {
                "public_key": p["public_key"],
                "endpoint": p.get("endpoint"),
                "latest_handshake": p.get("latest_handshake"),
                "transfer_rx": p.get("transfer_rx", 0),
                "transfer_tx": p.get("transfer_tx", 0),
            }
            for p in status.get("peers", [])
        ],
    }
