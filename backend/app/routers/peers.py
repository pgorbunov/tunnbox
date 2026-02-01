from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response
from urllib.parse import quote

from app.dependencies import get_current_user, create_qr_token, validate_qr_token
from app.database import (
    add_audit_log,
    save_peer_metadata,
    get_peer_metadata,
    get_all_peer_metadata,
    delete_peer_metadata,
)
from app.models.user import UserResponse
from app.models.peer import PeerCreate, PeerUpdate, PeerResponse
from app.services.wireguard import get_wireguard_service
from app.services.qr_generator import QRGenerator

router = APIRouter()
wg_service = get_wireguard_service()


@router.get("/{interface_name}/peers", response_model=list[PeerResponse])
async def list_peers(
    interface_name: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """List all peers for an interface."""
    try:
        peers_data = await wg_service.get_peers(interface_name)
        peer_metadata = await get_all_peer_metadata(interface_name)
        metadata_map = {m["public_key"]: m for m in peer_metadata}

        peers = []
        for peer in peers_data:
            meta = metadata_map.get(peer["public_key"], {})
            peers.append(PeerResponse(
                name=meta.get("name", peer["public_key"][:8] + "..."),
                public_key=peer["public_key"],
                allowed_ips=peer["allowed_ips"],
                endpoint=peer.get("endpoint"),
                latest_handshake=peer.get("latest_handshake"),
                transfer_rx=peer.get("transfer_rx", 0),
                transfer_tx=peer.get("transfer_tx", 0),
                is_online=peer.get("is_online", False),
                persistent_keepalive=peer.get("persistent_keepalive", 0),
            ))

        return peers
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{interface_name}/peers", response_model=PeerResponse, status_code=status.HTTP_201_CREATED)
async def add_peer(
    interface_name: str,
    request: Request,
    peer: PeerCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Add a new peer to an interface."""
    try:
        # If no allowed_ips provided, generate next available IP
        if not peer.allowed_ips or peer.allowed_ips == "auto":
            next_ip = await wg_service.get_next_available_ip(interface_name)
            if not next_ip:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not determine next available IP",
                )
            peer.allowed_ips = next_ip

        public_key, private_key = await wg_service.add_peer(interface_name, peer)

        # Save metadata including private key for config generation
        await save_peer_metadata(
            interface_name,
            public_key,
            peer.name,
            private_key,
        )

        await add_audit_log(
            current_user.id,
            "add_peer",
            f"Added peer {peer.name} to {interface_name}",
            request.client.host if request.client else None,
        )

        return PeerResponse(
            name=peer.name,
            public_key=public_key,
            allowed_ips=peer.allowed_ips,
            endpoint=None,
            latest_handshake=None,
            transfer_rx=0,
            transfer_tx=0,
            is_online=False,
            persistent_keepalive=peer.persistent_keepalive,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{interface_name}/peers/config/{public_key:path}")
async def get_peer_config(
    interface_name: str,
    public_key: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Download client configuration file."""
    metadata = await get_peer_metadata(interface_name, public_key)
    if not metadata or not metadata.get("private_key"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer configuration not available. The private key was not stored.",
        )

    try:
        config = await wg_service.generate_client_config(
            interface_name,
            public_key,
            metadata["private_key"],
        )

        filename = f"{metadata.get('name', 'peer')}.conf"

        return Response(
            content=config,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="{quote(filename)}"',
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{interface_name}/peers/qr/{public_key:path}")
async def generate_qr_token(
    interface_name: str,
    public_key: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Generate a short-lived signed token for QR code access."""
    metadata = await get_peer_metadata(interface_name, public_key)
    if not metadata or not metadata.get("private_key"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer configuration not available. The private key was not stored.",
        )

    # Create signed token
    qr_token = create_qr_token(interface_name, public_key)

    return {"qr_token": qr_token}


@router.get("/{interface_name}/peers/{public_key:path}", response_model=PeerResponse)
async def get_peer(
    interface_name: str,
    public_key: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a specific peer's details."""
    try:
        peers_data = await wg_service.get_peers(interface_name)
        peer_data = next((p for p in peers_data if p["public_key"] == public_key), None)

        if not peer_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Peer not found",
            )

        metadata = await get_peer_metadata(interface_name, public_key)

        return PeerResponse(
            name=metadata.get("name", public_key[:8] + "...") if metadata else public_key[:8] + "...",
            public_key=public_key,
            allowed_ips=peer_data["allowed_ips"],
            endpoint=peer_data.get("endpoint"),
            latest_handshake=peer_data.get("latest_handshake"),
            transfer_rx=peer_data.get("transfer_rx", 0),
            transfer_tx=peer_data.get("transfer_tx", 0),
            is_online=peer_data.get("is_online", False),
            persistent_keepalive=peer_data.get("persistent_keepalive", 0),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put("/{interface_name}/peers/{public_key:path}", response_model=PeerResponse)
async def update_peer(
    interface_name: str,
    public_key: str,
    request: Request,
    updates: PeerUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Update a peer's configuration."""
    try:
        from app.services.config_parser import ConfigParser
        from app.config import get_settings

        settings = get_settings()
        config_path = f"{settings.wg_config_path}/{interface_name}.conf"

        peer_updates = {}
        if updates.allowed_ips is not None:
            peer_updates["allowedips"] = updates.allowed_ips
        if updates.persistent_keepalive is not None:
            peer_updates["persistentkeepalive"] = str(updates.persistent_keepalive)

        if peer_updates:
            await ConfigParser.update_peer_in_config(config_path, public_key, peer_updates)

            # Sync if interface is active
            if await wg_service.is_interface_active(interface_name):
                await wg_service.sync_interface(interface_name)

        # Update metadata
        if updates.name is not None:
            metadata = await get_peer_metadata(interface_name, public_key)
            if metadata:
                await save_peer_metadata(
                    interface_name,
                    public_key,
                    updates.name,
                    metadata.get("private_key"),
                )

        await add_audit_log(
            current_user.id,
            "update_peer",
            f"Updated peer in {interface_name}",
            request.client.host if request.client else None,
        )

        # Return updated peer
        return await get_peer(interface_name, public_key, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{interface_name}/peers/{public_key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_peer(
    interface_name: str,
    public_key: str,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
):
    """Remove a peer from an interface."""
    try:
        await wg_service.remove_peer(interface_name, public_key)
        await delete_peer_metadata(interface_name, public_key)

        await add_audit_log(
            current_user.id,
            "remove_peer",
            f"Removed peer from {interface_name}",
            request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/{interface_name}/next-ip")
async def get_next_available_ip(
    interface_name: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get the next available IP address for the interface."""
    next_ip = await wg_service.get_next_available_ip(interface_name)
    if not next_ip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not determine next available IP",
        )
    return {"next_ip": next_ip}
