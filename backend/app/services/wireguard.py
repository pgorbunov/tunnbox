import asyncio
import re
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Protocol, runtime_checkable
import secrets
from functools import lru_cache
import logging

from app.config import get_settings
from app.services.config_parser import ConfigParser
from app.models.interface import InterfaceCreate, InterfaceResponse
from app.models.peer import PeerCreate
from app.database import get_all_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def validate_interface_name(name: str) -> None:
    """Validate interface name for safety (defense-in-depth).

    This provides an additional layer of validation beyond Pydantic models
    to ensure interface names cannot be used for path traversal or command injection.

    Args:
        name: Interface name to validate.

    Raises:
        ValueError: If the interface name is invalid or potentially dangerous.
    """
    if not name:
        raise ValueError("Interface name cannot be empty")

    # Strict whitelist: alphanumeric, underscore, hyphen only
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        logger.warning(f"Invalid interface name rejected: {name}")
        raise ValueError(
            "Interface name must contain only alphanumeric characters, underscores, and hyphens"
        )

    # Prevent path traversal
    if ".." in name or "/" in name or "\\" in name:
        logger.warning(f"Path traversal attempt detected in interface name: {name}")
        raise ValueError("Interface name contains invalid path characters")

    # Linux interface name length limit
    if len(name) > 15:
        raise ValueError("Interface name must be 15 characters or less")

    # Prevent reserved names
    reserved = ["all", "default", "lo", "localhost"]
    if name.lower() in reserved:
        raise ValueError(f"Interface name '{name}' is reserved")

@runtime_checkable
class IWireGuardService(Protocol):
    """Protocol defining the interface for WireGuard services."""
    
    async def generate_keypair(self) -> tuple[str, str]: ...
    async def discover_interfaces(self) -> list[str]: ...
    async def get_interface_status(self, name: str) -> dict[str, Any] | None: ...
    async def is_interface_active(self, name: str) -> bool: ...
    async def get_interface(self, name: str) -> InterfaceResponse | None: ...
    async def create_interface(self, config: InterfaceCreate) -> InterfaceResponse: ...
    async def delete_interface(self, name: str) -> None: ...
    async def toggle_interface(self, name: str, up: bool) -> None: ...
    async def sync_interface(self, name: str) -> None: ...
    async def get_peers(self, interface_name: str) -> list[dict[str, Any]]: ...
    async def add_peer(self, interface_name: str, peer: PeerCreate) -> tuple[str, str]: ...
    async def remove_peer(self, interface_name: str, public_key: str) -> None: ...
    async def generate_client_config(self, interface_name: str, peer_public_key: str, peer_private_key: str) -> str: ...
    async def get_next_available_ip(self, interface_name: str) -> str | None: ...


class BaseWireGuardService:
    """Shared logic for WireGuard services."""
    
    def __init__(self):
        self.config_path = Path(settings.wg_config_path)

    # --- Abstract Methods (Must be implemented by subclasses) ---
    async def generate_keypair(self) -> tuple[str, str]:
        raise NotImplementedError
        
    async def _get_public_key_from_private_base(self, private_key: str) -> str:
        raise NotImplementedError
        
    async def is_interface_active(self, name: str) -> bool:
        raise NotImplementedError
        
    async def toggle_interface(self, name: str, up: bool) -> None:
        raise NotImplementedError
        
    async def sync_interface(self, name: str) -> None:
        raise NotImplementedError
        
    async def get_interface_status(self, name: str) -> dict[str, Any] | None:
        raise NotImplementedError
        
    async def discover_interfaces(self) -> list[str]:
        raise NotImplementedError

    # --- Shared Implementation ---

    async def get_interface(self, name: str) -> InterfaceResponse | None:
        """Get full interface details including config and status."""
        validate_interface_name(name)
        config_path = self.config_path / f"{name}.conf"
        if not config_path.exists():
            return None

        # Parse config file
        config = await ConfigParser.parse_config(str(config_path))
        interface_config = config.get("interface", {})

        # Get runtime status
        is_active = await self.is_interface_active(name)
        status = await self.get_interface_status(name) if is_active else None

        # Calculate totals
        total_rx = 0
        total_tx = 0
        peer_count = len(config.get("peers", []))
        active_peer_count = 0

        if status:
            from datetime import datetime, timedelta
                # Consider peer active if handshake is within last 3 minutes (180 seconds)
            cutoff_time = datetime.utcnow() - timedelta(seconds=180)

            for peer in status.get("peers", []):
                total_rx += peer.get("transfer_rx", 0)
                total_tx += peer.get("transfer_tx", 0)

                # Check if peer has recent handshake
                latest_handshake = peer.get("latest_handshake")
                if latest_handshake and latest_handshake > cutoff_time:
                    active_peer_count += 1

        pk = ""
        if status and status.get("public_key"):
             pk = status["public_key"]
        else:
             pk = await self._get_public_key_from_private_base(interface_config.get("privatekey", ""))

        return InterfaceResponse(
            name=name,
            listen_port=int(interface_config.get("listenport", 51820)),
            address=interface_config.get("address", ""),
            public_key=pk,
            is_active=is_active,
            peer_count=peer_count,
            active_peer_count=active_peer_count,
            total_transfer_rx=total_rx,
            total_transfer_tx=total_tx,
            dns=interface_config.get("dns"),
            post_up=interface_config.get("postup"),
            post_down=interface_config.get("postdown"),
        )
    
    async def create_interface(self, config: InterfaceCreate) -> InterfaceResponse:
        """Create a new WireGuard interface."""
        validate_interface_name(config.name)
        config_path = self.config_path / f"{config.name}.conf"

        if config_path.exists():
            raise ValueError(f"Interface {config.name} already exists")

        # Generate keypair (polymorphic)
        private_key, public_key = await self.generate_keypair()

        # Get global DNS default from database for auto-populate
        db_settings = await get_all_settings()
        default_dns = db_settings.get('wg_default_dns', settings.wg_default_dns)

        # Build config
        interface_config = {
            "interface": {
                "privatekey": private_key,
                "address": config.address,
                "listenport": str(config.listen_port),
            },
            "peers": []
        }

        # Use provided DNS or fall back to global default
        dns_to_use = config.dns if config.dns else default_dns

        if dns_to_use:
            interface_config["interface"]["dns"] = dns_to_use
        if config.post_up:
            interface_config["interface"]["postup"] = config.post_up
        if config.post_down:
            interface_config["interface"]["postdown"] = config.post_down

        # Write config file
        await ConfigParser.write_config(str(config_path), interface_config)

        return InterfaceResponse(
            name=config.name,
            listen_port=config.listen_port,
            address=config.address,
            public_key=public_key,
            is_active=False,
            peer_count=0,
            active_peer_count=0,
            total_transfer_rx=0,
            total_transfer_tx=0,
            dns=dns_to_use,
            post_up=config.post_up,
            post_down=config.post_down,
        )

    async def delete_interface(self, name: str) -> None:
        """Delete a WireGuard interface."""
        validate_interface_name(name)
        # First, bring interface down if active
        if await self.is_interface_active(name):
            await self.toggle_interface(name, up=False)

        # Remove config file
        config_path = self.config_path / f"{name}.conf"
        if config_path.exists():
            config_path.unlink()
            
    async def get_peers(self, interface_name: str) -> list[dict[str, Any]]:
        """Get all peers for an interface with runtime stats."""
        validate_interface_name(interface_name)
        config_path = self.config_path / f"{interface_name}.conf"
        if not config_path.exists():
            raise ValueError(f"Interface {interface_name} not found")

        # Parse config
        config = await ConfigParser.parse_config(str(config_path))
        config_peers = {p.get("publickey"): p for p in config.get("peers", [])}

        # Get runtime status
        status = await self.get_interface_status(interface_name)
        status_peers = {}
        if status:
            status_peers = {p["public_key"]: p for p in status.get("peers", [])}

        # Merge config and status
        peers = []
        for public_key, config_peer in config_peers.items():
            status_peer = status_peers.get(public_key, {})

            latest_handshake = status_peer.get("latest_handshake")
            is_online = False
            if latest_handshake:
                # Consider peer online if handshake was within last 180 seconds (3 minutes)
                # Standard WireGuard keepalive/timeout behavior
                is_online = (datetime.utcnow() - latest_handshake).total_seconds() < 180

            peers.append({
                "public_key": public_key,
                "allowed_ips": config_peer.get("allowedips", ""),
                "endpoint": status_peer.get("endpoint"),
                "latest_handshake": latest_handshake,
                "transfer_rx": status_peer.get("transfer_rx", 0),
                "transfer_tx": status_peer.get("transfer_tx", 0),
                "is_online": is_online,
                "persistent_keepalive": int(config_peer.get("persistentkeepalive", 0) or 0),
            })

        return peers
            
    async def add_peer(self, interface_name: str, peer: PeerCreate) -> tuple[str, str]:
        """Add a peer to an interface. Returns (public_key, private_key)."""
        validate_interface_name(interface_name)
        config_path = self.config_path / f"{interface_name}.conf"
        if not config_path.exists():
            raise ValueError(f"Interface {interface_name} not found")

        # Generate keypair for client
        private_key, public_key = await self.generate_keypair()

        # Add peer to config
        peer_config = {
            "publickey": public_key,
            "allowedips": peer.allowed_ips,
        }
        if peer.persistent_keepalive > 0:
            peer_config["persistentkeepalive"] = str(peer.persistent_keepalive)

        await ConfigParser.add_peer_to_config(str(config_path), peer_config)

        # Sync if interface is active
        if await self.is_interface_active(interface_name):
            await self.sync_interface(interface_name)

        return public_key, private_key

    async def remove_peer(self, interface_name: str, public_key: str) -> None:
        """Remove a peer from an interface."""
        validate_interface_name(interface_name)
        config_path = self.config_path / f"{interface_name}.conf"
        if not config_path.exists():
            raise ValueError(f"Interface {interface_name} not found")

        await ConfigParser.remove_peer_from_config(str(config_path), public_key)

        # Sync if interface is active
        if await self.is_interface_active(interface_name):
            await self.sync_interface(interface_name)

    async def generate_client_config(
        self,
        interface_name: str,
        peer_public_key: str,
        peer_private_key: str,
    ) -> str:
        """Generate a complete client configuration file."""
        validate_interface_name(interface_name)
        config_path = self.config_path / f"{interface_name}.conf"
        if not config_path.exists():
            raise ValueError(f"Interface {interface_name} not found")

        # Get interface config
        config = await ConfigParser.parse_config(str(config_path))
        interface_config = config.get("interface", {})

        # Find peer config
        peer_config = None
        for p in config.get("peers", []):
            if p.get("publickey") == peer_public_key:
                peer_config = p
                break

        if not peer_config:
            raise ValueError(f"Peer not found in interface {interface_name}")

        # Get server public key
        server_public_key = await self._get_public_key_from_private_base(
            interface_config.get("privatekey", "")
        )

        # Build client config
        # Get global public endpoint from settings and construct full endpoint
        db_settings = await get_all_settings()
        public_endpoint = db_settings.get('public_endpoint', settings.wg_default_endpoint)
        listen_port = interface_config.get("listenport", "51820")
        
        # Construct full endpoint: hostname:port
        endpoint = f"{public_endpoint}:{listen_port}"
        
        dns = interface_config.get("dns", settings.wg_default_dns)
        client_ip = peer_config.get("allowedips", "").split(",")[0].strip()

        lines = [
            "[Interface]",
            f"Address = {client_ip}",
            f"PrivateKey = {peer_private_key}",
        ]
        if dns:
            lines.append(f"DNS = {dns}")

        lines.extend([
            "",
            "[Peer]",
            f"PublicKey = {server_public_key}",
            f"AllowedIPs = 0.0.0.0/0, ::/0",
            f"Endpoint = {endpoint}",
            "PersistentKeepalive = 25",
        ])

        return "\n".join(lines) + "\n"

    async def get_next_available_ip(self, interface_name: str) -> str | None:
        """Calculate the next available IP in the interface's subnet."""
        validate_interface_name(interface_name)
        config_path = self.config_path / f"{interface_name}.conf"
        if not config_path.exists():
            return None

        config = await ConfigParser.parse_config(str(config_path))
        interface_address = config.get("interface", {}).get("address", "")

        if not interface_address:
            return None

        # Parse the interface address (e.g., "10.0.0.1/24")
        match = re.match(r"(\d+)\.(\d+)\.(\d+)\.(\d+)/(\d+)", interface_address)
        if not match:
            return None

        base_ip = [int(match.group(i)) for i in range(1, 5)]
        
        # Get all used IPs
        used_ips = set()
        used_ips.add(tuple(base_ip))  # Server IP

        for peer in config.get("peers", []):
            allowed_ips = peer.get("allowedips", "")
            for ip_range in allowed_ips.split(","):
                ip_match = re.match(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", ip_range.strip())
                if ip_match:
                    used_ips.add(tuple(int(ip_match.group(i)) for i in range(1, 5)))

        # Find next available IP (simple approach: increment last octet)
        for i in range(2, 255):
            candidate = (base_ip[0], base_ip[1], base_ip[2], i)
            if candidate not in used_ips:
                return f"{candidate[0]}.{candidate[1]}.{candidate[2]}.{candidate[3]}/32"

        return None
    
    # Helper methods (copied from original)
    def _parse_handshake_time(self, hs_str: str) -> datetime | None:
        if not hs_str or hs_str == "(none)":
            return None
        total_seconds = 0
        patterns = [
            (r"(\d+)\s*day", 86400),
            (r"(\d+)\s*hour", 3600),
            (r"(\d+)\s*minute", 60),
            (r"(\d+)\s*second", 1),
        ]
        for pattern, multiplier in patterns:
            match = re.search(pattern, hs_str)
            if match:
                total_seconds += int(match.group(1)) * multiplier
        if total_seconds > 0:
            return datetime.utcnow() - timedelta(seconds=total_seconds)
        return None

    def _parse_transfer(self, transfer_str: str) -> tuple[int, int]:
        rx, tx = 0, 0
        units = {"B": 1, "KiB": 1024, "MiB": 1024 * 1024, "GiB": 1024 * 1024 * 1024, "TiB": 1024 * 1024 * 1024 * 1024}
        rx_match = re.search(r"([\d.]+)\s*(\w+)\s*received", transfer_str)
        if rx_match:
            value, unit = float(rx_match.group(1)), rx_match.group(2)
            rx = int(value * units.get(unit, 1))
        tx_match = re.search(r"([\d.]+)\s*(\w+)\s*sent", transfer_str)
        if tx_match:
            value, unit = float(tx_match.group(1)), tx_match.group(2)
            tx = int(value * units.get(unit, 1))
        return rx, tx


class RealWireGuardService(BaseWireGuardService):
    """Service for managing WireGuard interfaces and peers on Linux."""

    async def _run_command(self, *args: str, sudo: bool = False) -> tuple[str, str, int]:
        cmd = list(args)
        if sudo:
            cmd = ["sudo"] + cmd
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return stdout.decode(), stderr.decode(), process.returncode

    async def generate_keypair(self) -> tuple[str, str]:
        stdout, _, _ = await self._run_command("wg", "genkey")
        private_key = stdout.strip()
        process = await asyncio.create_subprocess_exec(
            "wg", "pubkey", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate(private_key.encode())
        public_key = stdout.decode().strip()
        return private_key, public_key

    async def _get_public_key_from_private_base(self, private_key: str) -> str:
        if not private_key: return ""
        process = await asyncio.create_subprocess_exec(
            "wg", "pubkey", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate(private_key.encode())
        return stdout.decode().strip()

    async def discover_interfaces(self) -> list[str]:
        if not self.config_path.exists(): return []
        interfaces = []
        for conf_file in self.config_path.glob("*.conf"):
            interfaces.append(conf_file.stem)
        return sorted(interfaces)

    async def get_interface_status(self, name: str) -> dict[str, Any] | None:
        validate_interface_name(name)
        stdout, stderr, returncode = await self._run_command("wg", "show", name)
        if returncode != 0: return None
        status = {
            "name": name, "is_active": True, "public_key": "", "listen_port": 0, "peers": []
        }
        current_peer = None
        for line in stdout.split("\n"):
            line = line.strip()
            if not line: continue
            if line.startswith("interface:"): continue
            elif line.startswith("public key:"):
                status["public_key"] = line.split(":", 1)[1].strip()
            elif line.startswith("listening port:"):
                status["listen_port"] = int(line.split(":", 1)[1].strip())
            elif line.startswith("peer:"):
                if current_peer: status["peers"].append(current_peer)
                current_peer = {
                    "public_key": line.split(":", 1)[1].strip(), "endpoint": None, "allowed_ips": "",
                    "latest_handshake": None, "transfer_rx": 0, "transfer_tx": 0, "persistent_keepalive": 0,
                }
            elif current_peer:
                if line.startswith("endpoint:"): current_peer["endpoint"] = line.split(":", 1)[1].strip()
                elif line.startswith("allowed ips:"): current_peer["allowed_ips"] = line.split(":", 1)[1].strip()
                elif line.startswith("latest handshake:"):
                    hs_str = line.split(":", 1)[1].strip()
                    current_peer["latest_handshake"] = self._parse_handshake_time(hs_str)
                elif line.startswith("transfer:"):
                    transfer_str = line.split(":", 1)[1].strip()
                    rx, tx = self._parse_transfer(transfer_str)
                    current_peer["transfer_rx"] = rx
                    current_peer["transfer_tx"] = tx
                elif line.startswith("persistent keepalive:"):
                    ka_str = line.split(":", 1)[1].strip()
                    if ka_str != "off":
                        match = re.search(r"(\d+)", ka_str)
                        if match: current_peer["persistent_keepalive"] = int(match.group(1))
        if current_peer: status["peers"].append(current_peer)
        return status

    async def is_interface_active(self, name: str) -> bool:
        validate_interface_name(name)
        stdout, _, returncode = await self._run_command("ip", "link", "show", name)
        return returncode == 0

    async def toggle_interface(self, name: str, up: bool) -> None:
        validate_interface_name(name)
        action = "up" if up else "down"
        _, stderr, returncode = await self._run_command("wg-quick", action, name)
        if returncode != 0 and "already" not in stderr.lower():
            raise RuntimeError(f"Failed to {action} interface: {stderr}")

    async def sync_interface(self, name: str) -> None:
        validate_interface_name(name)
        config_path = self.config_path / f"{name}.conf"

        # Use wg-quick strip to generate a config file compatible with wg syncconf
        # wg syncconf doesn't understand Address, PostUp, etc.
        stripped_config, stderr, returncode = await self._run_command("wg-quick", "strip", str(config_path))
        if returncode != 0:
            raise RuntimeError(f"Failed to strip config: {stderr}")
            
        # Write stripped config to a temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write(stripped_config)
            tmp_path = tmp.name
            
        try:
            _, stderr, returncode = await self._run_command("wg", "syncconf", name, tmp_path)
            if returncode != 0:
                raise RuntimeError(f"Failed to sync interface: {stderr}")
        finally:
            os.unlink(tmp_path)


class MockWireGuardService(BaseWireGuardService):
    """Mock service for non-Linux development environments."""

    def __init__(self):
        super().__init__()
        # Check if path is the default Linux path (normalized for OS)
        path_str = str(self.config_path).replace("\\", "/")
        if "/etc/wireguard" in path_str:
            self.config_path = Path("./data/wireguard")
            self.config_path.mkdir(parents=True, exist_ok=True)
            print(f"MockWireGuardService: Using local config path: {self.config_path}")
        self._active_interfaces: set[str] = set()
        
    async def generate_keypair(self) -> tuple[str, str]:
        pk = secrets.token_urlsafe(32)
        pub = secrets.token_urlsafe(32)
        return pk, pub

    async def _get_public_key_from_private_base(self, private_key: str) -> str:
        return f"MOCK_PUB_FOR_{private_key[:8]}..."

    async def discover_interfaces(self) -> list[str]:
        if not self.config_path.exists(): return []
        return sorted([f.stem for f in self.config_path.glob("*.conf")])

    async def is_interface_active(self, name: str) -> bool:
        return name in self._active_interfaces

    async def toggle_interface(self, name: str, up: bool) -> None:
        if up: self._active_interfaces.add(name)
        else: self._active_interfaces.discard(name)

    async def sync_interface(self, name: str) -> None:
        pass

    async def get_interface_status(self, name: str) -> dict[str, Any] | None:
        if name not in self._active_interfaces: return None
        return {
            "name": name, "is_active": True, "public_key": "MOCK_SERVER_PUBLIC_KEY", "listen_port": 51820,
            "peers": [
                {
                    "public_key": "MOCK_PEER_KEY_1", "endpoint": "1.2.3.4:12345", "allowed_ips": "10.0.0.2/32",
                    "latest_handshake": datetime.utcnow() - timedelta(minutes=1),
                    "transfer_rx": 1024 * 1024 * 5, "transfer_tx": 1024 * 1024 * 2, "persistent_keepalive": 25,
                }
            ]
        }


@lru_cache
def get_wireguard_service() -> IWireGuardService:
    """Factory to get the appropriate WireGuard service instance."""
    mode = settings.wg_backend_mode.lower()
    
    if mode == "auto":
        is_linux = sys.platform.startswith("linux")
        mode = "real" if is_linux else "mock"
    
    if mode == "real":
        return RealWireGuardService()
    else:
        return MockWireGuardService()