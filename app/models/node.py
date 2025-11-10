from enum import StrEnum, IntEnum

from pydantic import ConfigDict, BaseModel, Field
from app.models.warp import WarpSettings


class BackendConfigFormat(IntEnum):
    PLAIN = 0
    JSON = 1
    YAML = 2


class BackendConfig(BaseModel):
    config: str
    format: BackendConfigFormat


class BackendStats(BaseModel):
    running: bool


class Backend(BaseModel):
    name: str
    backend_type: str
    version: str | None
    running: bool


class NodeStatus(StrEnum):
    healthy = "healthy"
    unhealthy = "unhealthy"
    disabled = "disabled"


class NodeConnectionBackend(StrEnum):
    grpcio = "grpcio"
    grpclib = "grpclib"


class NodeSettings(BaseModel):
    min_node_version: str = "v0.2.0"
    certificate: str


class Node(BaseModel):
    id: int | None = Field(None)
    name: str
    address: str
    port: int = 53042
    connection_backend: NodeConnectionBackend = Field(
        default=NodeConnectionBackend.grpclib
    )
    usage_coefficient: float = Field(ge=0, default=1.0)
    model_config = ConfigDict(from_attributes=True)


class NodeCreate(Node):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "DE node",
                "address": "192.168.1.1",
                "port": 53042,
                "usage_coefficient": 1,
            }
        }
    )


class NodeModify(Node):
    name: str | None = Field(None)
    address: str | None = Field(None)
    port: int | None = Field(None)
    connection_backend: NodeConnectionBackend | None = Field(None)
    status: NodeStatus | None = Field(None)
    usage_coefficient: float | None = Field(None, ge=0)
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "DE node",
                "address": "192.168.1.1",
                "port": 53042,
                "status": "disabled",
                "usage_coefficient": 1.0,
            }
        }
    )


class NodeResponse(Node):
    xray_version: str | None = None
    status: NodeStatus
    message: str | None = None
    model_config = ConfigDict(from_attributes=True)
    inbound_ids: list[int] | None = None
    backends: list[Backend]
    warp_config: WarpSettings | None = None


class NodeUsageResponse(BaseModel):
    node_id: int | None = None
    node_name: str
    uplink: int
    downlink: int


class NodesUsageResponse(BaseModel):
    usages: list[NodeUsageResponse]


# Advanced Monitoring Models

class SystemMetrics(BaseModel):
    """System-level metrics from node"""
    cpu_percent: float = Field(..., ge=0, le=100, description="CPU usage percentage")
    cpu_cores: int = Field(..., gt=0, description="Number of CPU cores")
    memory_total: int = Field(..., gt=0, description="Total memory in bytes")
    memory_used: int = Field(..., ge=0, description="Used memory in bytes")
    memory_percent: float = Field(..., ge=0, le=100, description="Memory usage percentage")
    disk_total: int = Field(..., gt=0, description="Total disk space in bytes")
    disk_used: int = Field(..., ge=0, description="Used disk space in bytes")
    disk_percent: float = Field(..., ge=0, le=100, description="Disk usage percentage")
    network_rx_bytes: int = Field(..., ge=0, description="Total bytes received")
    network_tx_bytes: int = Field(..., ge=0, description="Total bytes transmitted")
    uptime_seconds: int = Field(..., ge=0, description="System uptime in seconds")
    timestamp: int = Field(..., description="Unix timestamp of metrics collection")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cpu_percent": 45.2,
                "cpu_cores": 4,
                "memory_total": 8589934592,  # 8GB
                "memory_used": 4294967296,   # 4GB
                "memory_percent": 50.0,
                "disk_total": 107374182400,  # 100GB
                "disk_used": 53687091200,    # 50GB
                "disk_percent": 50.0,
                "network_rx_bytes": 1073741824,  # 1GB
                "network_tx_bytes": 2147483648,  # 2GB
                "uptime_seconds": 864000,
                "timestamp": 1704931200
            }
        }
    )


class NodeHealthScore(BaseModel):
    """Node health scoring"""
    overall_score: float = Field(..., ge=0, le=100, description="Overall health score (0-100)")
    cpu_score: float = Field(..., ge=0, le=100, description="CPU health score")
    memory_score: float = Field(..., ge=0, le=100, description="Memory health score")
    disk_score: float = Field(..., ge=0, le=100, description="Disk health score")
    network_score: float = Field(..., ge=0, le=100, description="Network health score")
    status: NodeStatus = Field(..., description="Node status based on health")


class NodeMetricsResponse(BaseModel):
    """Complete node metrics response"""
    node_id: int
    node_name: str
    system_metrics: SystemMetrics | None = None
    health_score: NodeHealthScore | None = None
    backends: list[Backend] = []
    error: str | None = Field(None, description="Error message if metrics unavailable")


class AllNodesMetricsResponse(BaseModel):
    """Aggregated metrics for all nodes"""
    nodes: list[NodeMetricsResponse]
    total_nodes: int
    healthy_nodes: int
    unhealthy_nodes: int
    disabled_nodes: int
    average_cpu_percent: float
    average_memory_percent: float
    average_disk_percent: float
    total_network_rx: int
    total_network_tx: int
