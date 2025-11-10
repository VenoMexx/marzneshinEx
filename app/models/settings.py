from datetime import datetime
from enum import StrEnum
from typing import Pattern, Literal

from pydantic import BaseModel, Field

from app.models.proxy_mode import ProxyMode, ProxyModeSettings


class ConfigTypes(StrEnum):
    links = "links"
    base64_links = "base64-links"
    xray = "xray"
    sing_box = "sing-box"
    clash = "clash"
    clash_meta = "clash-meta"
    template = "template"
    block = "block"


class SubscriptionRule(BaseModel):
    pattern: Pattern
    result: ConfigTypes


class SubscriptionSettings(BaseModel):
    template_on_acceptance: bool
    profile_title: str
    support_link: str
    update_interval: int
    shuffle_configs: bool = False
    placeholder_if_disabled: bool = True
    placeholder_remark: str = "disabled"
    rules: list[SubscriptionRule]
    proxy_mode_enabled: bool = False  # Enable smart proxy mode
    default_proxy_mode: ProxyMode = ProxyMode.FULL  # Default mode for subscriptions


class TelegramSettings(BaseModel):
    token: str
    admin_id: list[int]
    channel_id: int | None


class RemoteBackupSettings(BaseModel):
    provider: Literal["s3", "ftp", "sftp"] = "s3"
    endpoint: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    bucket: str | None = None
    path: str = "marzneshin-backups"


class BackupSettings(BaseModel):
    enabled: bool = True
    interval_hours: int = Field(default=6, ge=1, le=168)  # 1 hour to 1 week
    retention_days: int = Field(default=7, ge=1, le=90)
    backup_location: str = "/var/lib/marzneshin/backups"
    include_database: bool = True
    include_logs: bool = False
    remote_backup: RemoteBackupSettings | None = None


class BackupInfo(BaseModel):
    filename: str
    created_at: datetime
    size_bytes: int
    location: str
    is_remote: bool = False


class DoHSettings(BaseModel):
    """DNS over HTTPS (DoH) configuration"""
    enabled: bool = False
    servers: list[str] = Field(
        default_factory=lambda: [
            "https://cloudflare-dns.com/dns-query",  # Cloudflare DoH
            "https://dns.google/dns-query",           # Google DoH
        ],
        description="List of DoH server URLs (HTTPS DNS endpoints)"
    )
    fallback_dns: list[str] = Field(
        default_factory=lambda: ["1.1.1.1", "8.8.8.8"],
        description="Fallback DNS servers if DoH fails"
    )
    use_cdn_doh: bool = True  # Use CDN-optimized DoH when Cloudflare is enabled
    custom_hosts: dict[str, str] = Field(
        default_factory=dict,
        description="Custom DNS mappings (domain -> IP)"
    )


class CloudflareDomain(BaseModel):
    domain: str
    zone_id: str
    enabled: bool = True


class CloudflareSettings(BaseModel):
    enabled: bool = False
    api_token: str | None = None
    email: str | None = None
    default_zone_id: str | None = None
    domains: list[CloudflareDomain] = []
    auto_cdn_ip: bool = True
    cdn_ports: list[int] = Field(
        default=[80, 443, 8080, 8443, 2052, 2053, 2082, 2083, 2086, 2087, 2095, 2096]
    )
    preferred_ips: list[str] = []  # User can manually add preferred CDN IPs


class CloudflareIPInfo(BaseModel):
    ip: str
    latency_ms: float | None = None
    location: str | None = None


class Settings(BaseModel):
    subscription: SubscriptionSettings
    telegram: TelegramSettings | None
    backup: BackupSettings = Field(default_factory=BackupSettings)
    cloudflare: CloudflareSettings = Field(default_factory=CloudflareSettings)
    proxy_mode: ProxyModeSettings = Field(default_factory=ProxyModeSettings)
    doh: DoHSettings = Field(default_factory=DoHSettings)
