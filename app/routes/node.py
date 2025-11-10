import asyncio
import logging
from typing import Annotated

import sqlalchemy
from fastapi import APIRouter, Body, Query
from fastapi import HTTPException, WebSocket
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.links import Page
from starlette.websockets import WebSocketDisconnect, WebSocketState
from grpclib.exceptions import StreamTerminatedError, GRPCError

from app import marznode
from app.db import crud, get_tls_certificate
from app.db.models import Node
from app.dependencies import (
    DBDep,
    SudoAdminDep,
    EndDateDep,
    StartDateDep,
    get_admin,
)
from app.models.node import (
    NodeCreate,
    NodeModify,
    NodeResponse,
    NodeSettings,
    NodeStatus,
    BackendConfig,
    BackendStats,
    SystemMetrics,
    NodeHealthScore,
    NodeMetricsResponse,
    AllNodesMetricsResponse,
)
from app.models.system import TrafficUsageSeries
from app.models.warp import WarpSettings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nodes", tags=["Node"])


@router.get("", response_model=Page[NodeResponse])
def get_nodes(
    db: DBDep,
    admin: SudoAdminDep,
    status: list[NodeStatus] = Query(None),
    name: str = Query(None),
):
    query = db.query(Node)

    if name:
        query = query.filter(Node.name.ilike(f"%{name}%"))

    if status:
        query = query.filter(Node.status.in_(status))

    return paginate(db, query)


@router.post("", response_model=NodeResponse)
async def add_node(new_node: NodeCreate, db: DBDep, admin: SudoAdminDep):
    try:
        db_node = crud.create_node(db, new_node)
    except sqlalchemy.exc.IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f'Node "{new_node.name}" already exists'
        )
    certificate = get_tls_certificate(db)

    await marznode.operations.add_node(db_node, certificate)

    logger.info("New node `%s` added", db_node.name)
    return db_node


@router.get("/settings", response_model=NodeSettings)
def get_node_settings(db: DBDep, admin: SudoAdminDep):
    tls = crud.get_tls_certificate(db)

    return NodeSettings(certificate=tls.certificate)


@router.get("/{node_id}", response_model=NodeResponse)
def get_node(node_id: int, db: DBDep, admin: SudoAdminDep):
    db_node = crud.get_node_by_id(db, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")

    return db_node


@router.websocket("/{node_id}/{backend}/logs")
async def node_logs(
    node_id: int,
    backend: str,
    websocket: WebSocket,
    db: DBDep,
    include_buffer: bool = True,
):
    token = websocket.query_params.get("token", "") or websocket.headers.get(
        "Authorization", ""
    ).removeprefix("Bearer ")
    admin = get_admin(db, token)

    if not admin or not admin.is_sudo:
        return await websocket.close(reason="You're not allowed", code=4403)

    if not marznode.nodes.get(node_id):
        return await websocket.close(reason="Node not found", code=4404)

    await websocket.accept()
    try:
        async for line in marznode.nodes[node_id].get_logs(
            name=backend, include_buffer=include_buffer
        ):
            await websocket.send_text(line)
    except WebSocketDisconnect:
        logger.debug("websocket disconnected")
    except (StreamTerminatedError, GRPCError):
        logger.info("node %i detached", node_id)
    finally:
        if websocket.state == WebSocketState.CONNECTED:
            await websocket.close()


@router.put("/{node_id}", response_model=NodeResponse)
async def modify_node(
    node_id: int, modified_node: NodeModify, db: DBDep, admin: SudoAdminDep
):
    db_node = crud.get_node_by_id(db, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")

    db_node = crud.update_node(db, db_node, modified_node)

    await marznode.operations.remove_node(db_node.id)
    if db_node.status != NodeStatus.disabled:
        certificate = get_tls_certificate(db)
        await marznode.operations.add_node(db_node, certificate)

    logger.info("Node `%s` modified", db_node.name)
    return db_node


@router.delete("/{node_id}")
async def remove_node(node_id: int, db: DBDep, admin: SudoAdminDep):
    db_node = crud.get_node_by_id(db, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")

    crud.remove_node(db, db_node)
    await marznode.operations.remove_node(db_node.id)

    logger.info(f"Node `%s` deleted", db_node.name)
    return {}


@router.post("/{node_id}/resync")
async def reconnect_node(node_id: int, db: DBDep, admin: SudoAdminDep):
    db_node = crud.get_node_by_id(db, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")

    return {}


@router.get("/{node_id}/usage", response_model=TrafficUsageSeries)
def get_usage(
    node_id: int,
    db: DBDep,
    admin: SudoAdminDep,
    start_date: StartDateDep,
    end_date: EndDateDep,
):
    """
    Get nodes usage
    """
    node = crud.get_node_by_id(db, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    return crud.get_node_usage(db, start_date, end_date, node)


@router.get("/{node_id}/{backend}/stats", response_model=BackendStats)
async def get_backend_stats(
    node_id: int, backend: str, db: DBDep, admin: SudoAdminDep
):
    if not (node := marznode.nodes.get(node_id)):
        raise HTTPException(status_code=404, detail="Node not found")

    try:
        stats = await node.get_backend_stats(backend)
    except Exception:
        raise HTTPException(502)
    else:
        return BackendStats(running=stats.running)


@router.get("/{node_id}/{backend}/config", response_model=BackendConfig)
async def get_node_xray_config(
    node_id: int, backend: str, admin: SudoAdminDep
):
    if not (node := marznode.nodes.get(node_id)):
        raise HTTPException(status_code=404, detail="Node not found")

    try:
        config, config_format = await node.get_backend_config(name=backend)
    except Exception:
        raise HTTPException(status_code=502, detail="Node isn't responsive")
    else:
        return {"config": config, "format": config_format}


@router.put("/{node_id}/{backend}/config")
async def alter_node_xray_config(
    node_id: int,
    backend: str,
    admin: SudoAdminDep,
    config: Annotated[BackendConfig, Body()],
):
    if not (node := marznode.nodes.get(node_id)):
        raise HTTPException(status_code=404, detail="Node not found")

    try:
        await asyncio.wait_for(
            node.restart_backend(
                name=backend,
                config=config.config,
                config_format=config.format.value,
            ),
            5,
        )
    except:
        raise HTTPException(
            status_code=502, detail="No response from the node."
        )
    return {}


@router.get("/{node_id}/warp", response_model=WarpSettings)
def get_node_warp_config(node_id: int, db: DBDep, admin: SudoAdminDep):
    """
    Get WARP configuration for a specific node
    """
    db_node = crud.get_node_by_id(db, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")

    if db_node.warp_config:
        return WarpSettings.model_validate(db_node.warp_config)

    # Return default WARP settings if not configured
    return WarpSettings()


@router.put("/{node_id}/warp", response_model=WarpSettings)
def update_node_warp_config(
    node_id: int,
    warp_settings: WarpSettings,
    db: DBDep,
    admin: SudoAdminDep
):
    """
    Update WARP configuration for a specific node

    Note: This only updates the panel-side configuration.
    Marznode integration is required for WARP to be operational.
    """
    db_node = crud.get_node_by_id(db, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Update warp_config in database
    db_node.warp_config = warp_settings.model_dump()
    db.commit()
    db.refresh(db_node)

    logger.info("WARP config updated for node `%s`", db_node.name)
    return warp_settings


# Advanced Monitoring Endpoints

@router.get("/{node_id}/metrics", response_model=NodeMetricsResponse)
async def get_node_metrics(
    node_id: int,
    db: DBDep,
    admin: SudoAdminDep
):
    """
    Get advanced system metrics for a specific node

    Returns comprehensive system metrics including:
    - CPU usage and core count
    - Memory usage (total, used, percentage)
    - Disk usage (total, used, percentage)
    - Network statistics (rx/tx bytes)
    - System uptime
    - Health score (0-100)

    **Note:** This endpoint requires Marznode v0.3.0+ with metrics collection support.
    See MARZNODE_METRICS_SPECIFICATION.md for implementation details.
    """
    db_node = crud.get_node_by_id(db, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Check if node is connected
    node = marznode.nodes.get(node_id)
    if not node:
        return NodeMetricsResponse(
            node_id=node_id,
            node_name=db_node.name,
            error="Node is not connected"
        )

    try:
        # Try to get metrics from Marznode
        # This will call a new gRPC method that needs to be implemented in Marznode
        # For now, return a placeholder response indicating feature needs node support

        # TODO: Implement when Marznode supports metrics collection
        # metrics = await node.get_system_metrics()

        return NodeMetricsResponse(
            node_id=node_id,
            node_name=db_node.name,
            backends=[],
            error="Metrics collection not yet supported by Marznode. Please upgrade to Marznode v0.3.0+"
        )

    except Exception as e:
        logger.error(f"Failed to get metrics for node {node_id}: {e}")
        return NodeMetricsResponse(
            node_id=node_id,
            node_name=db_node.name,
            error=f"Failed to collect metrics: {str(e)}"
        )


def calculate_health_score(metrics: SystemMetrics) -> NodeHealthScore:
    """
    Calculate node health score based on system metrics

    Scoring algorithm:
    - CPU: 100 - cpu_percent (lower usage = better)
    - Memory: 100 - memory_percent (lower usage = better)
    - Disk: 100 - disk_percent (lower usage = better)
    - Network: Always 100 (placeholder, can be enhanced)
    - Overall: Weighted average (CPU: 30%, Memory: 30%, Disk: 30%, Network: 10%)
    """
    # Individual scores (inverted - lower usage = higher score)
    cpu_score = max(0, 100 - metrics.cpu_percent)
    memory_score = max(0, 100 - metrics.memory_percent)
    disk_score = max(0, 100 - metrics.disk_percent)
    network_score = 100.0  # Placeholder

    # Weighted overall score
    overall_score = (
        cpu_score * 0.3 +
        memory_score * 0.3 +
        disk_score * 0.3 +
        network_score * 0.1
    )

    # Determine status based on overall score
    if overall_score >= 70:
        status = NodeStatus.healthy
    elif overall_score >= 40:
        status = NodeStatus.unhealthy
    else:
        status = NodeStatus.unhealthy

    return NodeHealthScore(
        overall_score=round(overall_score, 2),
        cpu_score=round(cpu_score, 2),
        memory_score=round(memory_score, 2),
        disk_score=round(disk_score, 2),
        network_score=round(network_score, 2),
        status=status
    )


@router.get("/metrics", response_model=AllNodesMetricsResponse)
async def get_all_nodes_metrics(
    db: DBDep,
    admin: SudoAdminDep
):
    """
    Get aggregated metrics for all nodes

    Returns comprehensive metrics for all nodes including:
    - Individual node metrics
    - Aggregated statistics (total nodes, healthy/unhealthy counts)
    - Average resource usage across all nodes
    - Total network traffic

    **Use Case:** Multi-node dashboard overview

    **Note:** This endpoint requires Marznode v0.3.0+ with metrics collection support.
    See MARZNODE_METRICS_SPECIFICATION.md for implementation details.
    """
    # Get all nodes from database
    all_nodes = db.query(Node).all()

    node_metrics_list = []
    total_cpu = 0.0
    total_memory = 0.0
    total_disk = 0.0
    total_rx = 0
    total_tx = 0
    healthy_count = 0
    unhealthy_count = 0
    disabled_count = 0
    nodes_with_metrics = 0

    for db_node in all_nodes:
        # Check node status
        if db_node.status == NodeStatus.disabled:
            disabled_count += 1
            node_metrics_list.append(NodeMetricsResponse(
                node_id=db_node.id,
                node_name=db_node.name,
                error="Node is disabled"
            ))
            continue

        # Check if node is connected
        node = marznode.nodes.get(db_node.id)
        if not node:
            unhealthy_count += 1
            node_metrics_list.append(NodeMetricsResponse(
                node_id=db_node.id,
                node_name=db_node.name,
                error="Node is not connected"
            ))
            continue

        try:
            # TODO: Implement when Marznode supports metrics collection
            # metrics = await node.get_system_metrics()
            # health = calculate_health_score(metrics)

            # For now, return placeholder
            node_metrics_list.append(NodeMetricsResponse(
                node_id=db_node.id,
                node_name=db_node.name,
                error="Metrics collection not yet supported by Marznode"
            ))

            # When implemented:
            # if health.status == NodeStatus.healthy:
            #     healthy_count += 1
            # else:
            #     unhealthy_count += 1
            #
            # total_cpu += metrics.cpu_percent
            # total_memory += metrics.memory_percent
            # total_disk += metrics.disk_percent
            # total_rx += metrics.network_rx_bytes
            # total_tx += metrics.network_tx_bytes
            # nodes_with_metrics += 1

        except Exception as e:
            logger.error(f"Failed to get metrics for node {db_node.id}: {e}")
            unhealthy_count += 1
            node_metrics_list.append(NodeMetricsResponse(
                node_id=db_node.id,
                node_name=db_node.name,
                error=f"Failed to collect metrics: {str(e)}"
            ))

    # Calculate averages
    avg_cpu = total_cpu / nodes_with_metrics if nodes_with_metrics > 0 else 0.0
    avg_memory = total_memory / nodes_with_metrics if nodes_with_metrics > 0 else 0.0
    avg_disk = total_disk / nodes_with_metrics if nodes_with_metrics > 0 else 0.0

    return AllNodesMetricsResponse(
        nodes=node_metrics_list,
        total_nodes=len(all_nodes),
        healthy_nodes=healthy_count,
        unhealthy_nodes=unhealthy_count,
        disabled_nodes=disabled_count,
        average_cpu_percent=round(avg_cpu, 2),
        average_memory_percent=round(avg_memory, 2),
        average_disk_percent=round(avg_disk, 2),
        total_network_rx=total_rx,
        total_network_tx=total_tx
    )
