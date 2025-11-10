# Marznode System Metrics Collection Specification

**Version:** 1.0
**Target Marznode Version:** v0.3.0+
**Panel Version:** Requires MarzneshinEx with Advanced Monitoring Support
**Status:** 🚧 Specification Ready - Implementation Required

---

## 📋 Overview

This specification defines the system metrics collection feature that Marznode must implement to support the Panel's Advanced Multi-Node Monitoring Dashboard.

### Goals

1. **Real-time Monitoring**: Collect system metrics (CPU, RAM, Disk, Network) in real-time
2. **gRPC API**: Expose metrics via gRPC endpoint for Panel to consume
3. **Lightweight**: Minimal performance overhead (<1% CPU, <10MB RAM)
4. **Cross-platform**: Support Linux (primary), with potential for FreeBSD/Windows

---

## 🎯 Required Features

### 1. System Metrics Collection

Marznode must collect the following system metrics:

#### CPU Metrics
```python
cpu_percent: float       # Current CPU usage percentage (0-100)
cpu_cores: int          # Number of CPU cores
```

**Implementation Notes:**
- Use `psutil.cpu_percent(interval=1)` for accurate measurement
- Average over 1-second window
- Exclude idle/wait time

#### Memory Metrics
```python
memory_total: int        # Total RAM in bytes
memory_used: int         # Used RAM in bytes (excluding cache/buffers)
memory_percent: float    # Memory usage percentage (0-100)
```

**Implementation Notes:**
- Use `psutil.virtual_memory()`
- `memory_used` should exclude cache and buffers (actual application usage)
- `memory_percent = (memory_used / memory_total) * 100`

#### Disk Metrics
```python
disk_total: int          # Total disk space in bytes
disk_used: int           # Used disk space in bytes
disk_percent: float      # Disk usage percentage (0-100)
```

**Implementation Notes:**
- Monitor the filesystem where Marznode is installed
- Use `psutil.disk_usage('/')`
- Include all mounted partitions or just root partition (configurable)

#### Network Metrics
```python
network_rx_bytes: int    # Total bytes received since boot
network_tx_bytes: int    # Total bytes transmitted since boot
```

**Implementation Notes:**
- Use `psutil.net_io_counters()`
- Cumulative counters (monotonically increasing)
- Panel will calculate delta for rate calculation

#### System Metrics
```python
uptime_seconds: int      # System uptime in seconds
timestamp: int           # Unix timestamp of collection (seconds)
```

**Implementation Notes:**
- `uptime_seconds`: Time since last system boot
- `timestamp`: UTC Unix timestamp when metrics were collected

---

## 🔌 gRPC API Specification

### New gRPC Method

Add the following method to Marznode's gRPC service:

```protobuf
service MarzNodeService {
    // Existing methods...

    rpc GetSystemMetrics(GetSystemMetricsRequest) returns (SystemMetrics);
}

message GetSystemMetricsRequest {
    // Empty - no parameters needed
}

message SystemMetrics {
    float cpu_percent = 1;
    int32 cpu_cores = 2;
    int64 memory_total = 3;
    int64 memory_used = 4;
    float memory_percent = 5;
    int64 disk_total = 6;
    int64 disk_used = 7;
    float disk_percent = 8;
    int64 network_rx_bytes = 9;
    int64 network_tx_bytes = 10;
    int64 uptime_seconds = 11;
    int64 timestamp = 12;
}
```

### API Behavior

**Request:**
```json
{}  // Empty request
```

**Response (Success):**
```json
{
  "cpu_percent": 45.2,
  "cpu_cores": 4,
  "memory_total": 8589934592,
  "memory_used": 4294967296,
  "memory_percent": 50.0,
  "disk_total": 107374182400,
  "disk_used": 53687091200,
  "disk_percent": 50.0,
  "network_rx_bytes": 1073741824,
  "network_tx_bytes": 2147483648,
  "uptime_seconds": 864000,
  "timestamp": 1704931200
}
```

**Response (Error):**
```json
{
  "code": "UNAVAILABLE",
  "message": "Failed to collect metrics: [error details]"
}
```

---

## 💻 Implementation Guide

### Python Implementation (Recommended)

```python
import psutil
import time
from typing import Dict

class SystemMetricsCollector:
    """
    Collects system metrics for Marznode monitoring
    """

    def collect_metrics(self) -> Dict:
        """
        Collect all system metrics

        Returns:
            Dict containing all metrics
        """
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_cores = psutil.cpu_count()

        # Memory metrics
        mem = psutil.virtual_memory()
        memory_total = mem.total
        memory_used = mem.used
        memory_percent = mem.percent

        # Disk metrics (root partition)
        disk = psutil.disk_usage('/')
        disk_total = disk.total
        disk_used = disk.used
        disk_percent = disk.percent

        # Network metrics
        net = psutil.net_io_counters()
        network_rx_bytes = net.bytes_recv
        network_tx_bytes = net.bytes_sent

        # System uptime
        uptime_seconds = int(time.time() - psutil.boot_time())

        # Current timestamp
        timestamp = int(time.time())

        return {
            "cpu_percent": cpu_percent,
            "cpu_cores": cpu_cores,
            "memory_total": memory_total,
            "memory_used": memory_used,
            "memory_percent": memory_percent,
            "disk_total": disk_total,
            "disk_used": disk_used,
            "disk_percent": disk_percent,
            "network_rx_bytes": network_rx_bytes,
            "network_tx_bytes": network_tx_bytes,
            "uptime_seconds": uptime_seconds,
            "timestamp": timestamp
        }
```

### gRPC Service Implementation

```python
import grpc
from concurrent import futures
from marznode_pb2 import SystemMetrics
from marznode_pb2_grpc import MarzNodeServiceServicer

class MarzNodeService(MarzNodeServiceServicer):
    """Marznode gRPC service"""

    def __init__(self):
        self.metrics_collector = SystemMetricsCollector()

    def GetSystemMetrics(self, request, context):
        """
        Handle GetSystemMetrics gRPC call
        """
        try:
            metrics = self.metrics_collector.collect_metrics()

            return SystemMetrics(
                cpu_percent=metrics["cpu_percent"],
                cpu_cores=metrics["cpu_cores"],
                memory_total=metrics["memory_total"],
                memory_used=metrics["memory_used"],
                memory_percent=metrics["memory_percent"],
                disk_total=metrics["disk_total"],
                disk_used=metrics["disk_used"],
                disk_percent=metrics["disk_percent"],
                network_rx_bytes=metrics["network_rx_bytes"],
                network_tx_bytes=metrics["network_tx_bytes"],
                uptime_seconds=metrics["uptime_seconds"],
                timestamp=metrics["timestamp"]
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(f"Failed to collect metrics: {str(e)}")
            return SystemMetrics()
```

---

## 📦 Dependencies

### Required Python Packages

```txt
psutil>=5.9.0    # System metrics collection
```

### Installation

```bash
pip install psutil>=5.9.0
```

---

## ⚙️ Configuration

### Optional Configuration Parameters

Add to Marznode config file (e.g., `config.yaml`):

```yaml
monitoring:
  enabled: true                    # Enable/disable metrics collection
  disk_path: "/"                   # Disk path to monitor (default: root)
  collection_interval: 5           # Metrics collection interval in seconds (for caching)
  cache_ttl: 5                     # Cache TTL in seconds
```

### Performance Considerations

- **CPU Overhead**: ~0.1-0.5% per metrics collection
- **Memory Overhead**: ~5-10MB additional RAM usage
- **Network Overhead**: ~500 bytes per request
- **Recommended Polling Interval**: Panel should poll every 5-10 seconds

---

## 🧪 Testing

### Unit Tests

```python
import unittest
from marznode.metrics import SystemMetricsCollector

class TestSystemMetrics(unittest.TestCase):

    def setUp(self):
        self.collector = SystemMetricsCollector()

    def test_collect_metrics(self):
        """Test metrics collection"""
        metrics = self.collector.collect_metrics()

        # Validate all fields exist
        required_fields = [
            "cpu_percent", "cpu_cores", "memory_total", "memory_used",
            "memory_percent", "disk_total", "disk_used", "disk_percent",
            "network_rx_bytes", "network_tx_bytes", "uptime_seconds", "timestamp"
        ]
        for field in required_fields:
            self.assertIn(field, metrics)

        # Validate ranges
        self.assertGreaterEqual(metrics["cpu_percent"], 0)
        self.assertLessEqual(metrics["cpu_percent"], 100)
        self.assertGreater(metrics["cpu_cores"], 0)
        self.assertGreater(metrics["memory_total"], 0)
        self.assertGreaterEqual(metrics["memory_percent"], 0)
        self.assertLessEqual(metrics["memory_percent"], 100)
```

### Integration Test

```bash
# Test gRPC endpoint
grpcurl -plaintext localhost:53042 MarzNodeService/GetSystemMetrics
```

**Expected Output:**
```json
{
  "cpuPercent": 45.2,
  "cpuCores": 4,
  "memoryTotal": "8589934592",
  "memoryUsed": "4294967296",
  "memoryPercent": 50,
  "diskTotal": "107374182400",
  "diskUsed": "53687091200",
  "diskPercent": 50,
  "networkRxBytes": "1073741824",
  "networkTxBytes": "2147483648",
  "uptimeSeconds": "864000",
  "timestamp": "1704931200"
}
```

---

## 🔐 Security Considerations

1. **Access Control**: Metrics endpoint should use same authentication as other gRPC methods
2. **Rate Limiting**: Consider rate limiting to prevent DoS (recommended: 1 req/sec per Panel)
3. **Information Disclosure**: Metrics reveal system resources but not sensitive data (acceptable risk)
4. **Privilege Level**: Metrics collection doesn't require root privileges

---

## 📊 Panel Integration

### Panel-Side Implementation (Already Done)

The Panel has already implemented:

✅ **Data Models** (`app/models/node.py`):
- `SystemMetrics` - Metrics data structure
- `NodeHealthScore` - Health scoring algorithm
- `NodeMetricsResponse` - Single node response
- `AllNodesMetricsResponse` - Multi-node aggregation

✅ **API Endpoints** (`app/routes/node.py`):
- `GET /nodes/{node_id}/metrics` - Single node metrics
- `GET /nodes/metrics` - All nodes metrics

✅ **Health Scoring Algorithm**:
- CPU Score: `100 - cpu_percent`
- Memory Score: `100 - memory_percent`
- Disk Score: `100 - disk_percent`
- Overall Score: Weighted average (30% CPU, 30% Memory, 30% Disk, 10% Network)

### Panel Expected Behavior

When Marznode v0.3.0+ is deployed:

1. Panel will call `node.get_system_metrics()` via gRPC
2. Panel will calculate health scores
3. Panel will aggregate metrics across all nodes
4. Panel will display in dashboard UI

---

## 🚀 Deployment

### Version Compatibility

| Marznode Version | Panel Version | Metrics Support |
|------------------|---------------|-----------------|
| < v0.3.0 | Any | ❌ Not supported |
| >= v0.3.0 | Latest | ✅ Fully supported |

### Upgrade Path

1. **Deploy Marznode v0.3.0+** with metrics support
2. **Panel automatically detects** support via gRPC method availability
3. **No Panel upgrade required** - API already implemented

### Backward Compatibility

- Old Marznode versions will return error "Method not found"
- Panel handles gracefully with error message
- No breaking changes for existing functionality

---

## 📖 References

- **psutil Documentation**: https://psutil.readthedocs.io/
- **gRPC Python**: https://grpc.io/docs/languages/python/
- **Marznode Repository**: https://github.com/marzneshin/marznode
- **Panel Monitoring API**: `app/routes/node.py` (lines 285-492)

---

## ✅ Implementation Checklist

### Phase 1: Basic Implementation
- [ ] Install `psutil` dependency
- [ ] Implement `SystemMetricsCollector` class
- [ ] Add `GetSystemMetrics` to gRPC proto file
- [ ] Implement gRPC service method
- [ ] Test locally with `grpcurl`

### Phase 2: Configuration & Testing
- [ ] Add configuration options to config file
- [ ] Implement caching (optional)
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Update Marznode documentation

### Phase 3: Deployment
- [ ] Release Marznode v0.3.0
- [ ] Update Marznode installation scripts
- [ ] Notify MarzneshinEx Panel users
- [ ] Monitor performance impact

---

## 💡 Future Enhancements

### Phase 2 (Future):
- **Per-process metrics**: Xray-core specific resource usage
- **Historical data**: Store metrics in time-series database
- **Alerts**: Threshold-based alerting (>90% disk usage, etc.)
- **Custom metrics**: Extensible metric collection

### Phase 3 (Future):
- **Distributed tracing**: Track requests across nodes
- **Anomaly detection**: ML-based anomaly detection
- **Predictive scaling**: Auto-scaling recommendations

---

## 📞 Support

For implementation questions or issues:

1. **Marznode Issues**: https://github.com/marzneshin/marznode/issues
2. **Panel Issues**: https://github.com/marzneshin/marzneshin/issues
3. **Telegram Group**: https://t.me/marzneshins

---

**Status**: 🟢 Ready for Implementation
**Priority**: 🔴 High (Core feature for multi-node deployments)
**Estimated Effort**: 2-3 days (including testing)

