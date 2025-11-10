"""
User Control Panel Routes

This module provides API endpoints for the user self-service portal,
allowing users to view their account information, get subscription links,
and manage their configs without admin assistance.
"""

import io
import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import Response, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import qrcode
import jwt

from app.config.env import DOCS_URL
from app.db import GetDB, crud
from app.db.models import User
from app.models.user_panel import (
    UserPanelAuth,
    UserPanelAuthResponse,
    UserPanelRefreshRequest,
    UserPanelRefreshResponse,
    UserPanelInfo,
    SubscriptionLinks,
)
from app.config import JWT_SECRET_KEY
from app.templates import render_template

logger = logging.getLogger(__name__)
router = APIRouter(tags=["User Panel"])

# CSRF Protection: Verify request origin
def verify_origin(request: Request):
    """
    Verify request origin to prevent CSRF attacks.
    Checks that the request comes from the same origin.
    """
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    host = request.headers.get("host")

    # Allow requests without origin (direct API calls, mobile apps)
    if not origin and not referer:
        return True

    # Check if origin matches host
    if origin:
        # Extract host from origin
        origin_host = origin.replace("http://", "").replace("https://", "").split("/")[0]
        if origin_host != host:
            logger.warning(f"CSRF attempt: Origin {origin_host} != Host {host}")
            raise HTTPException(
                status_code=403,
                detail="Cross-origin request forbidden"
            )

    return True

# JWT configuration for user panel tokens
USER_PANEL_ACCESS_TOKEN_EXPIRE_HOURS = 1
USER_PANEL_REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_user_panel_tokens(username: str, user_key: str) -> dict:
    """
    Create JWT access and refresh tokens for user panel

    Args:
        username: Username
        user_key: User subscription key

    Returns:
        Dict with access_token and refresh_token
    """
    # Access token - short lived (1 hour)
    access_expire = datetime.utcnow() + timedelta(hours=USER_PANEL_ACCESS_TOKEN_EXPIRE_HOURS)
    access_payload = {
        "sub": username,
        "key": user_key,
        "type": "access",
        "exp": access_expire,
    }
    access_token = jwt.encode(access_payload, JWT_SECRET_KEY, algorithm="HS256")

    # Refresh token - long lived (7 days)
    refresh_expire = datetime.utcnow() + timedelta(days=USER_PANEL_REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_payload = {
        "sub": username,
        "key": user_key,
        "type": "refresh",
        "exp": refresh_expire,
    }
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET_KEY, algorithm="HS256")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def verify_user_panel_token(token: str, token_type: str = "access") -> dict:
    """
    Verify JWT token and return payload

    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        Token payload dict

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != token_type:
            raise HTTPException(status_code=401, detail=f"Invalid token type. Expected {token_type}")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user_panel_user(
    authorization: Annotated[str | None, Header()] = None
) -> User:
    """
    Get current user from JWT token

    Args:
        authorization: Authorization header with Bearer token

    Returns:
        User object

    Raises:
        HTTPException: If authentication fails
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )

    token = authorization.replace("Bearer ", "")
    payload = verify_user_panel_token(token)

    username = payload.get("sub")
    user_key = payload.get("key")

    with GetDB() as db:
        user = crud.get_user(db, username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify subscription key
        if user.key != user_key:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        return user


UserPanelUserDep = Annotated[User, Depends(get_current_user_panel_user)]


@router.get("/user-panel", response_class=HTMLResponse)
def user_panel_page():
    """
    Serve the user control panel HTML page

    This is the main entry point for users to access their self-service portal.
    Users can view account information, get subscription links, and download QR codes.

    **Access URL:** https://your-panel.com/user-panel
    """
    return render_template("user_panel.html")


@router.post("/api/user-panel/auth", response_model=UserPanelAuthResponse)
def authenticate_user(
    auth_request: UserPanelAuth,
    request: Request,
    _: bool = Depends(verify_origin)
):
    """
    Authenticate user with username and subscription key

    **Security:** Protected against CSRF attacks via origin verification

    This endpoint allows users to log in to the user panel using their
    username and subscription key (found in their subscription URL).

    **Example:**
    ```json
    {
        "username": "john_doe",
        "subscription_key": "abc123def456..."
    }
    ```

    **Response:**
    Returns JWT access and refresh tokens. The access token should be included
    in the Authorization header for all subsequent requests:
    ```
    Authorization: Bearer <access_token>
    ```

    **Token Expiry:**
    - Access token: 1 hour
    - Refresh token: 7 days (use /refresh endpoint to get new access token)
    """
    with GetDB() as db:
        user = crud.get_user(db, auth_request.username)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Verify subscription key
        if user.key != auth_request.subscription_key:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Check if user is removed
        if user.removed:
            raise HTTPException(status_code=401, detail="Account has been removed")

        # Create access and refresh tokens
        tokens = create_user_panel_tokens(user.username, user.key)

        logger.info(f"User panel authentication successful for user: {user.username}")

        return UserPanelAuthResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type="bearer",
            username=user.username,
            expires_in=USER_PANEL_ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            refresh_expires_in=USER_PANEL_REFRESH_TOKEN_EXPIRE_DAYS * 86400
        )


@router.post("/api/user-panel/refresh", response_model=UserPanelRefreshResponse)
def refresh_access_token(refresh_request: UserPanelRefreshRequest):
    """
    Refresh access token using refresh token

    When the access token expires (after 1 hour), use this endpoint to obtain
    a new access token without requiring the user to re-enter credentials.

    **Example:**
    ```json
    {
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
    ```

    **Response:**
    Returns a new access token valid for 1 hour.

    **Token Expiry:** Access token: 1 hour

    **Security:**
    - Refresh tokens are long-lived (7 days)
    - If refresh token expires, user must re-authenticate
    - Refresh tokens cannot be used for API access, only for getting new access tokens
    """
    # Verify refresh token
    payload = verify_user_panel_token(refresh_request.refresh_token, token_type="refresh")

    username = payload.get("sub")
    user_key = payload.get("key")

    # Verify user still exists and credentials are valid
    with GetDB() as db:
        user = crud.get_user(db, username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        # Verify subscription key hasn't changed
        if user.key != user_key:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Check if user is removed
        if user.removed:
            raise HTTPException(status_code=401, detail="Account has been removed")

    # Create new access token
    access_expire = datetime.utcnow() + timedelta(hours=USER_PANEL_ACCESS_TOKEN_EXPIRE_HOURS)
    access_payload = {
        "sub": username,
        "key": user_key,
        "type": "access",
        "exp": access_expire,
    }
    new_access_token = jwt.encode(access_payload, JWT_SECRET_KEY, algorithm="HS256")

    logger.info(f"Access token refreshed for user: {username}")

    return UserPanelRefreshResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=USER_PANEL_ACCESS_TOKEN_EXPIRE_HOURS * 3600
    )


@router.get("/api/user-panel/me", response_model=UserPanelInfo)
def get_my_info(user: UserPanelUserDep):
    """
    Get current user's account information

    Returns detailed information about the authenticated user's account,
    including traffic usage, expiry date, and account status.

    **Authentication:** Requires Bearer token from /auth endpoint
    """
    # Calculate remaining traffic
    remaining_traffic = None
    usage_percentage = None
    if user.data_limit:
        remaining_traffic = max(0, user.data_limit - user.used_traffic)
        usage_percentage = (user.used_traffic / user.data_limit) * 100

    # Calculate days remaining
    days_remaining = None
    if user.expire_date:
        delta = user.expire_date - datetime.utcnow()
        days_remaining = max(0, delta.days)

    return UserPanelInfo(
        username=user.username,
        is_active=user.is_active,
        expired=user.expired,
        data_limit_reached=user.data_limit_reached,
        used_traffic=user.used_traffic,
        data_limit=user.data_limit,
        remaining_traffic=remaining_traffic,
        usage_percentage=usage_percentage,
        expire_date=user.expire_date,
        expire_strategy=user.expire_strategy,
        days_remaining=days_remaining,
        created_at=user.created_at,
        enabled=user.enabled,
        activated=user.activated,
        services_count=len(user.services),
        note=user.note,
    )


@router.get("/api/user-panel/subscription-links", response_model=SubscriptionLinks)
def get_subscription_links(user: UserPanelUserDep):
    """
    Get subscription links for all client formats

    Returns subscription URLs for V2Ray, Clash, Clash Meta, and Sing-Box clients.

    **Authentication:** Requires Bearer token

    **Usage:**
    Copy the appropriate link for your client type and paste it into the
    client's subscription field.
    """
    base_url = DOCS_URL.rstrip('/')

    return SubscriptionLinks(
        v2ray=f"{base_url}/sub/{user.key}/links",
        clash=f"{base_url}/sub/{user.key}/clash",
        clash_meta=f"{base_url}/sub/{user.key}/clash-meta",
        singbox=f"{base_url}/sub/{user.key}/sing-box",
    )


@router.get("/api/user-panel/qr/{format}")
def get_qr_code(format: str, user: UserPanelUserDep):
    """
    Get QR code for subscription link

    Generates a QR code image for the specified subscription format.

    **Authentication:** Requires Bearer token

    **Parameters:**
    - `format`: Client format (v2ray, clash, clash-meta, singbox)

    **Response:** PNG image

    **Usage:**
    Scan the QR code with your mobile proxy client to automatically
    configure the subscription.
    """
    # Validate format
    valid_formats = {
        "v2ray": "links",
        "clash": "clash",
        "clash-meta": "clash-meta",
        "singbox": "sing-box",
    }

    if format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Must be one of: {', '.join(valid_formats.keys())}"
        )

    # Generate subscription URL
    base_url = DOCS_URL.rstrip('/')
    sub_url = f"{base_url}/sub/{user.key}/{valid_formats[format]}"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(sub_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    logger.info(f"QR code generated for user {user.username}, format: {format}")

    return Response(content=img_bytes.read(), media_type="image/png")


@router.post("/api/user-panel/logout")
def logout(
    user: UserPanelUserDep,
    request: Request,
    _: bool = Depends(verify_origin)
):
    """
    Logout from user panel

    Note: Since JWT tokens are stateless, this endpoint simply confirms
    the logout action. The client should discard the token.

    **Authentication:** Requires Bearer token
    **Security:** Protected against CSRF attacks via origin verification

    **Client Action:** Delete the stored access token after calling this endpoint.
    """
    logger.info(f"User {user.username} logged out from user panel")

    return {
        "message": "Logged out successfully",
        "username": user.username
    }
