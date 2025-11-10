# WARP Support Feature

## Overview

WARP support enables routing specific traffic through Cloudflare WARP on a per-node basis. This is useful for accessing services that block proxy traffic (like Netflix, OpenAI, etc.) or for adding an additional layer of security.

**Current Status:** ✅ Panel-Side Complete | ⏳ Node-Side Integration Required

---

## Implementation Status

### ✅ Panel-Side (Master) - COMPLETE

The Marzneshin panel now has full API support for WARP configuration:

- **Models**: `WarpSettings` with routing modes and rules
- **Database**: `warp_config` JSON column in Node table
- **API Endpoints**: 2 endpoints for WARP management per node
- **Documentation**: Complete API documentation

### ⏳ Node-Side (Marznode) - PENDING

The following features require Marznode integration:

- WARP daemon installation and registration
- WARP+ license activation
- WARP status monitoring
- Automatic WARP outbound configuration in Xray
- Health checks and reconnection logic

---

## Architecture

### Panel-Side (Marzneshin)

```
┌─────────────────────────────────────────┐
│         Marzneshin Panel                │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │   WARP Configuration API          │ │
│  │   GET/PUT /nodes/{id}/warp        │ │
│  └───────────────────────────────────┘ │
│                  │                      │
│                  ▼                      │
│  ┌───────────────────────────────────┐ │
│  │   Database (warp_config)          │ │
│  │   Stores: enabled, routing_mode,  │ │
│  │   license_key, routing_rules      │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
                   │
                   │ gRPC
                   ▼
┌─────────────────────────────────────────┐
│         Marznode (Node Daemon)          │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │   WARP Daemon Manager             │ │
│  │   (TO BE IMPLEMENTED)             │ │
│  └───────────────────────────────────┘ │
│                  │                      │
│                  ▼                      │
│  ┌───────────────────────────────────┐ │
│  │   Cloudflare WARP Client          │ │
│  │   warp-svc / warp-cli             │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

## Data Models

### WarpSettings

```python
from enum import StrEnum
from pydantic import BaseModel, Field

class WarpRoutingMode(StrEnum):
    ALL = "all"          # Route all traffic through WARP
    GEOIP = "geoip"      # Route based on GeoIP rules
    CUSTOM = "custom"    # Custom routing rules

class WarpSettings(BaseModel):
    enabled: bool = False
    license_key: str | None = None  # WARP+ license key (optional)
    routing_mode: WarpRoutingMode = WarpRoutingMode.GEOIP
    routing_rules: list[str] = ["openai.com", "netflix.com", "spotify.com"]
    geoip_rules: list[str] = ["geosite:openai", "geosite:netflix"]
```

### Database Schema

```sql
-- Node table
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY,
    name VARCHAR(256) UNIQUE NOT NULL,
    address VARCHAR(256) NOT NULL,
    port INTEGER NOT NULL,
    -- ... other columns
    warp_config JSON,  -- Stores WarpSettings as JSON
    -- ...
);
```

---

## API Endpoints

### 1. Get Node WARP Configuration

**Endpoint:** `GET /api/nodes/{node_id}/warp`

**Authentication:** Required (Sudo Admin)

**Description:** Get the current WARP configuration for a specific node.

**Response:**

```json
{
  "enabled": false,
  "license_key": null,
  "routing_mode": "geoip",
  "routing_rules": ["openai.com", "netflix.com", "spotify.com"],
  "geoip_rules": ["geosite:openai", "geosite:netflix"]
}
```

**Example:**

```bash
curl -X GET "http://localhost:8000/api/nodes/1/warp" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### 2. Update Node WARP Configuration

**Endpoint:** `PUT /api/nodes/{node_id}/warp`

**Authentication:** Required (Sudo Admin)

**Description:** Update WARP configuration for a specific node.

**Request Body:**

```json
{
  "enabled": true,
  "license_key": "ABC123-DEF456-GHI789",
  "routing_mode": "custom",
  "routing_rules": ["openai.com", "*.openai.com", "chat.openai.com"],
  "geoip_rules": ["geosite:openai", "geosite:netflix", "geoip:us"]
}
```

**Response:**

```json
{
  "enabled": true,
  "license_key": "ABC123-DEF456-GHI789",
  "routing_mode": "custom",
  "routing_rules": ["openai.com", "*.openai.com", "chat.openai.com"],
  "geoip_rules": ["geosite:openai", "geosite:netflix", "geoip:us"]
}
```

**Example:**

```bash
curl -X PUT "http://localhost:8000/api/nodes/1/warp" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "routing_mode": "geoip",
    "routing_rules": ["openai.com", "netflix.com"],
    "geoip_rules": ["geosite:openai", "geosite:netflix"]
  }'
```

---

## WARP Routing Modes

### 1. ALL Mode

Routes **all traffic** through WARP outbound.

**Use Case:** Maximum privacy, all connections go through Cloudflare WARP.

**Configuration:**

```json
{
  "enabled": true,
  "routing_mode": "all"
}
```

**Xray Routing (Conceptual):**

```json
{
  "routing": {
    "rules": [
      {
        "type": "field",
        "network": "tcp,udp",
        "outboundTag": "warp"
      }
    ]
  },
  "outbounds": [
    {
      "tag": "warp",
      "protocol": "socks",
      "settings": {
        "servers": [{"address": "127.0.0.1", "port": 40000}]
      }
    }
  ]
}
```

---

### 2. GEOIP Mode (Default)

Routes traffic based on **GeoIP/GeoSite rules** through WARP.

**Use Case:** Route specific services (Netflix, OpenAI) through WARP while keeping other traffic direct or through proxy.

**Configuration:**

```json
{
  "enabled": true,
  "routing_mode": "geoip",
  "geoip_rules": ["geosite:openai", "geosite:netflix", "geoip:us"]
}
```

**Xray Routing (Conceptual):**

```json
{
  "routing": {
    "rules": [
      {
        "type": "field",
        "domain": ["geosite:openai", "geosite:netflix"],
        "outboundTag": "warp"
      },
      {
        "type": "field",
        "ip": ["geoip:us"],
        "outboundTag": "warp"
      }
    ]
  }
}
```

---

### 3. CUSTOM Mode

Routes traffic based on **custom domain rules** through WARP.

**Use Case:** Fine-grained control over which domains use WARP.

**Configuration:**

```json
{
  "enabled": true,
  "routing_mode": "custom",
  "routing_rules": [
    "openai.com",
    "*.openai.com",
    "chat.openai.com",
    "netflix.com",
    "*.netflix.com"
  ]
}
```

**Xray Routing (Conceptual):**

```json
{
  "routing": {
    "rules": [
      {
        "type": "field",
        "domain": [
          "openai.com",
          "domain:.openai.com",
          "chat.openai.com",
          "netflix.com",
          "domain:.netflix.com"
        ],
        "outboundTag": "warp"
      }
    ]
  }
}
```

---

## WARP+ License Key

WARP+ provides better performance and higher bandwidth compared to free WARP.

### Getting a WARP+ Key

1. Download the official WARP mobile app
2. Purchase WARP+ subscription
3. Get the license key from the app settings
4. Add it to the node WARP configuration

### Configuration

```json
{
  "enabled": true,
  "license_key": "YOUR-WARP-PLUS-KEY",
  "routing_mode": "geoip",
  "geoip_rules": ["geosite:openai", "geosite:netflix"]
}
```

The license key will be used by Marznode to register the WARP client.

---

## Use Cases

### 1. Accessing OpenAI Services

OpenAI blocks many proxy IPs. Route OpenAI traffic through WARP:

```bash
curl -X PUT "http://localhost:8000/api/nodes/1/warp" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "routing_mode": "custom",
    "routing_rules": ["openai.com", "*.openai.com", "chat.openai.com"]
  }'
```

---

### 2. Netflix and Streaming Services

Stream Netflix through WARP to avoid proxy blocks:

```bash
curl -X PUT "http://localhost:8000/api/nodes/1/warp" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "routing_mode": "geoip",
    "geoip_rules": ["geosite:netflix", "geosite:spotify"]
  }'
```

---

### 3. Additional Privacy Layer

Route all traffic through WARP for maximum privacy:

```bash
curl -X PUT "http://localhost:8000/api/nodes/1/warp" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "routing_mode": "all"
  }'
```

---

## Node Response with WARP Config

When fetching node details, WARP configuration is included:

**Endpoint:** `GET /api/nodes/{node_id}`

**Response:**

```json
{
  "id": 1,
  "name": "DE Node 1",
  "address": "192.168.1.100",
  "port": 53042,
  "status": "healthy",
  "xray_version": "1.8.4",
  "backends": [...],
  "warp_config": {
    "enabled": true,
    "license_key": null,
    "routing_mode": "geoip",
    "routing_rules": ["openai.com", "netflix.com"],
    "geoip_rules": ["geosite:openai", "geosite:netflix"]
  }
}
```

---

## Marznode Integration Requirements

To complete WARP support, Marznode must implement:

### 1. WARP Installation

- Install Cloudflare WARP client on node
- Register device with Cloudflare
- Handle WARP+ license activation

### 2. WARP Daemon Management

- Start/stop WARP daemon (`warp-svc`)
- Monitor WARP connection status
- Handle reconnection on failures

### 3. Xray Configuration

- Generate WARP outbound configuration
- Add WARP SOCKS5 proxy (default: `127.0.0.1:40000`)
- Inject routing rules based on `warp_config`
- Update Xray config dynamically

### 4. Status API

- Provide WARP connection status to panel
- Report WARP errors and issues
- Send health check results

### 5. gRPC Methods

New gRPC methods needed in Marznode:

```protobuf
service MarzNode {
  // Existing methods...

  rpc ConfigureWARP(WARPConfigRequest) returns (WARPConfigResponse);
  rpc GetWARPStatus(WARPStatusRequest) returns (WARPStatusResponse);
  rpc RestartWARP(RestartWARPRequest) returns (RestartWARPResponse);
}
```

---

## Installation Steps (Conceptual)

### On Marznode

1. **Install WARP Client:**

```bash
# Debian/Ubuntu
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
sudo apt update && sudo apt install cloudflare-warp
```

2. **Register WARP:**

```bash
warp-cli register
warp-cli set-mode proxy
warp-cli connect
```

3. **Activate WARP+ (Optional):**

```bash
warp-cli set-license YOUR-WARP-PLUS-KEY
```

4. **Configure WARP SOCKS Proxy:**

WARP creates a SOCKS5 proxy at `127.0.0.1:40000`

---

## Testing

### Test WARP Configuration

```bash
# 1. Get current WARP config
curl -X GET "http://localhost:8000/api/nodes/1/warp" \
  -H "Authorization: Bearer TOKEN"

# 2. Enable WARP with custom rules
curl -X PUT "http://localhost:8000/api/nodes/1/warp" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "routing_mode": "custom",
    "routing_rules": ["api.openai.com", "chat.openai.com"]
  }'

# 3. Verify configuration was saved
curl -X GET "http://localhost:8000/api/nodes/1/warp" \
  -H "Authorization: Bearer TOKEN"

# 4. Get node details (includes warp_config)
curl -X GET "http://localhost:8000/api/nodes/1" \
  -H "Authorization: Bearer TOKEN"
```

---

## Security Considerations

### 1. License Key Protection

- WARP+ license keys are stored in the database
- Should be encrypted at rest (TODO: implement encryption)
- Only accessible by sudo admins

### 2. WARP Traffic

- All WARP traffic goes through Cloudflare
- Cloudflare can see destination domains (not content due to TLS)
- Consider privacy implications for sensitive traffic

### 3. WARP Daemon Security

- WARP daemon runs as system service
- Ensure proper firewall rules
- Limit access to WARP SOCKS proxy port

---

## Troubleshooting

### WARP Configuration Not Applying

**Issue:** WARP config updated but not taking effect

**Solution:**
- Ensure Marznode integration is complete (currently pending)
- Check Marznode logs for WARP errors
- Verify WARP daemon is running on the node

### WARP Connection Failed

**Issue:** WARP daemon not connecting

**Solution:**
```bash
# On the node server
warp-cli status
warp-cli disconnect
warp-cli connect
```

### WARP+ License Not Activating

**Issue:** WARP+ license key not working

**Solution:**
```bash
# Verify license key format
warp-cli set-license YOUR-KEY
warp-cli account
```

---

## Benefits

### 1. Bypass Proxy Blocks

- Access services that block proxy IPs
- Netflix, OpenAI, Spotify, etc.

### 2. Additional Privacy

- Add Cloudflare WARP as additional layer
- Encrypted traffic to Cloudflare edge

### 3. Per-Node Configuration

- Configure WARP independently for each node
- Flexibility for different use cases

### 4. GeoIP-Based Routing

- Automatic routing based on destination
- No manual configuration for users

---

## Limitations

### Current Limitations

1. **Node-Side Not Implemented**: Requires Marznode integration
2. **No Status Monitoring**: Cannot check WARP connection status from panel
3. **Manual WARP Installation**: Marznode doesn't auto-install WARP yet
4. **No Auto-Reconnect**: WARP disconnections need manual intervention

### Future Improvements

1. Automatic WARP installation on nodes
2. Real-time WARP status in panel UI
3. Automatic reconnection on failures
4. WARP+ license validation
5. WARP bandwidth usage tracking
6. Multi-WARP support (multiple WARP accounts per node)

---

## Development Roadmap

### ✅ Phase 1: Panel-Side Foundation (COMPLETE)

- [x] Create `WarpSettings` model
- [x] Add `warp_config` column to Node table
- [x] Implement GET `/api/nodes/{node_id}/warp` endpoint
- [x] Implement PUT `/api/nodes/{node_id}/warp` endpoint
- [x] Add `warp_config` to `NodeResponse`
- [x] Write comprehensive documentation

### ⏳ Phase 2: Marznode Integration (TODO)

- [ ] WARP installation automation
- [ ] WARP daemon management
- [ ] gRPC methods for WARP control
- [ ] Xray WARP outbound configuration
- [ ] Routing rules injection

### ⏳ Phase 3: Status & Monitoring (TODO)

- [ ] WARP status API
- [ ] Health monitoring
- [ ] Automatic reconnection
- [ ] Error reporting to panel

### ⏳ Phase 4: Frontend UI (TODO)

- [ ] WARP configuration UI in node settings
- [ ] WARP status indicator
- [ ] Routing rules editor
- [ ] WARP+ license management UI

---

## Summary

✅ **Panel-Side (Master): COMPLETE**
- API endpoints: 2
- Data models: Complete
- Database schema: Ready
- Documentation: Comprehensive

⏳ **Node-Side (Marznode): PENDING**
- WARP daemon integration required
- Xray configuration needed
- Status monitoring to implement

🎯 **Next Steps:**
1. Begin Marznode WARP integration
2. Implement WARP installation automation
3. Add gRPC methods for WARP control
4. Create frontend UI for WARP management

---

**Panel-side WARP implementation is production-ready!** 🎉

The foundation is solid and ready for Marznode integration to make WARP fully operational.
