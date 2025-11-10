"""
Routing rules generator for Smart Proxy Mode
Generates routing configurations for different client types
"""

from typing import Dict, List

from app.models.proxy_mode import (
    ProxyMode,
    ProxyModeSettings,
    RoutingRule,
    RoutingAction,
    ClashRule,
    XrayRule,
    SingBoxRule,
)


def generate_clash_rules(proxy_mode: ProxyMode, settings: ProxyModeSettings) -> List[str]:
    """
    Generate Clash/ClashMeta routing rules
    Returns list of rule strings
    """
    rules = []

    # Add custom rules first
    for rule in settings.custom_rules:
        if rule.enabled:
            rules.append(ClashRule.from_routing_rule(rule))

    # Add ad/tracker blocking rules
    if settings.block_ads:
        rules.extend([
            "GEOSITE,category-ads-all,REJECT",
            "GEOSITE,category-ads-ir,REJECT",
        ])

    if settings.block_trackers:
        rules.extend([
            "GEOSITE,category-tracker-!cn,REJECT",
        ])

    # Add mode-specific rules
    if proxy_mode == ProxyMode.SMART:
        # Smart mode: Direct for Iran, Proxy for foreign
        for rule in settings.smart_mode_rules:
            if rule.enabled:
                rules.append(ClashRule.from_routing_rule(rule))

        # Default: PROXY for everything else
        rules.append("MATCH,PROXY")

    elif proxy_mode == ProxyMode.FILTERED:
        # Filtered mode: Proxy only for blocked sites
        for rule in settings.filtered_mode_rules:
            if rule.enabled:
                rules.append(ClashRule.from_routing_rule(rule))

        # Default: DIRECT for everything else
        rules.append("MATCH,DIRECT")

    elif proxy_mode == ProxyMode.FULL:
        # Full VPN mode: Everything through proxy
        rules.append("MATCH,PROXY")

    elif proxy_mode == ProxyMode.DIRECT:
        # Direct mode: No proxy
        rules.append("MATCH,DIRECT")

    return rules


def generate_xray_routing(proxy_mode: ProxyMode, settings: ProxyModeSettings) -> Dict:
    """
    Generate Xray routing configuration
    Returns Xray routing dict
    """
    routing_rules = []

    # Add custom rules first
    for rule in settings.custom_rules:
        if rule.enabled:
            routing_rules.append(XrayRule.from_routing_rule(rule))

    # Add ad/tracker blocking rules
    if settings.block_ads:
        routing_rules.append({
            "type": "field",
            "domain": ["geosite:category-ads-all", "geosite:category-ads-ir"],
            "outboundTag": "block"
        })

    if settings.block_trackers:
        routing_rules.append({
            "type": "field",
            "domain": ["geosite:category-tracker-!cn"],
            "outboundTag": "block"
        })

    # Add mode-specific rules
    if proxy_mode == ProxyMode.SMART:
        # Smart mode: Direct for Iran
        for rule in settings.smart_mode_rules:
            if rule.enabled:
                routing_rules.append(XrayRule.from_routing_rule(rule))

    elif proxy_mode == ProxyMode.FILTERED:
        # Filtered mode: Proxy only for blocked sites
        for rule in settings.filtered_mode_rules:
            if rule.enabled:
                routing_rules.append(XrayRule.from_routing_rule(rule))

        # Default: Direct for everything else (implicit in Xray)

    elif proxy_mode == ProxyMode.DIRECT:
        # All traffic direct
        routing_rules.append({
            "type": "field",
            "network": "tcp,udp",
            "outboundTag": "direct"
        })

    # Full VPN mode doesn't need special rules, proxy is default

    return {
        "domainStrategy": "IPIfNonMatch",
        "domainMatcher": "hybrid",
        "rules": routing_rules
    }


def generate_singbox_routing(proxy_mode: ProxyMode, settings: ProxyModeSettings) -> Dict:
    """
    Generate SingBox routing configuration
    Returns SingBox routing dict
    """
    routing_rules = []

    # Add custom rules first
    for rule in settings.custom_rules:
        if rule.enabled:
            routing_rules.append(SingBoxRule.from_routing_rule(rule))

    # Add ad/tracker blocking rules
    if settings.block_ads:
        routing_rules.append({
            "geosite": ["category-ads-all", "category-ads-ir"],
            "outbound": "block"
        })

    if settings.block_trackers:
        routing_rules.append({
            "geosite": ["category-tracker-!cn"],
            "outbound": "block"
        })

    # Add mode-specific rules
    if proxy_mode == ProxyMode.SMART:
        # Smart mode: Direct for Iran
        for rule in settings.smart_mode_rules:
            if rule.enabled:
                routing_rules.append(SingBoxRule.from_routing_rule(rule))

        # Default: proxy (handled by final rule)
        routing_rules.append({
            "outbound": "proxy"
        })

    elif proxy_mode == ProxyMode.FILTERED:
        # Filtered mode: Proxy only for blocked sites
        for rule in settings.filtered_mode_rules:
            if rule.enabled:
                routing_rules.append(SingBoxRule.from_routing_rule(rule))

        # Default: direct
        routing_rules.append({
            "outbound": "direct"
        })

    elif proxy_mode == ProxyMode.FULL:
        # Full VPN: Everything through proxy
        routing_rules.append({
            "outbound": "proxy"
        })

    elif proxy_mode == ProxyMode.DIRECT:
        # Direct mode: No proxy
        routing_rules.append({
            "outbound": "direct"
        })

    return {
        "rules": routing_rules,
        "final": "proxy" if proxy_mode in [ProxyMode.FULL, ProxyMode.SMART] else "direct"
    }


def get_default_proxy_mode_settings() -> ProxyModeSettings:
    """Get default proxy mode settings"""
    return ProxyModeSettings()


def enhance_subscription_with_routing(
    subscription_config: dict,
    proxy_mode: ProxyMode,
    settings: ProxyModeSettings,
    config_format: str
) -> dict:
    """
    Enhance subscription configuration with routing rules
    based on proxy mode and client type
    """
    if config_format in ["clash", "clash-meta"]:
        # Add Clash rules
        if "rules" not in subscription_config:
            subscription_config["rules"] = []

        clash_rules = generate_clash_rules(proxy_mode, settings)
        subscription_config["rules"] = clash_rules

    elif config_format == "xray":
        # Add Xray routing
        routing = generate_xray_routing(proxy_mode, settings)
        subscription_config["routing"] = routing

        # Ensure outbounds exist
        if "outbounds" not in subscription_config:
            subscription_config["outbounds"] = []

        # Add direct and block outbounds if not present
        outbound_tags = [o.get("tag") for o in subscription_config["outbounds"]]

        if "direct" not in outbound_tags:
            subscription_config["outbounds"].append({
                "protocol": "freedom",
                "tag": "direct"
            })

        if "block" not in outbound_tags:
            subscription_config["outbounds"].append({
                "protocol": "blackhole",
                "tag": "block"
            })

    elif config_format == "sing-box":
        # Add SingBox routing
        routing = generate_singbox_routing(proxy_mode, settings)
        subscription_config["route"] = routing

        # Ensure outbounds exist
        if "outbounds" not in subscription_config:
            subscription_config["outbounds"] = []

        # Add direct and block outbounds if not present
        outbound_tags = [o.get("tag") for o in subscription_config["outbounds"]]

        if "direct" not in outbound_tags:
            subscription_config["outbounds"].append({
                "type": "direct",
                "tag": "direct"
            })

        if "block" not in outbound_tags:
            subscription_config["outbounds"].append({
                "type": "block",
                "tag": "block"
            })

    return subscription_config
