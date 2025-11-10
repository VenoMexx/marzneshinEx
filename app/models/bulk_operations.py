"""
Bulk Operations Models

This module defines models for bulk user operations.
"""

from enum import StrEnum
from pydantic import BaseModel, Field


class BulkOperationType(StrEnum):
    """Bulk operation types"""
    DELETE = "delete"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    RESET_TRAFFIC = "reset_traffic"
    RESET_DAYS = "reset_days"
    EXTEND_DAYS = "extend_days"
    ADD_TRAFFIC = "add_traffic"
    SET_TRAFFIC_LIMIT = "set_traffic_limit"


class BulkUserOperation(BaseModel):
    """Request model for bulk user operations"""
    usernames: list[str] = Field(..., description="List of usernames to operate on", min_length=1)
    operation: BulkOperationType = Field(..., description="Operation to perform")

    # Optional parameters for specific operations
    days: int | None = Field(None, description="Number of days (for extend_days, reset_days)", ge=1)
    traffic_gb: float | None = Field(None, description="Traffic in GB (for add_traffic, set_traffic_limit)", ge=0)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "usernames": ["user1", "user2", "user3"],
                    "operation": "activate",
                },
                {
                    "usernames": ["user4", "user5"],
                    "operation": "extend_days",
                    "days": 30
                },
                {
                    "usernames": ["user6", "user7"],
                    "operation": "add_traffic",
                    "traffic_gb": 10.0
                }
            ]
        }
    }


class BulkOperationResult(BaseModel):
    """Result of a single user operation"""
    username: str
    success: bool
    message: str | None = None
    error: str | None = None


class BulkOperationResponse(BaseModel):
    """Response model for bulk operations"""
    operation: BulkOperationType
    total: int
    successful: int
    failed: int
    results: list[BulkOperationResult]

    model_config = {
        "json_schema_extra": {
            "example": {
                "operation": "activate",
                "total": 5,
                "successful": 4,
                "failed": 1,
                "results": [
                    {
                        "username": "user1",
                        "success": True,
                        "message": "User activated successfully"
                    },
                    {
                        "username": "user2",
                        "success": True,
                        "message": "User activated successfully"
                    },
                    {
                        "username": "user3",
                        "success": False,
                        "error": "User not found"
                    },
                ]
            }
        }
    }
