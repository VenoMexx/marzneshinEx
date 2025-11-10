from enum import StrEnum
from pydantic import BaseModel, Field


class WarpRoutingMode(StrEnum):
    """WARP routing modes"""
    ALL = "all"  # Route all traffic through WARP
    GEOIP = "geoip"  # Route based on GeoIP rules
    CUSTOM = "custom"  # Custom routing rules


class WarpSettings(BaseModel):
    """WARP configuration for a node"""
    enabled: bool = False
    license_key: str | None = Field(default=None, description="WARP+ license key (optional)")
    routing_mode: WarpRoutingMode = WarpRoutingMode.GEOIP
    routing_rules: list[str] = Field(
        default_factory=lambda: ["openai.com", "netflix.com", "spotify.com"],
        description="Domains/IPs to route through WARP"
    )
    # GeoIP/GeoSite rules for routing
    geoip_rules: list[str] = Field(
        default_factory=lambda: ["geosite:openai", "geosite:netflix"],
        description="GeoIP/GeoSite rules to route through WARP"
    )
