"""
User Control Panel Models

This module defines models for the user self-service portal.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class UserPanelAuth(BaseModel):
    """Authentication request for user panel"""
    username: str = Field(..., description="Username")
    subscription_key: str = Field(..., description="Subscription key (from subscription URL)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "subscription_key": "abc123def456..."
            }
        }
    }


class UserPanelAuthResponse(BaseModel):
    """Authentication response with access and refresh tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    username: str
    expires_in: int = 3600  # 1 hour in seconds
    refresh_expires_in: int = 604800  # 7 days in seconds


class UserPanelRefreshRequest(BaseModel):
    """Request to refresh access token"""
    refresh_token: str = Field(..., description="Refresh token from authentication")

    model_config = {
        "json_schema_extra": {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    }


class UserPanelRefreshResponse(BaseModel):
    """Response with new access token"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  # 1 hour in seconds


class UserPanelInfo(BaseModel):
    """User information for control panel"""
    username: str
    is_active: bool
    expired: bool
    data_limit_reached: bool

    # Traffic information
    used_traffic: int
    data_limit: int | None
    remaining_traffic: int | None
    usage_percentage: float | None

    # Expiry information
    expire_date: datetime | None
    expire_strategy: str
    days_remaining: int | None

    # Account information
    created_at: datetime
    enabled: bool
    activated: bool

    # Service information
    services_count: int
    note: str | None

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "is_active": True,
                "expired": False,
                "data_limit_reached": False,
                "used_traffic": 5368709120,
                "data_limit": 10737418240,
                "remaining_traffic": 5368709120,
                "usage_percentage": 50.0,
                "expire_date": "2024-12-31T23:59:59",
                "expire_strategy": "fixed_date",
                "days_remaining": 45,
                "created_at": "2024-11-01T10:30:00",
                "enabled": True,
                "activated": True,
                "services_count": 3,
                "note": "Premium user"
            }
        }
    }


class SubscriptionLinks(BaseModel):
    """Subscription links for different client formats"""
    v2ray: str
    clash: str
    clash_meta: str
    singbox: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "v2ray": "https://panel.example.com/sub/abc123.../links",
                "clash": "https://panel.example.com/sub/abc123.../clash",
                "clash_meta": "https://panel.example.com/sub/abc123.../clash-meta",
                "singbox": "https://panel.example.com/sub/abc123.../sing-box"
            }
        }
    }
