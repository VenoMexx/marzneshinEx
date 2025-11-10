"""
Security Management Models

Models for IP blacklist and fail2ban management
"""

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
import ipaddress


class IPBanRequest(BaseModel):
    """Request to ban an IP address"""
    ip_address: str = Field(..., description="IP address to ban (IPv4 or IPv6)")
    reason: str | None = Field(None, max_length=256, description="Reason for ban")
    expires_at: datetime | None = Field(None, description="Ban expiration (null = permanent)")
    node_id: int | None = Field(None, description="Node ID for node-specific ban (null = global)")

    @field_validator('ip_address')
    @classmethod
    def validate_ip(cls, v):
        """Validate IP address format"""
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ip_address": "192.168.1.100",
                "reason": "Brute force attack detected",
                "expires_at": "2025-01-20T00:00:00",
                "node_id": None
            }
        }
    )


class IPUnbanRequest(BaseModel):
    """Request to unban an IP address"""
    ip_address: str = Field(..., description="IP address to unban")

    @field_validator('ip_address')
    @classmethod
    def validate_ip(cls, v):
        """Validate IP address format"""
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")


class IPBlacklistEntry(BaseModel):
    """IP blacklist entry response"""
    id: int
    ip_address: str
    reason: str | None
    banned_by: str | None
    banned_at: datetime
    expires_at: datetime | None
    is_active: bool
    node_id: int | None
    node_name: str | None = Field(None, description="Node name if node-specific ban")
    created_at: datetime
    updated_at: datetime

    # Additional computed fields
    is_expired: bool = Field(False, description="Whether the ban has expired")
    is_global: bool = Field(True, description="Whether this is a global ban")

    model_config = ConfigDict(from_attributes=True)


class BlacklistResponse(BaseModel):
    """Response with list of blacklisted IPs"""
    entries: list[IPBlacklistEntry]
    total: int
    active: int
    expired: int
    global_bans: int
    node_specific_bans: int


class BanOperationResponse(BaseModel):
    """Response for ban/unban operations"""
    success: bool
    message: str
    ip_address: str
    affected_nodes: int = Field(0, description="Number of nodes that need to sync")


class NodeBlacklistSyncStatus(BaseModel):
    """Blacklist sync status for a specific node"""
    node_id: int
    node_name: str
    last_sync_at: datetime | None = Field(None, description="Last successful sync time")
    sync_status: str = Field(..., description="Sync status: 'synced', 'pending', 'error'")
    blacklisted_ips_count: int = Field(0, description="Number of IPs currently blocked on node")
    error_message: str | None = Field(None, description="Error message if sync failed")


class AllNodesBlacklistSyncStatus(BaseModel):
    """Aggregated blacklist sync status for all nodes"""
    nodes: list[NodeBlacklistSyncStatus]
    total_nodes: int
    synced_nodes: int
    pending_nodes: int
    error_nodes: int
    total_blacklisted_ips: int
