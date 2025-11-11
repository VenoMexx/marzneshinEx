import base64
import copy
import ipaddress
import json
import random
import secrets
import logging
from collections import defaultdict
from datetime import datetime as dt, timedelta
from importlib import resources
from typing import Literal, Union, List, Type
from uuid import UUID

import yaml
from jdatetime import date as jd
from v2share import (
    V2Data,
    SingBoxConfig,
    ClashConfig,
    ClashMetaConfig,
    XrayConfig,
    WireGuardConfig,
)
from v2share.base import BaseConfig
from v2share.data import MuxCoolSettings as V2MuxCoolSettings
from v2share.data import MuxSettings as V2MuxSettings
from v2share.data import SingBoxMuxSettings as V2SingBoxMuxSettings
from v2share.data import SplitHttpSettings as V2SplitHttpSettings
from v2share.data import XMuxSettings as V2XMuxSettings
from v2share.data import XrayNoise
from v2share.links import LinksConfig

from app.config.env import (
    XRAY_SUBSCRIPTION_TEMPLATE,
    SINGBOX_SUBSCRIPTION_TEMPLATE,
    CLASH_SUBSCRIPTION_TEMPLATE,
    SUBSCRIPTION_PAGE_TEMPLATE,
)
from app.db import GetDB
from app.db.crud import get_hosts_for_user
from app.models.proxy import (
    InboundHostSecurity,
    SplitHttpSettings,
    MuxSettings,
)
from app.models.settings import SubscriptionSettings
from app.models.user import UserResponse, UserExpireStrategy
from app.templates import render_template
from app.utils.keygen import gen_uuid, gen_password, generate_curve25519_pbk
from app.utils.system import get_public_ip, readable_size

SERVER_IP = get_public_ip()

ACTIVITY_EMOJIS = {
    True: "✅",
    False: "❌",
}

subscription_handlers: dict[str, Type[BaseConfig]] = {
    "links": LinksConfig,
    "xray": XrayConfig,
    "clash-meta": ClashMetaConfig,
    "clash": ClashConfig,
    "sing-box": SingBoxConfig,
    "wireguard": WireGuardConfig,
}

handlers_templates = {
    LinksConfig: None,
    WireGuardConfig: None,
    XrayConfig: XRAY_SUBSCRIPTION_TEMPLATE
    or resources.files("app.templates") / "xray.json",
    ClashConfig: CLASH_SUBSCRIPTION_TEMPLATE,
    ClashMetaConfig: CLASH_SUBSCRIPTION_TEMPLATE,
    SingBoxConfig: SINGBOX_SUBSCRIPTION_TEMPLATE
    or resources.files("app.templates") / "sing-box.json",
}


def generate_subscription_template(
    db_user, subscription_settings: SubscriptionSettings
):
    links = generate_subscription(
        user=db_user,
        config_format="links",
        use_placeholder=not db_user.is_active
        and subscription_settings.placeholder_if_disabled,
        placeholder_remark=subscription_settings.placeholder_remark,
        shuffle=subscription_settings.shuffle_configs,
    ).split()
    return render_template(
        SUBSCRIPTION_PAGE_TEMPLATE,
        {"user": UserResponse.model_validate(db_user), "links": links},
    )


def generate_subscription(
    user: "UserResponse",
    config_format: Literal["links", "xray", "clash-meta", "clash", "sing-box"],
    as_base64: bool = False,
    use_placeholder: bool = False,
    placeholder_remark: str = "disabled",
    shuffle: bool = False,
    include_cdn_configs: bool = False,
    apply_routing_rules: bool = False,
) -> str:
    extra_data = UserResponse.model_validate(user).model_dump(
        exclude={"subscription_url", "services", "inbounds"}
    )
    format_variables = setup_format_variables(extra_data)

    if config_format not in subscription_handlers.keys():
        raise ValueError(f'Unsupported format "{config_format}"')

    subscription_handler_class = subscription_handlers[config_format]
    if template_path := handlers_templates[subscription_handler_class]:
        subscription_handler = subscription_handler_class(
            template_path=template_path
        )
    else:
        subscription_handler = subscription_handler_class()

    if use_placeholder:
        placeholder_config = V2Data(
            "vmess",
            placeholder_remark.format_map(format_variables),
            "127.0.0.1",
            80,
        )
        configs = [placeholder_config]

    else:
        configs = generate_user_configs(
            user.inbounds,
            user.key,
            user.id,
            format_variables,
            chaining_support=subscription_handler.chaining_support,
        )

        # Add CDN configs if enabled
        if include_cdn_configs:
            cdn_configs = generate_cdn_configs(configs, user.id)
            configs.extend(cdn_configs)

    subscription_handler.add_proxies(configs)
    config = subscription_handler.render(sort=True, shuffle=shuffle)

    # Apply smart proxy routing rules if enabled
    if apply_routing_rules and config_format in ["clash", "clash-meta", "xray", "sing-box"]:
        config = apply_smart_proxy_routing(config, config_format)

    return (
        config if not as_base64 else base64.b64encode(config.encode()).decode()
    )


def format_time_left(seconds_left: int) -> str:
    if not seconds_left or seconds_left <= 0:
        return "∞"

    minutes, seconds = divmod(seconds_left, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    months, days = divmod(days, 30)

    result = []
    if months:
        result.append(f"{months}m")
    if days:
        result.append(f"{days}d")
    if hours and (days < 7):
        result.append(f"{hours}h")
    if minutes and not (months or days):
        result.append(f"{minutes}m")
    if seconds and not (months or days):
        result.append(f"{seconds}s")
    return " ".join(result)


def calculate_client_address(interface_address: str, user_id: int) -> str:
    try:
        interface = ipaddress.ip_interface(interface_address)
        address = interface.ip
        network = interface.network
    except ValueError:
        return ""
    user_address = network[user_id]
    if user_address == network[0]:
        user_address = network.broadcast_address - 1
    if user_address == address:
        user_address = network.broadcast_address - 2
    return user_address.compressed + "/" + str(user_address.max_prefixlen)


def setup_format_variables(extra_data: dict) -> dict:
    expire_strategy = extra_data.get("expire_strategy")
    expire_datetime = extra_data.get("expire_date")
    usage_duration = extra_data.get("usage_duration")

    if expire_strategy != UserExpireStrategy.START_ON_FIRST_USE:
        if expire_datetime is not None:
            seconds_left = (expire_datetime - dt.utcnow()).total_seconds()
            expire_date = expire_datetime.date()
            jalali_expire_date = jd.fromgregorian(
                year=expire_date.year,
                month=expire_date.month,
                day=expire_date.day,
            ).strftime("%Y-%m-%d")
            days_left = (expire_datetime - dt.utcnow()).days + 1
            time_left = format_time_left(seconds_left)
        else:
            days_left, time_left, expire_date, jalali_expire_date = "∞" * 4
    else:
        if usage_duration is not None and usage_duration >= 0:
            days_left = timedelta(seconds=usage_duration).days
            time_left = format_time_left(usage_duration)
            expire_date = "-"
            jalali_expire_date = "-"
        else:
            days_left, time_left, expire_date, jalali_expire_date = "∞" * 4

    if extra_data.get("data_limit"):
        data_limit = readable_size(extra_data["data_limit"])
        data_left = extra_data["data_limit"] - extra_data["used_traffic"]
        if data_left < 0:
            data_left = 0
        data_left = readable_size(data_left)
    else:
        data_limit, data_left = "∞" * 2

    status_emoji = ACTIVITY_EMOJIS.get(extra_data.get("is_active")) or ""

    format_variables = defaultdict(
        lambda: "<missing>",
        {
            "SERVER_IP": SERVER_IP,
            "USERNAME": extra_data.get("username", "{USERNAME}"),
            "DATA_USAGE": readable_size(extra_data.get("used_traffic")),
            "DATA_LIMIT": data_limit,
            "DATA_LEFT": data_left,
            "DAYS_LEFT": days_left,
            "EXPIRE_DATE": expire_date,
            "JALALI_EXPIRE_DATE": jalali_expire_date,
            "TIME_LEFT": time_left,
            "STATUS_EMOJI": status_emoji,
        },
    )

    return format_variables


# DoH settings cache (5 minute TTL)
_doh_cache = {
    "data": None,
    "expires_at": dt.min,
    "last_error": None
}
DOH_CACHE_TTL_MINUTES = 5
logger = logging.getLogger(__name__)


def get_doh_dns_servers() -> tuple[list[str], list[str]]:
    """
    Get DNS over HTTPS servers from settings with caching.

    Cache TTL: 5 minutes
    Returns cached result if available and not expired.

    Returns:
        Tuple of (doh_servers, fallback_dns)
    """
    from app.db import GetDB
    from app.db.models import Settings
    from app.models.settings import DoHSettings

    now = dt.now()

    # Return cached data if valid
    if _doh_cache["data"] and _doh_cache["expires_at"] > now:
        return _doh_cache["data"]

    try:
        with GetDB() as db:
            settings_row = db.query(Settings.doh).first()
            if not settings_row or not settings_row[0]:
                result = ([], [])
            else:
                doh_settings = DoHSettings.model_validate(settings_row[0])
                if not doh_settings.enabled:
                    result = ([], [])
                else:
                    result = (doh_settings.servers, doh_settings.fallback_dns)

        # Cache successful result
        _doh_cache["data"] = result
        _doh_cache["expires_at"] = now + timedelta(minutes=DOH_CACHE_TTL_MINUTES)
        _doh_cache["last_error"] = None
        return result

    except Exception as e:
        logger.error(f"Failed to fetch DoH settings: {e}")

        # Return last successful cache if available (stale cache fallback)
        if _doh_cache["data"]:
            logger.warning("Using stale DoH cache due to database error")
            return _doh_cache["data"]

        # No cache available, return empty
        _doh_cache["last_error"] = str(e)
        return ([], [])


def _get_effective_dns_servers(host) -> list[str]:
    """
    Determine which DNS servers to use for a host.

    Priority:
    1. Host-specific DNS servers (if configured)
    2. DoH servers (if enabled in settings)
    3. DoH fallback DNS (if DoH enabled but servers empty)
    4. Empty list (use client default)

    Args:
        host: InboundHost object

    Returns:
        List of DNS server addresses (IP or DoH URL)
    """
    # Check if host has specific DNS servers configured
    if host.dns_servers:
        return host.dns_servers.split(",")

    # Try to get DoH settings
    doh_servers, fallback_dns = get_doh_dns_servers()

    # If DoH is enabled and has servers, use them
    if doh_servers:
        # Combine DoH servers with fallback DNS for redundancy
        return doh_servers + fallback_dns

    # If DoH enabled but no servers, use fallback DNS only
    if fallback_dns:
        return fallback_dns

    # No DNS configured, return empty list (client will use defaults)
    return []


def generate_user_configs(
    inbounds: list,
    key: str,
    user_id: int,
    format_variables: dict,
    chaining_support: bool,
) -> Union[List, str]:
    salt = secrets.token_hex(8)
    configs = []

    with GetDB() as db:
        hosts = get_hosts_for_user(db, user_id)

    for host in hosts:
        chained_hosts = [c.chained_host for c in host.chain]
        if chained_hosts and not chaining_support:
            continue

        # Check if separate upload/download domains are configured
        if host.upload_host and host.download_host:
            # Generate upload-optimized config
            upload_host = _create_host_variant(host, host.upload_host, " (Upload)")
            upload_data = create_config(
                upload_host, key, format_variables, salt, user_id, chained_hosts
            )
            configs.append(upload_data)

            # Generate download-optimized config
            download_host = _create_host_variant(host, host.download_host, " (Download)")
            download_data = create_config(
                download_host, key, format_variables, salt, user_id, chained_hosts
            )
            configs.append(download_data)
        else:
            # Standard config generation
            data = create_config(
                host, key, format_variables, salt, user_id, chained_hosts
            )
            configs.append(data)

    return configs


def _create_host_variant(original_host, host_value: str, remark_suffix: str):
    """
    Create a temporary host variant with modified host and remark.
    Used for generating separate upload/download configs.
    Uses deep copy to prevent memory leaks from shared references.
    """
    # Deep copy to avoid memory leaks from shared nested objects
    variant = copy.deepcopy(original_host)
    variant.host = host_value
    variant.remark = original_host.remark + remark_suffix
    return variant


def create_config(
    host, key, format_variables, salt, user_id, next_hosts: list | None = None
):
    if next_hosts is None:
        next_hosts = []

    if host.inbound:
        inbound, protocol = (
            json.loads(host.inbound.config),
            host.inbound.protocol,
        )
        network = inbound.get("network")
        auth_uuid, auth_password = UUID(gen_uuid(key)), gen_password(key)
    else:
        inbound, protocol, network = {}, host.host_protocol, host.host_network
        auth_uuid, auth_password = (
            UUID(host.uuid) if host.uuid else None
        ), host.password

    # Extract node-specific information for template variables
    if host.inbound and host.inbound.node:
        node_address = host.inbound.node.address or SERVER_IP
        node_name = host.inbound.node.name or "Unknown"
    else:
        node_address = SERVER_IP  # Fallback to master IP
        node_name = "Master"

    format_variables.update(
        {
            "PROTOCOL": (
                host.inbound.protocol.value
                if host.inbound
                else host.host_protocol
            )
        }
    )
    format_variables.update({"TRANSPORT": network or "<missing>"})

    # Add node-specific template variables for multi-node deployments
    format_variables.update({
        "NODE_ADDRESS": node_address,  # Node-specific IP (e.g., de1.example.com, de2.example.com)
        "NODE_NAME": node_name,        # Node name (e.g., DE1, DE2, FI1)
    })

    host_snis = host.sni.split(",") if host.sni else []
    sni_list = host_snis or inbound.get("sni", [])
    if sni_list:
        sni = random.choice(sni_list).replace("*", salt)
    else:
        sni = ""

    host_hosts = host.host.split(",") if host.host else []
    req_host_list = host_hosts or inbound.get("host", [])
    if req_host_list:
        req_host = random.choice(req_host_list).replace("*", salt)
    else:
        req_host = ""

    host_tls = (
        None
        if host.security == InboundHostSecurity.inbound_default
        else host.security.value
    )
    splithttp_settings = (
        SplitHttpSettings.model_validate(host.splithttp_settings)
        if host.splithttp_settings
        else None
    )
    mux_settings = (
        MuxSettings.model_validate(host.mux_settings)
        if host.mux_settings
        else None
    )

    data = V2Data(
        host.inbound.protocol.value if host.inbound else host.host_protocol,
        host.remark.format_map(format_variables),
        host.address.format_map(format_variables),
        host.port or inbound.get("port", 0),
        transport_type=network,
        sni=sni,
        host=req_host,
        tls=host_tls or inbound.get("tls"),
        header_type=host.header_type or inbound.get("header_type"),
        alpn=host.alpn if host.alpn != "none" else None,
        path=(
            host.path.format_map(format_variables)
            if host.path
            else inbound.get("path")
        ),
        fingerprint=host.fingerprint.value or inbound.get("fp"),
        reality_pbk=inbound.get("pbk"),
        reality_sid=inbound.get("sid"),
        client_address=calculate_client_address(
            inbound.get("address"), user_id
        ),
        flow=host.flow or inbound.get("flow"),
        dns_servers=_get_effective_dns_servers(host),
        mtu=host.mtu,
        allowed_ips=(
            list(map(str.strip, host.allowed_ips.split(",")))
            if host.allowed_ips
            else None
        ),
        allow_insecure=host.allowinsecure,
        uuid=auth_uuid,
        password=auth_password,
        ed25519=generate_curve25519_pbk(key),
        early_data=host.early_data,
        splithttp_settings=(
            V2SplitHttpSettings(
                mode=splithttp_settings.mode,
                no_grpc_header=splithttp_settings.no_grpc_header,
                padding_bytes=splithttp_settings.padding_bytes,
                xmux=(
                    V2XMuxSettings(**splithttp_settings.xmux.model_dump())
                    if splithttp_settings.xmux
                    else None
                ),
            )
            if splithttp_settings
            else None
        ),
        mux_settings=(
            V2MuxSettings(
                protocol=mux_settings.protocol,
                sing_box_mux_settings=(
                    V2SingBoxMuxSettings(
                        **mux_settings.sing_box_mux_settings.model_dump()
                    )
                    if mux_settings.sing_box_mux_settings
                    else None
                ),
                mux_cool_settings=(
                    V2MuxCoolSettings(
                        **mux_settings.mux_cool_settings.model_dump()
                    )
                    if mux_settings.mux_cool_settings
                    else None
                ),
            )
            if mux_settings
            else None
        ),
        http_headers=host.http_headers,
        shadowsocks_method=host.shadowsocks_method or "chacha20-ietf-poly1305",
        shadowtls_version=host.shadowtls_version
        or inbound.get("shadowtls_version"),
        weight=host.weight,
        xray_noises=(
            [XrayNoise(**noise) for noise in host.udp_noises]
            if host.udp_noises
            else None
        ),
        next=(
            create_config(
                next_hosts[0],
                key,
                format_variables,
                salt,
                user_id,
                next_hosts[1:],
            )
            if next_hosts
            else None
        ),
    )
    if host.fragment:
        data.fragment = True
        data.fragment_packets = host.fragment["packets"]
        data.fragment_length = host.fragment["length"]
        data.fragment_interval = host.fragment["interval"]

    return data


def encode_title(text: str) -> str:
    return f"base64:{base64.b64encode(text.encode()).decode()}"


def apply_smart_proxy_routing(config: str, config_format: str) -> str:
    """
    Apply smart proxy routing rules to subscription config
    """
    try:
        from app.db import GetDB
        from app.db.models import Settings
        from app.models.settings import SubscriptionSettings
        from app.models.proxy_mode import ProxyModeSettings
        from app.utils.routing import generate_clash_rules, generate_xray_routing, generate_singbox_routing
        import yaml

        # Get settings from database
        with GetDB() as db:
            settings_row = db.query(Settings.subscription, Settings.proxy_mode).first()
            if not settings_row:
                return config

            sub_settings = SubscriptionSettings.model_validate(settings_row[0])
            proxy_mode_settings_data = settings_row[1]

            # Check if proxy mode is enabled
            if not sub_settings.proxy_mode_enabled:
                return config

            # Get proxy mode settings
            if not proxy_mode_settings_data:
                proxy_mode_settings = ProxyModeSettings()
            else:
                proxy_mode_settings = ProxyModeSettings.model_validate(proxy_mode_settings_data)

        proxy_mode = sub_settings.default_proxy_mode

        # Apply routing based on format
        if config_format in ["clash", "clash-meta"]:
            # Parse YAML
            config_dict = yaml.safe_load(config)

            # Add routing rules
            clash_rules = generate_clash_rules(proxy_mode, proxy_mode_settings)
            config_dict["rules"] = clash_rules

            # Convert back to YAML
            return yaml.dump(config_dict, allow_unicode=True, default_flow_style=False)

        elif config_format == "xray":
            # Parse JSON
            config_dict = json.loads(config)

            # Add routing
            routing = generate_xray_routing(proxy_mode, proxy_mode_settings)
            config_dict["routing"] = routing

            # Add direct and block outbounds if needed
            if "outbounds" not in config_dict:
                config_dict["outbounds"] = []

            outbound_tags = [o.get("tag") for o in config_dict["outbounds"]]
            if "direct" not in outbound_tags:
                config_dict["outbounds"].append({
                    "protocol": "freedom",
                    "tag": "direct"
                })
            if "block" not in outbound_tags:
                config_dict["outbounds"].append({
                    "protocol": "blackhole",
                    "tag": "block"
                })

            # Convert back to JSON
            return json.dumps(config_dict, indent=2)

        elif config_format == "sing-box":
            # Parse JSON
            config_dict = json.loads(config)

            # Add routing
            routing = generate_singbox_routing(proxy_mode, proxy_mode_settings)
            config_dict["route"] = routing

            # Add direct and block outbounds if needed
            if "outbounds" not in config_dict:
                config_dict["outbounds"] = []

            outbound_tags = [o.get("tag") for o in config_dict["outbounds"]]
            if "direct" not in outbound_tags:
                config_dict["outbounds"].append({
                    "type": "direct",
                    "tag": "direct"
                })
            if "block" not in outbound_tags:
                config_dict["outbounds"].append({
                    "type": "block",
                    "tag": "block"
                })

            # Convert back to JSON
            return json.dumps(config_dict, indent=2)

    except Exception as e:
        # Log error but don't fail subscription generation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to apply smart proxy routing: {e}")
        return config

    return config


def generate_cdn_configs(original_configs: list, user_id: int) -> list:
    """
    Generate CDN-optimized configurations from original configs
    Only generates CDN configs for WebSocket-based protocols
    """
    from app.db import GetDB
    from app.db.models import Settings
    from app.models.settings import CloudflareSettings

    cdn_configs = []

    try:
        # Get Cloudflare settings from database
        with GetDB() as db:
            settings_row = db.query(Settings.cloudflare).first()
            if not settings_row or not settings_row[0]:
                return cdn_configs

            cf_settings = CloudflareSettings.model_validate(settings_row[0])

        # Check if CDN is enabled
        if not cf_settings.enabled or not cf_settings.auto_cdn_ip:
            return cdn_configs

        # Get CDN IPs
        cdn_ips = cf_settings.preferred_ips[:5] if cf_settings.preferred_ips else []
        cdn_ports = cf_settings.cdn_ports[:6]  # Use first 6 CDN-compatible ports

        if not cdn_ips:
            # Use default Cloudflare CDN IPs if no preferred IPs configured
            cdn_ips = [
                "104.16.0.0",
                "104.17.0.0",
                "172.67.0.0",
            ]

        # Generate CDN configs for WebSocket-based protocols
        for config in original_configs:
            transport_type = getattr(config, "transport_type", None)

            # Only create CDN configs for WebSocket-based transports
            if transport_type in ["ws", "httpupgrade", "splithttp"]:
                for cdn_ip in cdn_ips[:2]:  # Use top 2 CDN IPs
                    for port in cdn_ports[:3]:  # Use top 3 ports
                        # Create a copy of the config
                        cdn_config = V2Data(
                            config.protocol,
                            f"{config.remark} [CDN]",
                            cdn_ip,
                            port,
                            transport_type=transport_type,
                            sni=config.sni,
                            host=config.host,
                            tls=config.tls or "tls",  # Ensure TLS for CDN
                            header_type=config.header_type,
                            alpn=config.alpn,
                            path=config.path,
                            fingerprint=config.fingerprint,
                            uuid=config.uuid,
                            password=config.password,
                            flow=config.flow,
                            allow_insecure=config.allow_insecure,
                        )

                        cdn_configs.append(cdn_config)

    except Exception as e:
        # Log error but don't fail subscription generation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to generate CDN configs: {e}")

    return cdn_configs
