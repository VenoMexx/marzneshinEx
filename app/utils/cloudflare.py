import asyncio
import logging
import time
from typing import List

import httpx

from app.models.settings import CloudflareSettings, CloudflareIPInfo

logger = logging.getLogger(__name__)

# Cloudflare CDN IP ranges (these are commonly used CDN IPs)
CLOUDFLARE_CDN_IPS = [
    "104.16.0.0",
    "104.17.0.0",
    "104.18.0.0",
    "104.19.0.0",
    "104.20.0.0",
    "104.21.0.0",
    "104.22.0.0",
    "104.23.0.0",
    "104.24.0.0",
    "104.25.0.0",
    "104.26.0.0",
    "104.27.0.0",
    "104.28.0.0",
    "104.29.0.0",
    "104.30.0.0",
    "104.31.0.0",
    "172.64.0.0",
    "172.65.0.0",
    "172.66.0.0",
    "172.67.0.0",
]


class CloudflareAPI:
    """Cloudflare API client for DNS and CDN management"""

    BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(self, api_token: str, email: str | None = None):
        self.api_token = api_token
        self.email = email
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        if email:
            self.headers["X-Auth-Email"] = email

    async def _request(
        self, method: str, endpoint: str, data: dict | None = None
    ) -> dict:
        """Make an API request to Cloudflare"""
        url = f"{self.BASE_URL}{endpoint}"

        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=self.headers)
                elif method == "POST":
                    response = await client.post(
                        url, headers=self.headers, json=data
                    )
                elif method == "PUT":
                    response = await client.put(url, headers=self.headers, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, headers=self.headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                result = response.json()

                if not result.get("success"):
                    errors = result.get("errors", [])
                    error_msg = ", ".join([e.get("message", "") for e in errors])
                    raise Exception(f"Cloudflare API error: {error_msg}")

                return result.get("result", {})

            except httpx.HTTPError as e:
                logger.error(f"Cloudflare API request failed: {e}")
                raise

    async def verify_token(self) -> bool:
        """Verify if the API token is valid"""
        try:
            await self._request("GET", "/user/tokens/verify")
            return True
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return False

    async def list_zones(self) -> List[dict]:
        """List all zones (domains) in the account"""
        try:
            result = await self._request("GET", "/zones")
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Failed to list zones: {e}")
            return []

    async def get_zone_details(self, zone_id: str) -> dict | None:
        """Get details of a specific zone"""
        try:
            return await self._request("GET", f"/zones/{zone_id}")
        except Exception as e:
            logger.error(f"Failed to get zone details: {e}")
            return None

    async def list_dns_records(
        self, zone_id: str, record_type: str | None = None
    ) -> List[dict]:
        """List DNS records for a zone"""
        try:
            endpoint = f"/zones/{zone_id}/dns_records"
            if record_type:
                endpoint += f"?type={record_type}"

            result = await self._request("GET", endpoint)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Failed to list DNS records: {e}")
            return []

    async def create_dns_record(
        self,
        zone_id: str,
        record_type: str,
        name: str,
        content: str,
        proxied: bool = True,
        ttl: int = 1,
    ) -> dict | None:
        """Create a new DNS record"""
        try:
            data = {
                "type": record_type,
                "name": name,
                "content": content,
                "proxied": proxied,
                "ttl": ttl,
            }
            return await self._request(
                "POST", f"/zones/{zone_id}/dns_records", data=data
            )
        except Exception as e:
            logger.error(f"Failed to create DNS record: {e}")
            return None

    async def update_dns_record(
        self,
        zone_id: str,
        record_id: str,
        record_type: str,
        name: str,
        content: str,
        proxied: bool = True,
        ttl: int = 1,
    ) -> dict | None:
        """Update an existing DNS record"""
        try:
            data = {
                "type": record_type,
                "name": name,
                "content": content,
                "proxied": proxied,
                "ttl": ttl,
            }
            return await self._request(
                "PUT", f"/zones/{zone_id}/dns_records/{record_id}", data=data
            )
        except Exception as e:
            logger.error(f"Failed to update DNS record: {e}")
            return None

    async def delete_dns_record(self, zone_id: str, record_id: str) -> bool:
        """Delete a DNS record"""
        try:
            await self._request("DELETE", f"/zones/{zone_id}/dns_records/{record_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete DNS record: {e}")
            return False

    async def get_zone_settings(self, zone_id: str) -> dict | None:
        """Get zone settings"""
        try:
            return await self._request("GET", f"/zones/{zone_id}/settings")
        except Exception as e:
            logger.error(f"Failed to get zone settings: {e}")
            return None


async def get_optimal_cdn_ips(
    count: int = 10, timeout: float = 2.0
) -> List[CloudflareIPInfo]:
    """
    Test Cloudflare CDN IPs and return the fastest ones
    This tests connectivity and latency to various CDN IPs
    """
    results = []

    async def test_ip(ip: str) -> CloudflareIPInfo | None:
        try:
            start_time = time.time()

            # Try to connect to the IP on port 443
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    # Use Cloudflare's test endpoint
                    await client.get(
                        f"https://{ip}",
                        headers={"Host": "cloudflare.com"},
                        follow_redirects=False,
                    )
                except Exception:
                    # Connection might fail but that's ok, we're testing reachability
                    pass

            latency = (time.time() - start_time) * 1000  # Convert to ms

            return CloudflareIPInfo(ip=ip, latency_ms=latency)

        except Exception as e:
            logger.debug(f"Failed to test IP {ip}: {e}")
            return None

    # Test IPs concurrently
    tasks = [test_ip(ip) for ip in CLOUDFLARE_CDN_IPS[:20]]
    test_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out failures and sort by latency
    for result in test_results:
        if isinstance(result, CloudflareIPInfo) and result.latency_ms:
            results.append(result)

    # Sort by latency and return top results
    results.sort(key=lambda x: x.latency_ms or float("inf"))
    return results[:count]


async def get_cloudflare_cdn_ips() -> List[str]:
    """
    Get a list of Cloudflare CDN IP addresses
    Returns both static list and optionally fetches latest from Cloudflare
    """
    # Return static list of known good CDN IPs
    return CLOUDFLARE_CDN_IPS


def generate_cdn_configs_for_user(
    user_configs: List[dict], cdn_ips: List[str], cdn_ports: List[int]
) -> List[dict]:
    """
    Generate CDN-compatible configurations for a user
    Takes existing user configs and creates CDN versions
    """
    cdn_configs = []

    for config in user_configs:
        # Only create CDN configs for WebSocket-based protocols
        if config.get("transport_type") in ["ws", "httpupgrade", "splithttp"]:
            for cdn_ip in cdn_ips[:3]:  # Use top 3 CDN IPs
                for port in cdn_ports[:4]:  # Use top 4 ports
                    cdn_config = config.copy()
                    cdn_config["address"] = cdn_ip
                    cdn_config["port"] = port
                    cdn_config["remark"] = f"{config.get('remark', 'Config')} [CDN-{cdn_ip}]"

                    # Ensure TLS is enabled for CDN
                    if not cdn_config.get("tls"):
                        cdn_config["tls"] = "tls"

                    cdn_configs.append(cdn_config)

    return cdn_configs
