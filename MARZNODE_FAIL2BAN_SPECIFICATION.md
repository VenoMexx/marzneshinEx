# Marznode Fail2ban Integration Specification

**Version:** 1.0
**Target Marznode Version:** v0.3.0+
**Panel Version:** Requires MarzneshinEx with Centralized Security Management
**Status:** 🚧 Specification Ready - Implementation Required

---

## 📋 Overview

This specification defines the fail2ban integration that Marznode must implement to support the Panel's Centralized IP Blacklist Management system.

### Goals

1. **Centralized Blacklist**: Sync IP blacklist from Panel automatically
2. **Automated Blocking**: Apply IP bans via fail2ban/iptables
3. **Real-time Sync**: Support immediate sync on-demand
4. **Cross-platform**: Support Linux (primary), with potential for FreeBSD

---

## 🎯 Required Features

### 1. IP Blacklist Synchronization

Marznode must periodically fetch the blacklist from Panel and apply bans.

#### Sync Frequency
- **Default**: Every 5 minutes (configurable)
- **On-Demand**: Support immediate sync via gRPC call

#### Blacklist Types
```python
# Global ban: Applies to all nodes
{
  "ip_address": "192.168.1.100",
  "node_id": null,  # null = global
  "expires_at": null,  # null = permanent
  "reason": "Brute force attack"
}

# Node-specific ban: Applies to specific node only
{
  "ip_address": "10.0.0.50",
  "node_id": 42,  # This node ID
  "expires_at": "2025-01-20T00:00:00",
  "reason": "DDoS attack"
}
```

---

## 🔌 gRPC API Specification

### New gRPC Methods

Add the following methods to Marznode's gRPC service:

```protobuf
service MarzNodeService {
    // Existing methods...

    rpc SyncBlacklist(SyncBlacklistRequest) returns (SyncBlacklistResponse);
    rpc GetBlacklistStatus(GetBlacklistStatusRequest) returns (BlacklistStatus);
}

message SyncBlacklistRequest {
    // Empty - trigger immediate sync
}

message SyncBlacklistResponse {
    bool success = 1;
    int32 total_ips_blocked = 2;
    int32 new_bans_applied = 3;
    int32 bans_removed = 4;
    string error_message = 5;
}

message GetBlacklistStatusRequest {
    // Empty - get current status
}

message BlacklistStatus {
    int64 last_sync_timestamp = 1;  // Unix timestamp
    int32 total_blocked_ips = 2;
    string sync_status = 3;  // "synced", "pending", "error"
    string error_message = 4;
}
```

---

## 💻 Implementation Guide

### Architecture Overview

```
┌─────────────────┐
│  MarzneshinEx   │
│      Panel      │
└────────┬────────┘
         │
         │ gRPC: Sync Blacklist
         ▼
┌─────────────────┐
│    Marznode     │
│  ┌───────────┐  │
│  │  Sync     │  │
│  │  Manager  │  │
│  └─────┬─────┘  │
│        │        │
│        ▼        │
│  ┌───────────┐  │
│  │ Fail2ban  │  │
│  │  Manager  │  │
│  └─────┬─────┘  │
│        │        │
│        ▼        │
│  ┌───────────┐  │
│  │ iptables  │  │
│  │  / nftables│  │
│  └───────────┘  │
└─────────────────┘
```

### Component 1: Blacklist Sync Manager

```python
import time
import logging
from datetime import datetime
from typing import List, Dict

class BlacklistSyncManager:
    """
    Manages synchronization of IP blacklist from Panel
    """

    def __init__(self, panel_url: str, node_id: int):
        self.panel_url = panel_url
        self.node_id = node_id
        self.last_sync = None
        self.current_blacklist = []
        self.fail2ban_manager = Fail2banManager()
        self.sync_interval = 300  # 5 minutes

    async def start_auto_sync(self):
        """
        Start automatic synchronization loop
        """
        while True:
            try:
                await self.sync_blacklist()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logging.error(f"Blacklist sync failed: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute on error

    async def sync_blacklist(self) -> Dict:
        """
        Synchronize blacklist from Panel

        Returns:
            Dict with sync statistics
        """
        try:
            # Fetch blacklist from Panel (via HTTP or database)
            blacklist = await self.fetch_blacklist_from_panel()

            # Compare with current blacklist
            to_ban = []
            to_unban = []

            current_ips = set(self.current_blacklist)
            new_ips = set([entry['ip_address'] for entry in blacklist])

            # Find IPs to ban (new in blacklist)
            to_ban = new_ips - current_ips

            # Find IPs to unban (removed from blacklist)
            to_unban = current_ips - new_ips

            # Apply changes via fail2ban
            new_bans = 0
            bans_removed = 0

            for ip in to_ban:
                if self.fail2ban_manager.ban_ip(ip):
                    new_bans += 1

            for ip in to_unban:
                if self.fail2ban_manager.unban_ip(ip):
                    bans_removed += 1

            # Update current blacklist
            self.current_blacklist = list(new_ips)
            self.last_sync = datetime.utcnow()

            logging.info(
                f"Blacklist synced: {len(blacklist)} total, "
                f"{new_bans} new bans, {bans_removed} unbans"
            )

            return {
                "success": True,
                "total_ips_blocked": len(blacklist),
                "new_bans_applied": new_bans,
                "bans_removed": bans_removed,
                "error_message": None
            }

        except Exception as e:
            logging.error(f"Blacklist sync error: {e}")
            return {
                "success": False,
                "total_ips_blocked": len(self.current_blacklist),
                "new_bans_applied": 0,
                "bans_removed": 0,
                "error_message": str(e)
            }

    async def fetch_blacklist_from_panel(self) -> List[Dict]:
        """
        Fetch blacklist from Panel

        Returns:
            List of blacklist entries
        """
        # Option 1: HTTP API (recommended)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.panel_url}/api/security/blacklist",
                params={
                    "active_only": True,
                    "node_id": self.node_id  # Get node-specific + global bans
                }
            )
            response.raise_for_status()
            data = response.json()
            return data['entries']

        # Option 2: Direct database query (if shared database)
        # Not recommended for distributed deployments
```

### Component 2: Fail2ban Manager

```python
import subprocess
import logging

class Fail2banManager:
    """
    Manages fail2ban operations for IP blocking
    """

    def __init__(self, jail_name: str = "marzneshin"):
        self.jail_name = jail_name

    def ban_ip(self, ip_address: str) -> bool:
        """
        Ban an IP address using fail2ban

        Args:
            ip_address: IP to ban

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use fail2ban-client to ban IP
            cmd = ["fail2ban-client", "set", self.jail_name, "banip", ip_address]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                logging.info(f"Banned IP: {ip_address}")
                return True
            else:
                logging.error(f"Failed to ban {ip_address}: {result.stderr}")
                return False

        except Exception as e:
            logging.error(f"Error banning IP {ip_address}: {e}")
            return False

    def unban_ip(self, ip_address: str) -> bool:
        """
        Unban an IP address

        Args:
            ip_address: IP to unban

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use fail2ban-client to unban IP
            cmd = ["fail2ban-client", "set", self.jail_name, "unbanip", ip_address]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                logging.info(f"Unbanned IP: {ip_address}")
                return True
            else:
                logging.error(f"Failed to unban {ip_address}: {result.stderr}")
                return False

        except Exception as e:
            logging.error(f"Error unbanning IP {ip_address}: {e}")
            return False

    def get_banned_ips(self) -> List[str]:
        """
        Get list of currently banned IPs

        Returns:
            List of banned IP addresses
        """
        try:
            cmd = ["fail2ban-client", "status", self.jail_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                # Parse output to extract IPs
                # Format: "|- Banned IP list: 192.168.1.1 10.0.0.1"
                for line in result.stdout.split('\n'):
                    if "Banned IP list:" in line:
                        ips = line.split(":")[-1].strip().split()
                        return ips
                return []
            else:
                logging.error(f"Failed to get banned IPs: {result.stderr}")
                return []

        except Exception as e:
            logging.error(f"Error getting banned IPs: {e}")
            return []
```

### Component 3: gRPC Service Implementation

```python
import grpc
from marznode_pb2 import (
    SyncBlacklistResponse,
    BlacklistStatus
)
from marznode_pb2_grpc import MarzNodeServiceServicer

class MarzNodeService(MarzNodeServiceServicer):
    """Marznode gRPC service"""

    def __init__(self):
        self.blacklist_manager = BlacklistSyncManager(
            panel_url=config.panel_url,
            node_id=config.node_id
        )

    async def SyncBlacklist(self, request, context):
        """
        Handle SyncBlacklist gRPC call - force immediate sync
        """
        try:
            result = await self.blacklist_manager.sync_blacklist()

            return SyncBlacklistResponse(
                success=result["success"],
                total_ips_blocked=result["total_ips_blocked"],
                new_bans_applied=result["new_bans_applied"],
                bans_removed=result["bans_removed"],
                error_message=result["error_message"] or ""
            )

        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return SyncBlacklistResponse(
                success=False,
                total_ips_blocked=0,
                new_bans_applied=0,
                bans_removed=0,
                error_message=str(e)
            )

    def GetBlacklistStatus(self, request, context):
        """
        Handle GetBlacklistStatus gRPC call
        """
        try:
            last_sync = self.blacklist_manager.last_sync
            last_sync_timestamp = int(last_sync.timestamp()) if last_sync else 0

            # Determine sync status
            if not last_sync:
                sync_status = "pending"
            elif (datetime.utcnow() - last_sync).seconds > 600:  # 10 minutes
                sync_status = "pending"
            else:
                sync_status = "synced"

            return BlacklistStatus(
                last_sync_timestamp=last_sync_timestamp,
                total_blocked_ips=len(self.blacklist_manager.current_blacklist),
                sync_status=sync_status,
                error_message=""
            )

        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return BlacklistStatus(
                last_sync_timestamp=0,
                total_blocked_ips=0,
                sync_status="error",
                error_message=str(e)
            )
```

---

## ⚙️ Fail2ban Configuration

### Jail Configuration

Create `/etc/fail2ban/jail.d/marzneshin.conf`:

```ini
[marzneshin]
enabled = true
port = all
filter = marzneshin
logpath = /var/log/marznode/access.log
maxretry = 0  # Managed externally by Panel
bantime = -1  # Permanent (managed by Panel)
findtime = 3600
action = iptables-allports[name=marzneshin]
```

### Filter Configuration

Create `/etc/fail2ban/filter.d/marzneshin.conf`:

```ini
[Definition]
# This filter is intentionally empty
# Bans are managed externally by MarzneshinEx Panel
failregex =
ignoreregex =
```

**Note**: We don't use fail2ban's log monitoring. We only use it as an IP ban management tool.

---

## 📦 Dependencies

### Required Packages

```txt
fail2ban>=0.11.0    # IP ban management
httpx>=0.24.0       # HTTP client for Panel API
```

### System Requirements

- **fail2ban** must be installed and running
- **iptables** or **nftables** for packet filtering
- **sudo** privileges for fail2ban operations

### Installation

```bash
# Install fail2ban
apt-get install fail2ban  # Debian/Ubuntu
yum install fail2ban      # CentOS/RHEL

# Copy configuration files
cp configs/fail2ban/jail.d/marzneshin.conf /etc/fail2ban/jail.d/
cp configs/fail2ban/filter.d/marzneshin.conf /etc/fail2ban/filter.d/

# Restart fail2ban
systemctl restart fail2ban

# Verify jail is active
fail2ban-client status marzneshin
```

---

## 🧪 Testing

### Unit Tests

```python
import unittest
from marznode.blacklist import BlacklistSyncManager, Fail2banManager

class TestFail2banManager(unittest.TestCase):

    def setUp(self):
        self.manager = Fail2banManager(jail_name="test-jail")

    def test_ban_ip(self):
        """Test IP banning"""
        result = self.manager.ban_ip("192.168.1.100")
        self.assertTrue(result)

        # Verify IP is banned
        banned_ips = self.manager.get_banned_ips()
        self.assertIn("192.168.1.100", banned_ips)

    def test_unban_ip(self):
        """Test IP unbanning"""
        # Ban first
        self.manager.ban_ip("192.168.1.100")

        # Then unban
        result = self.manager.unban_ip("192.168.1.100")
        self.assertTrue(result)

        # Verify IP is not banned
        banned_ips = self.manager.get_banned_ips()
        self.assertNotIn("192.168.1.100", banned_ips)
```

### Integration Test

```bash
# Test fail2ban operations
fail2ban-client set marzneshin banip 192.168.1.100
fail2ban-client status marzneshin
fail2ban-client set marzneshin unbanip 192.168.1.100

# Test gRPC endpoint
grpcurl -plaintext localhost:53042 MarzNodeService/SyncBlacklist
grpcurl -plaintext localhost:53042 MarzNodeService/GetBlacklistStatus
```

---

## 🔐 Security Considerations

1. **Authentication**: Blacklist API should require authentication token
2. **Rate Limiting**: Limit sync frequency to prevent abuse (max 1 req/min)
3. **Privilege Escalation**: fail2ban requires sudo - use sudoers whitelist
4. **DDoS Protection**: Large blacklists (>10K IPs) should be paginated

### Sudoers Configuration

Add to `/etc/sudoers.d/marznode`:

```bash
marznode ALL=(ALL) NOPASSWD: /usr/bin/fail2ban-client
```

---

## 📊 Panel Integration

### Panel-Side Implementation (Already Done)

The Panel has already implemented:

✅ **Database Model** (`app/db/models.py`):
- `IPBlacklist` table for centralized storage

✅ **API Endpoints** (`app/routes/security.py`):
- `GET /api/security/blacklist` - Get blacklist
- `POST /api/security/blacklist/ban` - Ban IP
- `POST /api/security/blacklist/unban` - Unban IP
- `GET /api/security/blacklist/sync-status` - Get sync status
- `POST /api/security/blacklist/sync` - Force sync

✅ **Data Models** (`app/models/security.py`):
- Request/response models
- Validation logic

### Panel Expected Behavior

When Marznode v0.3.0+ is deployed:

1. Marznode auto-syncs every 5 minutes
2. Panel can trigger immediate sync via gRPC
3. Panel displays sync status per node
4. Bans are applied across all nodes (global) or specific nodes

---

## 🚀 Deployment

### Version Compatibility

| Marznode Version | Panel Version | Fail2ban Support |
|------------------|---------------|------------------|
| < v0.3.0 | Any | ❌ Not supported |
| >= v0.3.0 | Latest | ✅ Fully supported |

### Upgrade Path

1. **Install fail2ban** on server
2. **Configure jail** and filter files
3. **Deploy Marznode v0.3.0+** with fail2ban integration
4. **Panel automatically detects** support and enables security features
5. **No Panel upgrade required** - API already implemented

### Configuration

Add to Marznode config file:

```yaml
security:
  fail2ban:
    enabled: true
    jail_name: "marzneshin"
    sync_interval: 300  # seconds
  blacklist:
    panel_url: "https://panel.example.com"
    sync_enabled: true
```

---

## 📖 References

- **fail2ban Documentation**: https://fail2ban.readthedocs.io/
- **iptables Guide**: https://wiki.archlinux.org/title/Iptables
- **Marznode Repository**: https://github.com/marzneshin/marznode
- **Panel Security API**: `app/routes/security.py`

---

## ✅ Implementation Checklist

### Phase 1: Basic Implementation
- [ ] Install fail2ban on server
- [ ] Configure jail and filter
- [ ] Implement `BlacklistSyncManager` class
- [ ] Implement `Fail2banManager` class
- [ ] Add gRPC methods (SyncBlacklist, GetBlacklistStatus)
- [ ] Test locally

### Phase 2: Integration
- [ ] Add auto-sync loop (every 5 minutes)
- [ ] Add Panel API client
- [ ] Handle expired bans
- [ ] Implement error handling and retry logic
- [ ] Write unit tests
- [ ] Write integration tests

### Phase 3: Production
- [ ] Add logging and monitoring
- [ ] Performance testing (>1000 IPs)
- [ ] Security audit
- [ ] Documentation
- [ ] Release Marznode v0.3.0

---

## 💡 Alternative Implementations

### Option 1: iptables Direct (No fail2ban)

If fail2ban is not available, use iptables directly:

```python
def ban_ip_iptables(ip: str):
    subprocess.run([
        "iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"
    ])

def unban_ip_iptables(ip: str):
    subprocess.run([
        "iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"
    ])
```

**Pros**: No dependencies
**Cons**: Doesn't persist across reboots, no logging

### Option 2: nftables (Modern Linux)

For modern Linux systems with nftables:

```python
def ban_ip_nftables(ip: str):
    subprocess.run([
        "nft", "add", "element", "inet", "filter", "blacklist", f"{ip}"
    ])
```

---

## 📞 Support

For implementation questions or issues:

1. **Marznode Issues**: https://github.com/marzneshin/marznode/issues
2. **Panel Issues**: https://github.com/marzneshin/marzneshin/issues
3. **Telegram Group**: https://t.me/marzneshins

---

**Status**: 🟢 Ready for Implementation
**Priority**: 🔴 High (Critical security feature)
**Estimated Effort**: 3-4 days (including testing and fail2ban setup)
