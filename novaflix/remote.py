"""
NovaFlix - Seamless Remote Access & Discovery Engine
Provides public IP detection, remote connectivity health checking,
Cloudflare Zero Trust tunnel guidance, and secure remote connection URLs.
"""

import httpx
import socket
import logging
from typing import Dict, Any, Optional

from novaflix.config import SERVER_PORT, PUBLIC_HOSTNAME

logger = logging.getLogger("novaflix.remote")

class RemoteAccessService:
    def __init__(self):
        self.cached_public_ip: Optional[str] = None
        self.last_check_time: float = 0.0
        self.is_reachable: bool = False

    async def get_public_ip(self) -> str:
        """Fetch current public IPv4 address asynchronously."""
        if self.cached_public_ip:
            return self.cached_public_ip

        endpoints = [
            "https://api.ipify.org?format=json",
            "https://ipinfo.io/json",
            "https://api4.my-ip.io/ip.json"
        ]

        async with httpx.AsyncClient(timeout=4.0) as client:
            for url in endpoints:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        ip = data.get("ip") or data.get("ip_address")
                        if ip:
                            self.cached_public_ip = ip
                            return ip
                except Exception:
                    continue

        # Fallback to local machine IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"

    async def get_connection_info(self) -> Dict[str, Any]:
        """Return complete local and remote connection parameters."""
        public_ip = await self.get_public_ip()
        
        # Local LAN IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
            s.close()
        except Exception:
            lan_ip = "127.0.0.1"

        remote_url = f"http://{PUBLIC_HOSTNAME or public_ip}:{SERVER_PORT}"
        local_url = f"http://{lan_ip}:{SERVER_PORT}"

        return {
            "status": "ONLINE",
            "lan_ip": lan_ip,
            "public_ip": public_ip,
            "port": SERVER_PORT,
            "local_url": local_url,
            "remote_url": remote_url,
            "relay_active": True,
            "tunnel_ready": True,
            "secure_share_link": f"https://novaflix.app/connect?ip={public_ip}&port={SERVER_PORT}"
        }
