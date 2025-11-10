from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ProxyMode(StrEnum):
    """Proxy routing modes"""
    FULL = "full"  # All traffic through proxy
    SMART = "smart"  # Only foreign/blocked sites through proxy
    FILTERED = "filtered"  # Only explicitly filtered sites through proxy
    DIRECT = "direct"  # No proxy, direct connection only


class RoutingRuleType(StrEnum):
    """Types of routing rules"""
    DOMAIN = "domain"
    DOMAIN_SUFFIX = "domain-suffix"
    DOMAIN_KEYWORD = "domain-keyword"
    GEOIP = "geoip"
    GEOSITE = "geosite"
    IP_CIDR = "ip-cidr"
    PROCESS = "process"


class RoutingAction(StrEnum):
    """Actions for routing rules"""
    PROXY = "proxy"
    DIRECT = "direct"
    BLOCK = "block"


class RoutingRule(BaseModel):
    """A single routing rule"""
    type: RoutingRuleType
    pattern: str  # e.g., "google.com", "ir", "geosite:category-ads-all"
    action: RoutingAction
    enabled: bool = True


class ProxyModeSettings(BaseModel):
    """Smart proxy mode configuration"""
    enabled: bool = True
    default_mode: ProxyMode = ProxyMode.FULL

    # Predefined rule sets for different modes
    smart_mode_rules: list[RoutingRule] = Field(
        default=[
            # Direct for Iran
            RoutingRule(
                type=RoutingRuleType.GEOIP,
                pattern="ir",
                action=RoutingAction.DIRECT,
            ),
            # Direct for private IPs
            RoutingRule(
                type=RoutingRuleType.GEOIP,
                pattern="private",
                action=RoutingAction.DIRECT,
            ),
            # Direct for .ir domains
            RoutingRule(
                type=RoutingRuleType.DOMAIN_SUFFIX,
                pattern=".ir",
                action=RoutingAction.DIRECT,
            ),
            # Proxy everything else
        ]
    )

    filtered_mode_rules: list[RoutingRule] = Field(
        default=[
            # Popular blocked sites
            RoutingRule(
                type=RoutingRuleType.GEOSITE,
                pattern="google",
                action=RoutingAction.PROXY,
            ),
            RoutingRule(
                type=RoutingRuleType.GEOSITE,
                pattern="youtube",
                action=RoutingAction.PROXY,
            ),
            RoutingRule(
                type=RoutingRuleType.GEOSITE,
                pattern="telegram",
                action=RoutingAction.PROXY,
            ),
            RoutingRule(
                type=RoutingRuleType.GEOSITE,
                pattern="twitter",
                action=RoutingAction.PROXY,
            ),
            RoutingRule(
                type=RoutingRuleType.GEOSITE,
                pattern="facebook",
                action=RoutingAction.PROXY,
            ),
            RoutingRule(
                type=RoutingRuleType.GEOSITE,
                pattern="instagram",
                action=RoutingAction.PROXY,
            ),
            # Direct everything else
        ]
    )

    # Custom rules that apply to all modes
    custom_rules: list[RoutingRule] = []

    # Block ads and tracking
    block_ads: bool = True
    block_trackers: bool = False


class UserProxyMode(BaseModel):
    """User-specific proxy mode configuration"""
    user_id: int
    proxy_mode: ProxyMode = ProxyMode.FULL
    custom_rules: list[RoutingRule] = []
    include_in_subscription: bool = True


# Clash/ClashMeta rule types
class ClashRule(BaseModel):
    """Clash-format routing rule"""
    rule: str  # e.g., "GEOIP,IR,DIRECT"

    @classmethod
    def from_routing_rule(cls, rule: RoutingRule, default_action: str = "MATCH") -> str:
        """Convert RoutingRule to Clash rule format"""
        if rule.type == RoutingRuleType.GEOIP:
            return f"GEOIP,{rule.pattern.upper()},{rule.action.upper()}"
        elif rule.type == RoutingRuleType.GEOSITE:
            return f"GEOSITE,{rule.pattern},{rule.action.upper()}"
        elif rule.type == RoutingRuleType.DOMAIN:
            return f"DOMAIN,{rule.pattern},{rule.action.upper()}"
        elif rule.type == RoutingRuleType.DOMAIN_SUFFIX:
            return f"DOMAIN-SUFFIX,{rule.pattern},{rule.action.upper()}"
        elif rule.type == RoutingRuleType.DOMAIN_KEYWORD:
            return f"DOMAIN-KEYWORD,{rule.pattern},{rule.action.upper()}"
        elif rule.type == RoutingRuleType.IP_CIDR:
            return f"IP-CIDR,{rule.pattern},{rule.action.upper()}"
        elif rule.type == RoutingRuleType.PROCESS:
            return f"PROCESS-NAME,{rule.pattern},{rule.action.upper()}"
        else:
            return f"MATCH,{default_action}"


# Xray/V2Ray rule types
class XrayRule(BaseModel):
    """Xray-format routing rule"""

    @classmethod
    def from_routing_rule(cls, rule: RoutingRule) -> dict:
        """Convert RoutingRule to Xray routing rule format"""
        xray_rule = {
            "type": "field",
            "outboundTag": rule.action.value if rule.action != RoutingAction.BLOCK else "block",
        }

        if rule.type == RoutingRuleType.DOMAIN:
            xray_rule["domain"] = [rule.pattern]
        elif rule.type == RoutingRuleType.DOMAIN_SUFFIX:
            xray_rule["domain"] = [f"full:{rule.pattern}"]
        elif rule.type == RoutingRuleType.DOMAIN_KEYWORD:
            xray_rule["domain"] = [f"keyword:{rule.pattern}"]
        elif rule.type == RoutingRuleType.GEOSITE:
            xray_rule["domain"] = [f"geosite:{rule.pattern}"]
        elif rule.type == RoutingRuleType.GEOIP:
            xray_rule["ip"] = [f"geoip:{rule.pattern}"]
        elif rule.type == RoutingRuleType.IP_CIDR:
            xray_rule["ip"] = [rule.pattern]

        return xray_rule


# SingBox rule types
class SingBoxRule(BaseModel):
    """SingBox-format routing rule"""

    @classmethod
    def from_routing_rule(cls, rule: RoutingRule) -> dict:
        """Convert RoutingRule to SingBox routing rule format"""
        singbox_rule = {
            "outbound": rule.action.value if rule.action != RoutingAction.BLOCK else "block",
        }

        if rule.type == RoutingRuleType.DOMAIN:
            singbox_rule["domain"] = [rule.pattern]
        elif rule.type == RoutingRuleType.DOMAIN_SUFFIX:
            singbox_rule["domain_suffix"] = [rule.pattern]
        elif rule.type == RoutingRuleType.DOMAIN_KEYWORD:
            singbox_rule["domain_keyword"] = [rule.pattern]
        elif rule.type == RoutingRuleType.GEOSITE:
            singbox_rule["geosite"] = [rule.pattern]
        elif rule.type == RoutingRuleType.GEOIP:
            singbox_rule["geoip"] = [rule.pattern]
        elif rule.type == RoutingRuleType.IP_CIDR:
            singbox_rule["ip_cidr"] = [rule.pattern]

        return singbox_rule
