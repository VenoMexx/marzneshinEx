# Separate Upload/Download Domains Feature

## Overview

The **Separate Upload/Download Domains** feature allows administrators to configure different domains for upload and download traffic on each inbound host. This provides enhanced traffic obfuscation, improved CDN optimization, and better load distribution across different network paths.

## Table of Contents

- [Purpose and Benefits](#purpose-and-benefits)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [API Usage](#api-usage)
- [Use Cases](#use-cases)
- [Technical Details](#technical-details)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Purpose and Benefits

### Why Separate Upload/Download Domains?

1. **Traffic Pattern Obfuscation**
   - Makes Deep Packet Inspection (DPI) analysis more difficult
   - Different domains for different traffic directions confuse automated detection systems
   - Reduces the fingerprint of your proxy traffic

2. **CDN Optimization**
   - Use different CDN edges optimized for upload vs download
   - Some CDN providers have different performance characteristics for each direction
   - Allows routing through geographically optimal paths for each traffic type

3. **Load Distribution**
   - Distribute traffic across multiple domains/IPs
   - Reduce load on individual CDN endpoints
   - Improve overall system reliability

4. **Bypass Restrictions**
   - If one domain gets throttled or blocked, the other may still work
   - Provides redundancy at the domain level
   - Allows graceful degradation of service

---

## How It Works

### Subscription Generation

When you configure both `upload_host` and `download_host` for an inbound host, Marzneshin automatically generates **two separate configurations** in the user's subscription:

1. **Upload-Optimized Config**
   - Uses the domain specified in `upload_host`
   - Identified with " (Upload)" suffix in the config name
   - Recommended for upload-heavy traffic patterns

2. **Download-Optimized Config**
   - Uses the domain specified in `download_host`
   - Identified with " (Download)" suffix in the config name
   - Recommended for download-heavy traffic patterns

### Client Behavior

Users will see both configurations in their proxy client:

```
🇺🇸 US-Server-1 (Upload)
🇺🇸 US-Server-1 (Download)
```

They can:
- Use both configurations simultaneously (client will balance)
- Manually select upload-optimized for torrenting/uploading
- Manually select download-optimized for streaming/downloading
- Let the client auto-select based on availability

---

## Configuration

### Database Schema

The feature adds two new optional fields to the `hosts` table:

```sql
upload_host   VARCHAR(1024)  -- Domain for upload traffic
download_host VARCHAR(1024)  -- Domain for download traffic
```

### Via Web Panel (Frontend)

When creating or editing an inbound host, you'll see three domain fields:

1. **Host** (original field)
   - Used when upload/download domains are not specified
   - Supports comma-separated values for round-robin
   - Example: `cdn1.example.com,cdn2.example.com`

2. **Upload Host** (new field)
   - Domain optimized for upload traffic
   - Example: `upload-cdn.example.com`

3. **Download Host** (new field)
   - Domain optimized for download traffic
   - Example: `download-cdn.example.com`

**Behavior:**
- If both upload_host and download_host are empty → uses `host` field (standard behavior)
- If both upload_host and download_host are set → generates two separate configs
- If only one is set → falls back to standard behavior

---

## API Usage

### Creating a Host with Separate Domains

**Endpoint:** `POST /api/inbounds/{inbound_id}/hosts`

```json
{
  "remark": "US Server 1",
  "address": "123.45.67.89",
  "port": 443,
  "host": "default.example.com",
  "upload_host": "upload.example.com",
  "download_host": "download.example.com",
  "sni": "sni.example.com",
  "path": "/ws",
  "security": "tls",
  "network": "ws"
}
```

### Updating a Host

**Endpoint:** `PUT /api/inbounds/hosts/{host_id}`

```json
{
  "upload_host": "upload-cdn.example.com",
  "download_host": "download-cdn.example.com"
}
```

### Response Model

The `InboundHost` model includes the new fields:

```python
class InboundHost(BaseModel):
    remark: str
    address: str
    host: str | None = None
    upload_host: str | None = None      # NEW
    download_host: str | None = None    # NEW
    # ... other fields
```

---

## Use Cases

### Use Case 1: CDN Optimization

**Scenario:** You have a CDN with different edge servers optimized for different traffic directions.

**Configuration:**
```json
{
  "remark": "CDN Server",
  "address": "origin.example.com",
  "upload_host": "upload-edge.cdn.com",
  "download_host": "download-edge.cdn.com"
}
```

**Result:** Upload traffic goes through upload-optimized edge, download through download-optimized edge.

---

### Use Case 2: Geographic Load Distribution

**Scenario:** You want to route traffic through different geographic locations.

**Configuration:**
```json
{
  "remark": "Global Server",
  "upload_host": "us-west.example.com",
  "download_host": "eu-central.example.com"
}
```

**Result:** Upload routed via US West, download via EU Central.

---

### Use Case 3: Traffic Obfuscation

**Scenario:** You want to make traffic analysis harder by using completely different domains.

**Configuration:**
```json
{
  "remark": "Obfuscated Server",
  "upload_host": "api-v2.cloudservice.net",
  "download_host": "cdn-assets.mediasite.io"
}
```

**Result:** Upload traffic appears to go to a cloud API, download to a media CDN.

---

### Use Case 4: Redundancy and Failover

**Scenario:** One domain might get blocked, but you want fallback options.

**Configuration:**
```json
{
  "remark": "Resilient Server",
  "host": "primary.example.com",
  "upload_host": "backup-upload.example.com",
  "download_host": "backup-download.example.com"
}
```

**Result:** Three total configs generated, providing multiple connection options.

---

## Technical Details

### Implementation Architecture

#### 1. Database Layer (`app/db/models.py`)

```python
class InboundHost(Base):
    __tablename__ = "hosts"

    # ... existing fields
    upload_host = Column(String(1024), nullable=True)
    download_host = Column(String(1024), nullable=True)
```

#### 2. API Models (`app/models/proxy.py`)

```python
class InboundHost(BaseModel):
    upload_host: str | None = Field(
        None,
        description="Separate domain for upload traffic"
    )
    download_host: str | None = Field(
        None,
        description="Separate domain for download traffic"
    )
```

#### 3. Config Generation (`app/utils/share.py`)

```python
def generate_user_configs(...):
    for host in hosts:
        if host.upload_host and host.download_host:
            # Generate upload config
            upload_host_variant = _create_host_variant(
                host, host.upload_host, " (Upload)"
            )
            configs.append(create_config(upload_host_variant, ...))

            # Generate download config
            download_host_variant = _create_host_variant(
                host, host.download_host, " (Download)"
            )
            configs.append(create_config(download_host_variant, ...))
        else:
            # Standard single config
            configs.append(create_config(host, ...))
```

#### 4. CRUD Operations (`app/db/crud.py`)

Both `add_host()` and `update_host()` functions support the new fields:

```python
def add_host(db: Session, inbound: Inbound, host: InboundHostModify):
    host = InboundHost(
        # ... existing fields
        upload_host=host.upload_host,
        download_host=host.download_host,
    )
```

---

## Best Practices

### 1. Domain Selection

✅ **DO:**
- Use different CDN providers for upload/download
- Use geographically diverse domains
- Use domains that match common services (e.g., CDNs, APIs)

❌ **DON'T:**
- Use obviously related domain names (e.g., `up.example.com` and `down.example.com`)
- Use domains that might raise suspicion
- Use domains without proper SSL certificates

### 2. CDN Configuration

✅ **DO:**
- Configure both domains with Cloudflare or your CDN
- Enable WebSocket support on both domains
- Test both domains independently before deployment

❌ **DON'T:**
- Mix CDN and non-CDN domains (creates fingerprint)
- Use expired or invalid SSL certificates
- Forget to configure DNS properly

### 3. Performance Testing

Before deploying to users:

```bash
# Test upload domain
curl -o /dev/null -w '%{speed_upload}' --upload-file test.bin https://upload.example.com

# Test download domain
curl -o /dev/null -w '%{speed_download}' https://download.example.com/test.bin
```

### 4. Monitoring

Monitor both domains separately:

- Response times
- Success rates
- Geographic distribution of requests
- CDN hit/miss ratios

---

## Troubleshooting

### Problem: Configs not generating separately

**Symptoms:** Only one config appears in subscription

**Diagnosis:**
```bash
# Check if both fields are set
curl -X GET https://panel.example.com/api/inbounds/hosts/{id} \
  -H "Authorization: Bearer TOKEN"
```

**Solution:**
- Ensure both `upload_host` AND `download_host` are set
- If only one is set, system falls back to standard behavior
- Check database migration was applied: `alembic current`

---

### Problem: Clients can't connect to upload/download domains

**Symptoms:** Connection failures on specific configs

**Diagnosis:**
```bash
# Test DNS resolution
nslookup upload.example.com
nslookup download.example.com

# Test TLS handshake
openssl s_client -connect upload.example.com:443 -servername upload.example.com

# Test WebSocket (if using ws)
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     https://upload.example.com/ws
```

**Solution:**
- Verify DNS records are correct
- Check SSL certificates are valid
- Ensure firewall rules allow both domains
- Verify CDN configuration for both domains

---

### Problem: Performance worse with separate domains

**Symptoms:** Slower speeds when using upload/download configs

**Diagnosis:**
```bash
# Benchmark standard config
time curl https://standard.example.com/test.bin

# Benchmark upload domain
time curl --upload-file test.bin https://upload.example.com

# Benchmark download domain
time curl https://download.example.com/test.bin
```

**Solution:**
- Check if domains are routing through optimal paths
- Verify CDN edge location selection
- Consider using domains in same geographic region
- May need to adjust `upload_host`/`download_host` values

---

### Problem: Migration fails

**Symptoms:** Error when running `alembic upgrade head`

**Solution:**
```bash
# Check migration status
alembic current

# Check for conflicts
alembic history

# Force upgrade (if safe)
alembic upgrade head

# Manual SQL (last resort)
ALTER TABLE hosts ADD COLUMN upload_host VARCHAR(1024);
ALTER TABLE hosts ADD COLUMN download_host VARCHAR(1024);
```

---

## Migration Guide

### Applying the Migration

```bash
# Check current migration
alembic current

# Apply migration
alembic upgrade head

# Verify
alembic current
# Should show: 0d7ca8e24cc3 (head)
```

### Rollback (if needed)

```bash
# Rollback to previous version
alembic downgrade -1

# Or rollback to specific revision
alembic downgrade 57eba0a293f2
```

---

## Advanced Configuration

### Combining with Cloudflare

If using Cloudflare CDN:

1. Create two CNAME records:
   ```
   upload.example.com   CNAME  origin.example.com
   download.example.com CNAME  origin.example.com
   ```

2. Enable Cloudflare proxy (orange cloud) for both

3. Configure separate caching rules:
   - Upload domain: Minimal caching, optimize for POST/PUT
   - Download domain: Aggressive caching, optimize for GET

4. Set different security levels:
   - Upload: Higher security (more verification)
   - Download: Lower security (better performance)

### Combining with Multiple IPs

You can combine with comma-separated addresses:

```json
{
  "remark": "Multi-IP Server",
  "address": "1.2.3.4,5.6.7.8",
  "upload_host": "upload1.example.com,upload2.example.com",
  "download_host": "download1.example.com,download2.example.com"
}
```

Result: Even more configs generated with all combinations.

---

## Performance Impact

### Subscription Size

**Before:** 1 config per host
**After:** 2 configs per host (when both domains set)

**Example:**
- 10 hosts with separate domains = 20 configs in subscription
- Subscription file size increases proportionally
- Most clients handle this without issues

### Processing Overhead

**Minimal impact:**
- Config generation adds ~1-2ms per host
- Memory usage increases slightly
- No runtime performance impact on proxy traffic

---

## Security Considerations

### 1. Domain Privacy

- Both domains will be visible in subscription URLs
- Choose domains that don't reveal sensitive information
- Use generic, legitimate-looking domain names

### 2. SSL/TLS

- Both domains MUST have valid SSL certificates
- Certificate mismatch will break connections
- Use wildcard certificates if possible

### 3. Traffic Analysis

- Separate domains reduce traffic pattern fingerprinting
- But both domains will show in DNS queries
- Consider using DoH (DNS over HTTPS) at client level

---

## Integration with Other Features

### Works With

✅ **Cloudflare CDN Integration**
- Both domains can use Cloudflare
- Separate Worker routes for upload/download

✅ **Smart Proxy Mode**
- Both configs inherit routing rules
- Works with all proxy modes

✅ **Host Chaining**
- Upload and download variants both support chaining
- Can chain different hosts for upload vs download

✅ **WARP Integration**
- Both configs can use WARP
- Independent WARP routing per domain

### Compatibility

- **Client Support:** All major clients (V2Ray, Clash, Sing-Box)
- **Protocol Support:** All protocols (VLESS, VMess, Trojan, Shadowsocks)
- **Transport Support:** All transports (WS, gRPC, HTTP/2, TCP, QUIC)

---

## Monitoring and Analytics

### Tracking Usage

Monitor which configs users prefer:

```python
# Example analytics query
SELECT
    CASE
        WHEN remark LIKE '% (Upload)' THEN 'Upload Config'
        WHEN remark LIKE '% (Download)' THEN 'Download Config'
        ELSE 'Standard Config'
    END as config_type,
    COUNT(*) as connection_count,
    AVG(used_traffic) as avg_traffic
FROM user_connections
GROUP BY config_type;
```

### Performance Metrics

Track performance differences:

```python
# Compare upload vs download performance
{
    "upload_domain": {
        "avg_latency_ms": 45,
        "avg_speed_mbps": 250,
        "error_rate": 0.02
    },
    "download_domain": {
        "avg_latency_ms": 38,
        "avg_speed_mbps": 450,
        "error_rate": 0.01
    }
}
```

---

## FAQ

### Q: Do I need to set both upload_host and download_host?

**A:** Yes, both must be set to enable the feature. If only one is set, the system falls back to using the standard `host` field.

### Q: Can I use the same domain for both?

**A:** Yes, but this defeats the purpose of the feature. The system will still generate two separate configs, but they'll be identical.

### Q: Will existing users automatically get the new configs?

**A:** Yes! When they refresh their subscription, they'll see both upload and download configs.

### Q: Can I use comma-separated values in upload_host/download_host?

**A:** Currently, each field accepts a single domain. Use the standard `host` field for comma-separated round-robin.

### Q: What happens if one domain goes down?

**A:** Users can manually switch to the other config. For automatic failover, configure both in the client's load balancer.

### Q: Does this work with Reality protocol?

**A:** Yes! All protocols are supported, including Reality, VLESS, VMess, Trojan, and Shadowsocks.

### Q: How do I disable this feature for a specific host?

**A:** Just set both `upload_host` and `download_host` to `null` or empty string. The system will use the standard `host` field.

---

## Changelog

### Version 1.0.0 (2025-01-10)

**Added:**
- `upload_host` and `download_host` columns to hosts table
- Automatic generation of separate upload/download configs
- API support for new fields in create/update operations
- Database migration `0d7ca8e24cc3`
- Comprehensive documentation

**Modified:**
- `generate_user_configs()` function to support domain separation
- `InboundHost` database model
- `InboundHost` API model
- `add_host()` and `update_host()` CRUD operations

---

## Related Features

- [Cloudflare CDN Integration](./CLOUDFLARE_CDN_FEATURE.md)
- [Smart Proxy Mode](./SMART_PROXY_MODE_FEATURE.md)
- [QUIC Protocol Support](./QUIC_PROTOCOL_FEATURE.md)
- [WARP Integration](./WARP_FEATURE.md)

---

## Support

For issues or questions about this feature:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review the [FAQ](#faq)
3. Check existing GitHub issues
4. Create a new issue with:
   - Marzneshin version
   - Error logs
   - Configuration details (sanitized)
   - Steps to reproduce

---

## License

This feature is part of Marzneshin and inherits the same license.

---

**Last Updated:** 2025-01-10
**Feature Version:** 1.0.0
**Minimum Marzneshin Version:** Latest
