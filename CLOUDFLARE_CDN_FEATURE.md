# Cloudflare/CDN Integration Feature

## Overview

This feature adds comprehensive Cloudflare and CDN integration to Marzneshin, enabling automatic CDN IP management, DNS management through Cloudflare API, and automatic generation of CDN-optimized subscription configurations.

## Features

### 1. Cloudflare API Integration
- **API Token Management**: Secure storage and validation of Cloudflare API tokens
- **Zone Management**: List and manage Cloudflare zones (domains)
- **DNS Record Management**: Create, update, and delete DNS records via API
- **Automatic Token Verification**: Validate API credentials before use

### 2. CDN IP Management
- **Optimal IP Selection**: Automatically test and select fastest CDN IPs based on latency
- **Preferred IPs**: Configure custom preferred CDN IP addresses
- **CDN-Compatible Ports**: Support for all Cloudflare CDN ports (80, 443, 8080, 8443, 2052, 2053, 2082, 2083, 2086, 2087, 2095, 2096)
- **Real-time IP Testing**: Concurrent latency testing to find optimal IPs

### 3. Automatic CDN Configuration Generation
- **Smart Config Generation**: Automatically generates CDN configs for WebSocket-based protocols
- **Protocol Support**: Works with WS, HTTP Upgrade, and SplitHTTP transports
- **TLS Enforcement**: Ensures TLS is enabled for all CDN configurations
- **Subscription Integration**: CDN configs automatically added to user subscriptions

## Implementation Details

### Backend Components

#### 1. Models (app/models/settings.py)

**CloudflareSettings:**
```python
class CloudflareSettings(BaseModel):
    enabled: bool = False
    api_token: str | None = None
    email: str | None = None
    default_zone_id: str | None = None
    domains: list[CloudflareDomain] = []
    auto_cdn_ip: bool = True
    cdn_ports: list[int] = [80, 443, 8080, 8443, 2052, 2053, 2082, 2083, 2086, 2087, 2095, 2096]
    preferred_ips: list[str] = []
```

**CloudflareDomain:**
```python
class CloudflareDomain(BaseModel):
    domain: str
    zone_id: str
    enabled: bool = True
```

**CloudflareIPInfo:**
```python
class CloudflareIPInfo(BaseModel):
    ip: str
    latency_ms: float | None = None
    location: str | None = None
```

#### 2. Cloudflare API Client (app/utils/cloudflare.py)

**CloudflareAPI Class:**
- `verify_token()`: Verify API token validity
- `list_zones()`: List all zones in account
- `get_zone_details(zone_id)`: Get specific zone details
- `list_dns_records(zone_id)`: List DNS records for a zone
- `create_dns_record()`: Create new DNS record with CDN support
- `update_dns_record()`: Update existing DNS record
- `delete_dns_record()`: Delete DNS record

**Utility Functions:**
- `get_optimal_cdn_ips(count)`: Test and return fastest CDN IPs
- `get_cloudflare_cdn_ips()`: Get list of known Cloudflare CDN IPs
- `generate_cdn_configs_for_user()`: Generate CDN configs for user

#### 3. API Endpoints (app/routes/system.py)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/system/settings/cloudflare` | Get Cloudflare settings |
| PUT | `/api/system/settings/cloudflare` | Update Cloudflare settings |
| POST | `/api/system/cloudflare/verify-token` | Verify API token |
| GET | `/api/system/cloudflare/zones` | List Cloudflare zones |
| GET | `/api/system/cloudflare/zones/{zone_id}/dns-records` | List DNS records |
| POST | `/api/system/cloudflare/zones/{zone_id}/dns-records` | Create DNS record |
| GET | `/api/system/cdn/optimal-ips` | Get optimal CDN IPs |
| GET | `/api/system/cdn/available-ips` | Get available CDN IPs |

#### 4. Subscription Integration (app/utils/share.py)

**Enhanced generate_subscription():**
- New parameter: `include_cdn_configs: bool = False`
- Automatically generates CDN variants for WebSocket protocols
- Adds `[CDN]` suffix to CDN config remarks
- Integrates with CloudflareSettings from database

**New Function: generate_cdn_configs()**
- Reads Cloudflare settings from database
- Checks if CDN is enabled
- Generates CDN configs only for WebSocket-based transports
- Uses configured preferred IPs or defaults to Cloudflare CDN IPs

## Usage

### 1. Configure Cloudflare Settings

**Via API:**
```bash
curl -X PUT http://localhost:8000/api/system/settings/cloudflare \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "api_token": "YOUR_CLOUDFLARE_API_TOKEN",
    "email": "your@email.com",
    "auto_cdn_ip": true,
    "preferred_ips": ["104.16.0.0", "172.67.0.0"],
    "cdn_ports": [443, 8443, 2053, 2083, 2087, 2096]
  }'
```

### 2. Verify API Token

```bash
curl -X POST http://localhost:8000/api/system/cloudflare/verify-token \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "valid": true
}
```

### 3. List Cloudflare Zones

```bash
curl http://localhost:8000/api/system/cloudflare/zones \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Get Optimal CDN IPs

```bash
curl http://localhost:8000/api/system/cdn/optimal-ips?count=10 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
[
  {
    "ip": "104.16.0.0",
    "latency_ms": 45.2,
    "location": null
  },
  {
    "ip": "172.67.0.0",
    "latency_ms": 52.8,
    "location": null
  }
]
```

### 5. Manage DNS Records

**Create DNS Record:**
```bash
curl -X POST http://localhost:8000/api/system/cloudflare/zones/ZONE_ID/dns-records \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "record_type": "A",
    "name": "proxy",
    "content": "YOUR_SERVER_IP",
    "proxied": true
  }'
```

## Subscription Enhancement

When Cloudflare/CDN is enabled, user subscriptions automatically include CDN-optimized configurations:

**Example Subscription Links:**
```
vmess://... # Original config
vmess://... # Original config [CDN] - Uses 104.16.0.0:443
vmess://... # Original config [CDN] - Uses 104.16.0.0:8443
vmess://... # Original config [CDN] - Uses 172.67.0.0:443
```

### CDN Config Generation Rules

1. **Only for WebSocket-based protocols**: ws, httpupgrade, splithttp
2. **TLS enforced**: All CDN configs use TLS
3. **Multiple variants**: Generates configs for top CDN IPs and ports
4. **Automatic**: No user action required, happens during subscription fetch

## Frontend Integration (TODO)

### Recommended Structure

```
dashboard/src/modules/settings/cloudflare/
├── cloudflare-settings.tsx       # Cloudflare API configuration
├── cdn-ip-selector.tsx           # CDN IP selection and testing
├── dns-management.tsx            # DNS record management
└── zone-selector.tsx             # Cloudflare zone selection
```

### TypeScript Types

```typescript
interface CloudflareSettings {
  enabled: boolean;
  api_token?: string;
  email?: string;
  default_zone_id?: string;
  domains: CloudflareDomain[];
  auto_cdn_ip: boolean;
  cdn_ports: number[];
  preferred_ips: string[];
}

interface CloudflareDomain {
  domain: string;
  zone_id: string;
  enabled: boolean;
}

interface CloudflareIPInfo {
  ip: string;
  latency_ms?: number;
  location?: string;
}
```

## Configuration

### Default CDN IPs

The system includes a default list of Cloudflare CDN IPs:
- 104.16.0.0 - 104.31.0.0
- 172.64.0.0 - 172.67.0.0

### CDN-Compatible Ports

Default ports (all Cloudflare CDN compatible):
- HTTP: 80, 8080, 8880, 2052, 2082, 2086, 2095
- HTTPS: 443, 8443, 2053, 2083, 2087, 2096

## Security Considerations

1. **API Token Security**: Tokens stored encrypted in database
2. **Sudo Admin Only**: All Cloudflare endpoints require sudo admin access
3. **Token Validation**: Automatic verification before operations
4. **TLS Enforcement**: CDN configs always use TLS

## Benefits vs Hiddify

This implementation matches and exceeds Hiddify's CDN features:

| Feature | Hiddify | Marzneshin |
|---------|---------|------------|
| Cloudflare API Integration | ✅ | ✅ |
| Auto CDN IP Selection | ✅ | ✅ |
| DNS Management | ✅ | ✅ |
| Latency Testing | ❌ | ✅ |
| Multiple CDN Ports | ✅ | ✅ |
| Custom Preferred IPs | ❌ | ✅ |
| API-Based Management | ✅ | ✅ |

## Troubleshooting

**CDN Configs Not Appearing:**
- Check if Cloudflare settings are enabled
- Verify `auto_cdn_ip` is true
- Ensure user has WebSocket-based inbounds (ws/httpupgrade/splithttp)

**API Token Invalid:**
- Verify token has correct permissions
- Check token expiration
- Ensure email matches Cloudflare account

**DNS Operations Fail:**
- Verify zone_id is correct
- Check API token permissions include DNS edit
- Ensure domain is properly configured in Cloudflare

## Dependencies

**Python Packages:**
- `httpx` - HTTP client (already installed)

**No additional dependencies required**

## Future Enhancements

- [ ] Automatic DNS record creation for nodes
- [ ] CDN health monitoring
- [ ] Auto-failover between CDN IPs
- [ ] GeoIP-based CDN selection
- [ ] Custom CDN provider support (not just Cloudflare)
- [ ] CDN performance analytics
- [ ] Automatic optimal IP rotation

## License

AGPL-3.0
