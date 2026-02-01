import re
from pathlib import Path
from typing import Any
import aiofiles


class ConfigParser:
    """Parser for WireGuard configuration files."""

    @staticmethod
    async def parse_config(path: str) -> dict[str, Any]:
        """Parse a WireGuard .conf file into structured data."""
        config = {
            "interface": {},
            "peers": []
        }

        async with aiofiles.open(path, "r") as f:
            content = await f.read()

        current_section = None
        current_data = {}

        for line in content.split("\n"):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                # Detect custom PublicEndpoint comment
                if line.startswith("# PublicEndpoint = "):
                    # It usually appears in the Interface section block or at top
                    # We'll attach it to the interface config regardless of current section context if it's the first one,
                    # or if current_section is None or "interface"
                    if current_section != "peer":
                       # Temporarily store it, will merge into interface dict later if current_data is active, 
                       # or directly into config['interface'] if not.
                       # Actually easier: just put it in config['interface'] directly.
                       config["interface"]["public_endpoint"] = line.split("=", 1)[1].strip()
                continue

            # Section headers
            if line.lower() == "[interface]":
                if current_section == "peer" and current_data:
                    config["peers"].append(current_data)
                current_section = "interface"
                current_data = {}
                continue

            if line.lower() == "[peer]":
                if current_section == "interface":
                    config["interface"].update(current_data) # Merge instead of overwrite to keep public_endpoint
                elif current_section == "peer" and current_data:
                    config["peers"].append(current_data)
                current_section = "peer"
                current_data = {}
                continue

            # Key-value pairs
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Normalize key names to lowercase with underscores
                key_normalized = key.lower().replace(" ", "_")
                current_data[key_normalized] = value

        # Don't forget the last section
        if current_section == "interface":
            config["interface"].update(current_data)
        elif current_section == "peer" and current_data:
            config["peers"].append(current_data)

        return config

    @staticmethod
    async def write_config(path: str, config: dict[str, Any]) -> None:
        """Write structured data to a WireGuard .conf file."""
        lines = []

        # Interface section
        lines.append("[Interface]")
        interface = config.get("interface", {})
        
        # Write PublicEndpoint comment
        if "public_endpoint" in interface and interface["public_endpoint"]:
            lines.append(f"# PublicEndpoint = {interface['public_endpoint']}")

        key_order = ["privatekey", "address", "listenport", "dns", "postup", "postdown", "mtu"]

        # Write keys in preferred order
        for key in key_order:
            if key in interface:
                display_key = ConfigParser._normalize_key_for_write(key)
                lines.append(f"{display_key} = {interface[key]}")

        # Write any remaining keys
        for key, value in interface.items():
            if key not in key_order and key != "public_endpoint":
                display_key = ConfigParser._normalize_key_for_write(key)
                lines.append(f"{display_key} = {value}")

        # Peer sections
        for peer in config.get("peers", []):
            lines.append("")
            lines.append("[Peer]")
            peer_key_order = ["publickey", "presharedkey", "allowedips", "endpoint", "persistentkeepalive"]

            for key in peer_key_order:
                if key in peer:
                    display_key = ConfigParser._normalize_key_for_write(key)
                    lines.append(f"{display_key} = {peer[key]}")

            for key, value in peer.items():
                if key not in peer_key_order:
                    display_key = ConfigParser._normalize_key_for_write(key)
                    lines.append(f"{display_key} = {value}")

        async with aiofiles.open(path, "w") as f:
            await f.write("\n".join(lines) + "\n")

    @staticmethod
    def _normalize_key_for_write(key: str) -> str:
        """Convert normalized key back to WireGuard config format."""
        key_map = {
            "privatekey": "PrivateKey",
            "publickey": "PublicKey",
            "presharedkey": "PresharedKey",
            "address": "Address",
            "listenport": "ListenPort",
            "dns": "DNS",
            "postup": "PostUp",
            "postdown": "PostDown",
            "allowedips": "AllowedIPs",
            "endpoint": "Endpoint",
            "persistentkeepalive": "PersistentKeepalive",
            "mtu": "MTU",
        }
        return key_map.get(key, key.title())

    @staticmethod
    async def add_peer_to_config(path: str, peer: dict[str, str]) -> None:
        """Append a [Peer] section to an existing config file."""
        config = await ConfigParser.parse_config(path)
        config["peers"].append(peer)
        await ConfigParser.write_config(path, config)

    @staticmethod
    async def remove_peer_from_config(path: str, public_key: str) -> None:
        """Remove a [Peer] section by public key."""
        config = await ConfigParser.parse_config(path)
        config["peers"] = [
            p for p in config["peers"]
            if p.get("publickey") != public_key
        ]
        await ConfigParser.write_config(path, config)

    @staticmethod
    async def update_peer_in_config(path: str, public_key: str, updates: dict[str, str]) -> None:
        """Update a peer's configuration by public key."""
        config = await ConfigParser.parse_config(path)
        for peer in config["peers"]:
            if peer.get("publickey") == public_key:
                peer.update(updates)
                break
        await ConfigParser.write_config(path, config)
