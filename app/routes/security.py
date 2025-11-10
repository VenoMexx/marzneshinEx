"""
Security Management Routes

API endpoints for centralized IP blacklist and fail2ban management
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_

from app.db import GetDB, crud
from app.db.models import IPBlacklist, Node
from app.dependencies import SudoAdminDep, DBDep, get_admin
from app.models.security import (
    IPBanRequest,
    IPUnbanRequest,
    IPBlacklistEntry,
    BlacklistResponse,
    BanOperationResponse,
    NodeBlacklistSyncStatus,
    AllNodesBlacklistSyncStatus,
)
from app import marznode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/security", tags=["Security"])


@router.get("/blacklist", response_model=BlacklistResponse)
def get_blacklist(
    db: DBDep,
    admin: SudoAdminDep,
    active_only: bool = Query(True, description="Show only active bans"),
    node_id: int | None = Query(None, description="Filter by node ID (null = global bans only)"),
):
    """
    Get IP blacklist entries

    Returns list of all blacklisted IP addresses with filtering options.

    **Filters:**
    - `active_only`: Show only active (non-expired) bans
    - `node_id`: Filter by node (null = show global bans)

    **Use Case:** View all banned IPs across the system or for specific node
    """
    query = db.query(IPBlacklist)

    # Filter by active status
    if active_only:
        query = query.filter(
            and_(
                IPBlacklist.is_active == True,
                (IPBlacklist.expires_at == None) | (IPBlacklist.expires_at > datetime.utcnow())
            )
        )

    # Filter by node
    if node_id is not None:
        query = query.filter(IPBlacklist.node_id == node_id)
    else:
        # Show global bans only
        query = query.filter(IPBlacklist.node_id == None)

    entries_db = query.all()

    # Convert to response models
    entries = []
    for entry in entries_db:
        # Check if expired
        is_expired = False
        if entry.expires_at and entry.expires_at < datetime.utcnow():
            is_expired = True

        # Get node name if node-specific
        node_name = None
        if entry.node_id:
            node = crud.get_node_by_id(db, entry.node_id)
            node_name = node.name if node else f"Node {entry.node_id}"

        entries.append(IPBlacklistEntry(
            id=entry.id,
            ip_address=entry.ip_address,
            reason=entry.reason,
            banned_by=entry.banned_by,
            banned_at=entry.banned_at,
            expires_at=entry.expires_at,
            is_active=entry.is_active,
            node_id=entry.node_id,
            node_name=node_name,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            is_expired=is_expired,
            is_global=(entry.node_id is None)
        ))

    # Calculate statistics
    total = len(entries)
    active = sum(1 for e in entries if e.is_active and not e.is_expired)
    expired = sum(1 for e in entries if e.is_expired)
    global_bans = sum(1 for e in entries if e.is_global)
    node_specific_bans = total - global_bans

    return BlacklistResponse(
        entries=entries,
        total=total,
        active=active,
        expired=expired,
        global_bans=global_bans,
        node_specific_bans=node_specific_bans
    )


@router.post("/blacklist/ban", response_model=BanOperationResponse)
def ban_ip(
    ban_request: IPBanRequest,
    db: DBDep,
    admin: SudoAdminDep,
):
    """
    Ban an IP address globally or on specific node

    Adds IP to centralized blacklist. Nodes will sync this ban on next sync cycle.

    **Parameters:**
    - `ip_address`: IP to ban (IPv4 or IPv6)
    - `reason`: Optional reason for ban
    - `expires_at`: Optional expiration date (null = permanent)
    - `node_id`: Optional node ID (null = global ban across all nodes)

    **Note:** Requires Marznode v0.3.0+ with fail2ban integration.
    See MARZNODE_FAIL2BAN_SPECIFICATION.md for implementation details.
    """
    # Check if IP already banned
    existing = db.query(IPBlacklist).filter(
        and_(
            IPBlacklist.ip_address == ban_request.ip_address,
            IPBlacklist.node_id == ban_request.node_id,
            IPBlacklist.is_active == True
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"IP {ban_request.ip_address} is already banned"
        )

    # Validate node exists if node_id specified
    if ban_request.node_id:
        node = crud.get_node_by_id(db, ban_request.node_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"Node {ban_request.node_id} not found")

    # Create blacklist entry
    blacklist_entry = IPBlacklist(
        ip_address=ban_request.ip_address,
        reason=ban_request.reason,
        banned_by=admin.username,
        banned_at=datetime.utcnow(),
        expires_at=ban_request.expires_at,
        is_active=True,
        node_id=ban_request.node_id
    )

    db.add(blacklist_entry)
    db.commit()
    db.refresh(blacklist_entry)

    # Calculate affected nodes
    if ban_request.node_id:
        affected_nodes = 1
    else:
        # Global ban affects all active nodes
        affected_nodes = db.query(Node).filter(Node.status != "disabled").count()

    logger.info(
        f"IP {ban_request.ip_address} banned by {admin.username}. "
        f"Reason: {ban_request.reason}. Affects {affected_nodes} node(s)."
    )

    return BanOperationResponse(
        success=True,
        message=f"IP {ban_request.ip_address} banned successfully",
        ip_address=ban_request.ip_address,
        affected_nodes=affected_nodes
    )


@router.post("/blacklist/unban", response_model=BanOperationResponse)
def unban_ip(
    unban_request: IPUnbanRequest,
    db: DBDep,
    admin: SudoAdminDep,
):
    """
    Unban an IP address

    Removes IP from blacklist or marks it as inactive.
    Nodes will sync this change on next sync cycle.

    **Parameters:**
    - `ip_address`: IP to unban

    **Note:** This unbans the IP globally. For node-specific unbans, use DELETE endpoint.
    """
    # Find active bans for this IP
    bans = db.query(IPBlacklist).filter(
        and_(
            IPBlacklist.ip_address == unban_request.ip_address,
            IPBlacklist.is_active == True
        )
    ).all()

    if not bans:
        raise HTTPException(
            status_code=404,
            detail=f"IP {unban_request.ip_address} is not currently banned"
        )

    # Mark all bans as inactive
    affected_nodes = 0
    for ban in bans:
        ban.is_active = False
        ban.updated_at = datetime.utcnow()

        if ban.node_id:
            affected_nodes += 1
        else:
            # Global ban affects all active nodes
            affected_nodes = db.query(Node).filter(Node.status != "disabled").count()

    db.commit()

    logger.info(
        f"IP {unban_request.ip_address} unbanned by {admin.username}. "
        f"Affects {affected_nodes} node(s)."
    )

    return BanOperationResponse(
        success=True,
        message=f"IP {unban_request.ip_address} unbanned successfully",
        ip_address=unban_request.ip_address,
        affected_nodes=affected_nodes
    )


@router.get("/blacklist/sync-status", response_model=AllNodesBlacklistSyncStatus)
async def get_blacklist_sync_status(
    db: DBDep,
    admin: SudoAdminDep,
):
    """
    Get blacklist sync status for all nodes

    Returns synchronization status showing which nodes have successfully
    synced the blacklist and which are pending or have errors.

    **Use Case:** Monitor fail2ban sync status across all nodes

    **Note:** Requires Marznode v0.3.0+ with fail2ban integration.
    See MARZNODE_FAIL2BAN_SPECIFICATION.md for implementation details.
    """
    all_nodes = db.query(Node).all()

    node_statuses = []
    synced_count = 0
    pending_count = 0
    error_count = 0

    for db_node in all_nodes:
        # Check if node is connected
        node = marznode.nodes.get(db_node.id)

        if not node:
            # Node not connected
            node_statuses.append(NodeBlacklistSyncStatus(
                node_id=db_node.id,
                node_name=db_node.name,
                last_sync_at=None,
                sync_status="pending",
                blacklisted_ips_count=0,
                error_message="Node not connected"
            ))
            pending_count += 1
            continue

        try:
            # TODO: Implement when Marznode supports blacklist sync
            # sync_status = await node.get_blacklist_sync_status()

            # Placeholder response
            node_statuses.append(NodeBlacklistSyncStatus(
                node_id=db_node.id,
                node_name=db_node.name,
                last_sync_at=None,
                sync_status="pending",
                blacklisted_ips_count=0,
                error_message="Fail2ban integration not yet supported by Marznode"
            ))
            pending_count += 1

        except Exception as e:
            logger.error(f"Failed to get sync status for node {db_node.id}: {e}")
            node_statuses.append(NodeBlacklistSyncStatus(
                node_id=db_node.id,
                node_name=db_node.name,
                last_sync_at=None,
                sync_status="error",
                blacklisted_ips_count=0,
                error_message=str(e)
            ))
            error_count += 1

    # Get total blacklisted IPs (active only)
    total_blacklisted = db.query(IPBlacklist).filter(
        and_(
            IPBlacklist.is_active == True,
            (IPBlacklist.expires_at == None) | (IPBlacklist.expires_at > datetime.utcnow())
        )
    ).count()

    return AllNodesBlacklistSyncStatus(
        nodes=node_statuses,
        total_nodes=len(all_nodes),
        synced_nodes=synced_count,
        pending_nodes=pending_count,
        error_nodes=error_count,
        total_blacklisted_ips=total_blacklisted
    )


@router.post("/blacklist/sync")
async def force_sync_blacklist(
    db: DBDep,
    admin: SudoAdminDep,
    node_id: int | None = Query(None, description="Node ID to sync (null = all nodes)"),
):
    """
    Force immediate blacklist synchronization

    Triggers immediate sync of blacklist to specified node or all nodes.
    Normally nodes sync automatically every few minutes.

    **Parameters:**
    - `node_id`: Specific node to sync (null = sync all nodes)

    **Use Case:** After banning/unbanning IP, force immediate sync instead of waiting

    **Note:** Requires Marznode v0.3.0+ with fail2ban integration.
    See MARZNODE_FAIL2BAN_SPECIFICATION.md for implementation details.
    """
    if node_id:
        # Sync specific node
        node = crud.get_node_by_id(db, node_id)
        if not node:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

        # Check if node is connected
        node_conn = marznode.nodes.get(node_id)
        if not node_conn:
            raise HTTPException(
                status_code=503,
                detail=f"Node {node.name} is not connected"
            )

        try:
            # TODO: Implement when Marznode supports fail2ban sync
            # await node_conn.sync_blacklist()

            logger.info(f"Blacklist sync triggered for node {node.name} by {admin.username}")

            return {
                "success": False,
                "message": "Fail2ban sync not yet supported by Marznode. Please upgrade to Marznode v0.3.0+",
                "synced_nodes": 0
            }

        except Exception as e:
            logger.error(f"Failed to sync blacklist to node {node.name}: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to sync blacklist: {str(e)}"
            )

    else:
        # Sync all nodes
        all_nodes = db.query(Node).filter(Node.status != "disabled").all()
        synced_count = 0

        for db_node in all_nodes:
            node_conn = marznode.nodes.get(db_node.id)
            if not node_conn:
                logger.warning(f"Node {db_node.name} not connected, skipping sync")
                continue

            try:
                # TODO: Implement when Marznode supports fail2ban sync
                # await node_conn.sync_blacklist()
                # synced_count += 1
                pass

            except Exception as e:
                logger.error(f"Failed to sync blacklist to node {db_node.name}: {e}")

        logger.info(f"Blacklist sync triggered for all nodes by {admin.username}")

        return {
            "success": False,
            "message": "Fail2ban sync not yet supported by Marznode. Please upgrade to Marznode v0.3.0+",
            "synced_nodes": synced_count
        }
