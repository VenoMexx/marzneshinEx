# DNS over HTTPS (DoH) Feature

## Overview

The **DNS over HTTPS (DoH)** feature enables encrypted DNS queries for all proxy connections, providing enhanced privacy, security, and censorship resistance. DoH encrypts DNS requests using HTTPS, preventing DNS hijacking, eavesdropping, and manipulation by ISPs or network intermediaries.

## Table of Contents

- [Purpose and Benefits](#purpose-and-benefits)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [API Usage](#api-usage)
- [CDN Integration](#cdn-integration)
- [Use Cases](#use-cases)
- [Technical Details](#technical-details)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Supported Clients](#supported-clients)

---

## Purpose and Benefits

### Why DNS over HTTPS?

1. **Privacy Protection**
   - Encrypts DNS queries using HTTPS/TLS
   - Prevents ISPs from seeing which websites you visit
   - Protects against DNS query logging and surveillance
   - Hides DNS traffic from network administrators

2. **Security Enhancement**
   - Prevents DNS hijacking and spoofing attacks
   - Protects against man-in-the-middle (MITM) attacks
   - Ensures DNS response integrity
   - Reduces risk of DNS cache poisoning

3. **Censorship Resistance**
   - Bypasses DNS-based filtering and blocking
   - Prevents DNS redirect attacks
   - Access blocked websites even when DNS is filtered
   - Works in restrictive network environments

4. **CDN Optimization**
   - Use Cloudflare's anycast DoH for global performance
   - Automatic failover to multiple DoH providers
   - Reduced DNS query latency
   - Better reliability through redundant servers

---

## How It Works

### Traditional DNS vs DoH

**Traditional DNS (Unencrypted):**
```
Client → DNS Query (Port 53, Unencrypted) → DNS Server → Response
         ↑ Visible to ISP, Network, Governments
```

**DNS over HTTPS (Encrypted):**
```
Client → HTTPS Request (Port 443, Encrypted) → DoH Server → Response
         ↑ Looks like normal HTTPS traffic, Encrypted
```

### Integration with Marzneshin

When DoH is enabled:

1. **Global Configuration**: Admin configures DoH servers in panel settings
2. **Subscription Generation**: Marzneshin automatically includes DoH DNS in configs
3. **Client Configuration**: User clients use DoH servers for all DNS queries
4. **Fallback Support**: If DoH fails, clients fall back to traditional DNS

### DNS Resolution Priority

```
1. Host-specific DNS servers (if configured for individual host)
   ↓ (if not set)
2. DoH servers from global settings (if DoH enabled)
   ↓ (if DoH unavailable)
3. Fallback DNS servers (traditional DNS as backup)
   ↓ (if all fail)
4. Client default DNS
```

---

## Configuration

### Via Web Panel

**Step 1: Access DoH Settings**
- Navigate to **Settings** → **DNS over HTTPS**
- Or use API endpoint: `GET /api/settings/doh`

**Step 2: Configure DoH Servers**

```json
{
  "enabled": true,
  "servers": [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/dns-query"
  ],
  "fallback_dns": ["1.1.1.1", "8.8.8.8"],
  "use_cdn_doh": true,
  "custom_hosts": {
    "example.com": "93.184.216.34"
  }
}
```

**Field Descriptions:**

- **enabled**: Enable/disable DoH globally
- **servers**: List of DoH server URLs (HTTPS endpoints)
- **fallback_dns**: Traditional DNS servers if DoH fails
- **use_cdn_doh**: Use CDN-optimized DoH when Cloudflare is enabled
- **custom_hosts**: Custom DNS mappings (domain → IP)

### Popular DoH Providers

#### Cloudflare DoH
```
URL: https://cloudflare-dns.com/dns-query
Anycast: Yes
IPv4: 1.1.1.1, 1.0.0.1
IPv6: 2606:4700:4700::1111, 2606:4700:4700::1001
Features: Fast, privacy-focused, no logging
```

#### Google Public DNS
```
URL: https://dns.google/dns-query
Anycast: Yes
IPv4: 8.8.8.8, 8.8.4.4
IPv6: 2001:4860:4860::8888, 2001:4860:4860::8844
Features: Reliable, global coverage
```

#### Quad9 DoH
```
URL: https://dns.quad9.net/dns-query
Anycast: Yes
IPv4: 9.9.9.9, 149.112.112.112
IPv6: 2620:fe::fe, 2620:fe::9
Features: Security-focused, blocks malware
```

#### AdGuard DNS
```
URL: https://dns.adguard.com/dns-query
Anycast: Yes
IPv4: 94.140.14.14, 94.140.15.15
IPv6: 2a10:50c0::ad1:ff, 2a10:50c0::ad2:ff
Features: Ad-blocking, family-friendly options
```

---

## API Usage

### Get DoH Settings

**Endpoint:** `GET /api/settings/doh`

**Headers:**
```
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "enabled": true,
  "servers": [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/dns-query"
  ],
  "fallback_dns": ["1.1.1.1", "8.8.8.8"],
  "use_cdn_doh": true,
  "custom_hosts": {}
}
```

---

### Update DoH Settings

**Endpoint:** `PUT /api/settings/doh`

**Headers:**
```
Authorization: Bearer <admin_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "enabled": true,
  "servers": [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/dns-query",
    "https://dns.quad9.net/dns-query"
  ],
  "fallback_dns": ["1.1.1.1", "8.8.8.8", "9.9.9.9"],
  "use_cdn_doh": true,
  "custom_hosts": {
    "api.myservice.com": "203.0.113.10"
  }
}
```

**Response:**
```json
{
  "enabled": true,
  "servers": [...],
  "fallback_dns": [...],
  "use_cdn_doh": true,
  "custom_hosts": {...}
}
```

---

### Test DoH Server

**Endpoint:** `POST /api/doh/test-server?server_url=<URL>`

**Headers:**
```
Authorization: Bearer <admin_token>
```

**Example:**
```bash
curl -X POST "https://panel.example.com/api/doh/test-server?server_url=https://cloudflare-dns.com/dns-query" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (Success):**
```json
{
  "status": "success",
  "server": "https://cloudflare-dns.com/dns-query",
  "response_time_ms": 45.23,
  "data": {
    "Status": 0,
    "TC": false,
    "RD": true,
    "RA": true,
    "AD": false,
    "CD": false,
    "Question": [...],
    "Answer": [...]
  }
}
```

**Response (Error):**
```json
{
  "status": "error",
  "server": "https://invalid-doh.com/dns-query",
  "error": "Connection timeout"
}
```

---

## CDN Integration

### Cloudflare CDN + DoH

When both Cloudflare CDN and DoH are enabled:

1. **Optimized Routing**: DNS queries routed through Cloudflare's anycast network
2. **Shared Infrastructure**: Uses same CDN as proxy traffic for consistency
3. **Geographic Optimization**: Automatic routing to nearest Cloudflare edge
4. **Enhanced Privacy**: Both DNS and proxy traffic encrypted end-to-end

**Configuration:**
```json
{
  "cloudflare": {
    "enabled": true,
    "auto_cdn_ip": true,
    "preferred_ips": ["104.16.0.0", "172.64.0.0"]
  },
  "doh": {
    "enabled": true,
    "use_cdn_doh": true,
    "servers": ["https://cloudflare-dns.com/dns-query"]
  }
}
```

### Benefits of CDN + DoH

- **Unified Network**: Single provider for both DNS and proxy traffic
- **Better Performance**: Reduced latency through shared infrastructure
- **Improved Privacy**: All traffic encrypted and routed through CDN
- **Simplified Management**: One provider to manage and monitor

---

## Use Cases

### Use Case 1: Bypass DNS Filtering

**Scenario:** Government/ISP blocks websites via DNS filtering

**Configuration:**
```json
{
  "enabled": true,
  "servers": [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/dns-query"
  ],
  "fallback_dns": []  // No fallback to prevent DNS leaks
}
```

**Result:** All DNS queries encrypted via HTTPS, bypassing DNS filters

---

### Use Case 2: Privacy-Focused Setup

**Scenario:** Maximum privacy for users in surveillance-heavy regions

**Configuration:**
```json
{
  "enabled": true,
  "servers": [
    "https://dns.quad9.net/dns-query"  // No logging policy
  ],
  "fallback_dns": ["9.9.9.9"],
  "custom_hosts": {
    "panel.example.com": "203.0.113.10"  // Direct IP mapping
  }
}
```

**Result:** Zero DNS logging, encrypted queries, custom host protection

---

### Use Case 3: High Availability

**Scenario:** Mission-critical service requiring maximum uptime

**Configuration:**
```json
{
  "enabled": true,
  "servers": [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/dns-query",
    "https://dns.quad9.net/dns-query",
    "https://dns.adguard.com/dns-query"
  ],
  "fallback_dns": ["1.1.1.1", "8.8.8.8", "9.9.9.9", "94.140.14.14"]
}
```

**Result:** Multiple DoH providers with traditional DNS fallback

---

### Use Case 4: Corporate/Enterprise

**Scenario:** Company proxy server with internal domain resolution

**Configuration:**
```json
{
  "enabled": true,
  "servers": [
    "https://cloudflare-dns.com/dns-query"
  ],
  "fallback_dns": ["1.1.1.1"],
  "custom_hosts": {
    "internal.company.com": "192.168.1.10",
    "api.internal.com": "192.168.1.20",
    "vpn.company.com": "203.0.113.50"
  }
}
```

**Result:** Public DoH for internet, custom mappings for internal services

---

## Technical Details

### Database Schema

**Settings Table:**
```sql
ALTER TABLE settings ADD COLUMN doh JSON;
```

**DoH Settings Structure:**
```json
{
  "enabled": boolean,
  "servers": [string],          // DoH URLs
  "fallback_dns": [string],     // Traditional DNS IPs
  "use_cdn_doh": boolean,
  "custom_hosts": {string: string}
}
```

### Implementation Architecture

#### 1. Settings Model (`app/models/settings.py`)

```python
class DoHSettings(BaseModel):
    enabled: bool = False
    servers: list[str] = Field(default_factory=lambda: [
        "https://cloudflare-dns.com/dns-query",
        "https://dns.google/dns-query",
    ])
    fallback_dns: list[str] = Field(default_factory=lambda: [
        "1.1.1.1", "8.8.8.8"
    ])
    use_cdn_doh: bool = True
    custom_hosts: dict[str, str] = Field(default_factory=dict)
```

#### 2. Config Generation (`app/utils/share.py`)

```python
def _get_effective_dns_servers(host) -> list[str]:
    # Priority:
    # 1. Host-specific DNS
    # 2. DoH servers (if enabled)
    # 3. Fallback DNS
    # 4. Client default

    if host.dns_servers:
        return host.dns_servers.split(",")

    doh_servers, fallback_dns = get_doh_dns_servers()

    if doh_servers:
        return doh_servers + fallback_dns  # Redundancy

    return fallback_dns if fallback_dns else []
```

#### 3. API Endpoints (`app/routes/system.py`)

```python
@router.get("/settings/doh", response_model=DoHSettings)
def get_doh_settings(db: DBDep, admin: SudoAdminDep):
    """Get DoH settings"""

@router.put("/settings/doh", response_model=DoHSettings)
def update_doh_settings(db: DBDep, modifications: DoHSettings, ...):
    """Update DoH settings"""

@router.post("/doh/test-server")
async def test_doh_server(server_url: str, ...):
    """Test DoH server availability"""
```

---

## Best Practices

### 1. Server Selection

✅ **DO:**
- Use multiple DoH providers for redundancy
- Choose providers with anycast networks
- Test server latency before deployment
- Use reputable providers with no-logging policies

❌ **DON'T:**
- Rely on single DoH provider
- Use untrusted or unknown DoH servers
- Mix providers from same jurisdiction (for privacy)
- Forget to configure fallback DNS

### 2. Performance Optimization

**Recommended Configuration:**
```json
{
  "servers": [
    "https://cloudflare-dns.com/dns-query",  // Primary (fast)
    "https://dns.google/dns-query"           // Secondary (reliable)
  ],
  "fallback_dns": ["1.1.1.1", "8.8.8.8"],    // Quick fallback
  "use_cdn_doh": true                         // CDN optimization
}
```

### 3. Privacy Considerations

For maximum privacy:
```json
{
  "servers": [
    "https://dns.quad9.net/dns-query"  // Strict no-logging
  ],
  "fallback_dns": [],  // No fallback to prevent DNS leaks
  "custom_hosts": {
    "sensitive-domain.com": "203.0.113.10"
  }
}
```

### 4. Monitoring

Track DoH performance:
```bash
# Test DoH server
curl "https://panel.example.com/api/doh/test-server?server_url=https://cloudflare-dns.com/dns-query"

# Monitor response times
# Expected: < 50ms for nearby servers
#           < 100ms for distant servers
#           > 200ms indicates issues
```

---

## Troubleshooting

### Problem: Clients can't resolve domains

**Symptoms:** Connection failures, DNS resolution errors

**Diagnosis:**
```bash
# Test DoH server manually
curl "https://cloudflare-dns.com/dns-query?name=google.com&type=A" \
  -H "accept: application/dns-json"

# Check if DoH is reachable
ping 1.1.1.1
```

**Solution:**
- Verify DoH servers are reachable from your network
- Check firewall rules allow HTTPS (port 443)
- Ensure DoH URLs are correct
- Add fallback DNS servers

---

### Problem: Slow DNS resolution

**Symptoms:** High latency, slow website loading

**Diagnosis:**
```bash
# Test DoH response time
curl -w "@curl-format.txt" -o /dev/null -s \
  "https://cloudflare-dns.com/dns-query?name=google.com&type=A"

# curl-format.txt:
time_namelookup:  %{time_namelookup}\n
time_connect:     %{time_connect}\n
time_total:       %{time_total}\n
```

**Solution:**
- Use geographically closer DoH servers
- Enable `use_cdn_doh` for CDN optimization
- Reduce number of DoH servers (too many can slow down)
- Check network path to DoH servers

---

### Problem: DoH not being used in clients

**Symptoms:** DNS queries still visible to ISP

**Diagnosis:**
- Check subscription config:
  ```bash
  curl "https://panel.example.com/sub/USER_KEY/xray" | base64 -d | jq '.dns'
  ```
- Verify DoH is enabled in panel settings
- Check client supports DoH (most modern clients do)

**Solution:**
- Ensure `enabled: true` in DoH settings
- Update clients to latest version
- Check client logs for DNS configuration errors

---

### Problem: Custom hosts not working

**Symptoms:** Custom domain mappings ignored

**Diagnosis:**
```bash
# Check if custom_hosts is in config
curl "https://panel.example.com/api/settings/doh" | jq '.custom_hosts'
```

**Solution:**
- Verify custom_hosts format: `{"domain": "ip"}`
- Ensure domain is exact match (case-sensitive)
- Check client supports static host mappings
- May need client restart after config update

---

## Supported Clients

### Client Compatibility

| Client | DoH Support | Notes |
|--------|-------------|-------|
| **V2Ray** | ✅ Yes | Full support via dns.servers |
| **Xray-core** | ✅ Yes | Native DoH support |
| **Clash** | ✅ Yes | DoH in dns.nameserver |
| **Clash Meta** | ✅ Yes | Enhanced DoH support |
| **Sing-Box** | ✅ Yes | Full DoH implementation |
| **Shadowrocket** | ✅ Yes | iOS, supports DoH URLs |
| **V2RayNG** | ✅ Yes | Android, full DoH support |
| **Nekoray** | ✅ Yes | Desktop, complete DoH |

### Client Configuration Examples

#### Xray/V2Ray
```json
{
  "dns": {
    "servers": [
      "https://cloudflare-dns.com/dns-query",
      "https://dns.google/dns-query",
      "1.1.1.1"
    ]
  }
}
```

#### Clash/Clash Meta
```yaml
dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  nameserver:
    - https://cloudflare-dns.com/dns-query
    - https://dns.google/dns-query
  fallback:
    - 1.1.1.1
    - 8.8.8.8
```

#### Sing-Box
```json
{
  "dns": {
    "servers": [
      {
        "tag": "dns-remote",
        "address": "https://cloudflare-dns.com/dns-query",
        "detour": "proxy"
      },
      {
        "tag": "dns-local",
        "address": "https://dns.google/dns-query",
        "detour": "direct"
      }
    ]
  }
}
```

---

## Security Considerations

### 1. MITM Protection

DoH protects against DNS MITM attacks:
- TLS encryption prevents tampering
- Certificate validation ensures authenticity
- DNS responses cannot be modified in transit

### 2. Privacy Benefits

- **ISP Blind**: ISP cannot see which websites you visit via DNS
- **No Query Logging**: Use no-logging DoH providers
- **Traffic Blending**: DNS queries look like normal HTTPS traffic

### 3. Potential Risks

⚠️ **Centralization**: Using few DoH providers may centralize DNS
⚠️ **Trust**: You trust DoH provider instead of ISP
⚠️ **Blocking**: Some networks may block known DoH servers

**Mitigation:**
- Use multiple DoH providers
- Choose privacy-focused providers
- Have fallback DNS configured
- Monitor DoH server availability

---

## Performance Metrics

### Expected Performance

| Metric | Traditional DNS | DoH | Notes |
|--------|----------------|-----|-------|
| **Query Time** | 10-30ms | 20-50ms | DoH slightly slower due to TLS |
| **Privacy** | None | High | DoH encrypted |
| **Censorship Resistance** | Low | High | DoH harder to block |
| **Overhead** | ~50 bytes | ~500 bytes | TLS adds overhead |

### Optimization Tips

1. **Use Anycast DoH**: Cloudflare, Google use anycast for low latency
2. **Enable CDN DoH**: Shared infrastructure reduces hops
3. **Cache Aggressively**: Client-side DNS caching reduces queries
4. **Limit Servers**: 2-3 DoH servers optimal for balance

---

## Migration Guide

### Enabling DoH on Existing Panel

**Step 1: Backup Settings**
```bash
# Export current settings
curl "https://panel.example.com/api/settings/doh" > doh-backup.json
```

**Step 2: Apply Migration**
```bash
# Run database migration
alembic upgrade head
```

**Step 3: Configure DoH**
```bash
# Update DoH settings via API
curl -X PUT "https://panel.example.com/api/settings/doh" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "servers": ["https://cloudflare-dns.com/dns-query"],
    "fallback_dns": ["1.1.1.1", "8.8.8.8"]
  }'
```

**Step 4: Test Configuration**
```bash
# Test DoH server
curl -X POST "https://panel.example.com/api/doh/test-server?server_url=https://cloudflare-dns.com/dns-query"
```

**Step 5: Users Update Subscriptions**
- Users refresh subscriptions in their clients
- New configs automatically include DoH DNS
- No manual client configuration needed

---

## FAQ

### Q: Does DoH slow down connections?

**A:** Minimal impact. DoH adds 10-20ms latency per DNS query, but queries are cached. Overall browsing speed impact < 1%.

### Q: Can DoH be blocked?

**A:** Theoretically yes, but DoH uses port 443 (HTTPS). Blocking it requires blocking all HTTPS traffic, which breaks most internet.

### Q: Do I need DoH if using VPN/proxy?

**A:** Yes! Even with VPN/proxy, DNS queries may leak. DoH ensures DNS privacy regardless of tunnel.

### Q: What if DoH server goes down?

**A:** Configure `fallback_dns` servers. Clients automatically fall back to traditional DNS if DoH fails.

### Q: Does DoH work with IPv6?

**A:** Yes! DoH works with both IPv4 (A records) and IPv6 (AAAA records) queries.

### Q: Can I use custom DoH server?

**A:** Yes! Any RFC 8484-compliant DoH server works. Just add the URL to `servers` list.

### Q: Does DoH prevent DNS leaks?

**A:** Yes, when properly configured. Remove `fallback_dns` to prevent leaks, but may reduce reliability.

---

## Related Features

- [Cloudflare CDN Integration](./CLOUDFLARE_CDN_FEATURE.md)
- [Smart Proxy Mode](./SMART_PROXY_MODE_FEATURE.md)
- [Separate Upload/Download Domains](./UPLOAD_DOWNLOAD_DOMAINS_FEATURE.md)
- [QUIC Protocol Support](./QUIC_PROTOCOL_FEATURE.md)

---

## References

- [RFC 8484 - DNS Queries over HTTPS](https://datatracker.ietf.org/doc/html/rfc8484)
- [Cloudflare DoH Documentation](https://developers.cloudflare.com/1.1.1.1/dns-over-https/)
- [Google Public DNS](https://developers.google.com/speed/public-dns/docs/doh)
- [Xray DNS Configuration](https://xtls.github.io/config/dns.html)

---

## Support

For issues or questions about DoH:

1. Check [Troubleshooting](#troubleshooting) section
2. Review [FAQ](#faq)
3. Test DoH server using `/api/doh/test-server` endpoint
4. Check client logs for DNS errors
5. Open GitHub issue with:
   - Marzneshin version
   - DoH configuration (sanitized)
   - Client type and version
   - Error messages or logs

---

**Last Updated:** 2025-01-10
**Feature Version:** 1.0.0
**Minimum Marzneshin Version:** Latest
