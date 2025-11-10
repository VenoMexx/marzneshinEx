# Telegram MTProto Proxy Support

## Overview

**Telegram MTProto Proxy** is a specialized proxy protocol designed specifically for Telegram messenger. Marzneshin supports MTProto proxies through Xray-core's Shadowsocks protocol with specific configurations, allowing users to bypass Telegram restrictions and access the messenger even in countries where it's blocked.

## Table of Contents

- [What is MTProto Proxy](#what-is-mtproto-proxy)
- [Why Use MTProto Proxy](#why-use-mtproto-proxy)
- [How It Works in Marzneshin](#how-it-works-in-marzneshin)
- [Configuration](#configuration)
- [Setup Guide](#setup-guide)
- [Client Configuration](#client-configuration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

---

## What is MTProto Proxy

MTProto is Telegram's proprietary protocol for secure communication. MTProto Proxy is a special type of proxy that:

- Works exclusively with Telegram apps
- Uses Telegram's native protocol
- Provides end-to-end encryption
- Bypasses Telegram blocks in restrictive countries
- Offers better performance for Telegram traffic

### Key Features

✅ **Telegram-Specific**: Optimized only for Telegram messenger
✅ **Deep Packet Inspection (DPI) Resistant**: Disguises traffic patterns
✅ **Low Latency**: Direct protocol support without additional overhead
✅ **Easy Setup**: Simple configuration in Telegram apps
✅ **Promotion Support**: Can show sponsored channels (optional)

---

## Why Use MTProto Proxy

### Use Cases

1. **Bypass Telegram Blocks**
   - Access Telegram in countries where it's banned
   - Circumvent ISP-level Telegram restrictions
   - Avoid IP-based blocks

2. **Privacy Enhancement**
   - Hide Telegram usage from ISP
   - Prevent traffic analysis
   - Protect against DPI

3. **Performance**
   - Direct Telegram protocol support
   - Lower latency than general-purpose proxies
   - Optimized for Telegram's traffic patterns

4. **Monetization** (Optional)
   - Earn from sponsored channels
   - Telegram pays for proxy bandwidth
   - Revenue share for proxy operators

---

## How It Works in Marzneshin

### Architecture

Marzneshin doesn't implement a standalone MTProto proxy server. Instead, it leverages **Xray-core** capabilities with specific configurations that work with Telegram:

```
Telegram App → MTProto Protocol → Xray-core (Shadowsocks/VMess) → Telegram Servers
```

### Current Implementation Status

**⚠️ Important Note:**

Marzneshin currently uses Xray-core for proxy protocols, which primarily supports:
- VMess
- VLESS
- Trojan
- Shadowsocks
- Wireguard

**Native MTProto proxy** is not directly implemented in Xray-core. However, you can:

1. **Use Shadowsocks** - Telegram works well with Shadowsocks proxies
2. **Deploy Standalone MTProto Server** - Run a separate MTProto proxy alongside Marzneshin
3. **Use Telegram Proxy Protocol** - Configure SOCKS5/HTTP proxy for Telegram

---

## Configuration

### Option 1: Using Shadowsocks for Telegram

Shadowsocks works excellently with Telegram and provides similar benefits to MTProto.

**Step 1: Create Shadowsocks Inbound**

Via API:
```json
{
  "protocol": "shadowsocks",
  "tag": "telegram-ss",
  "config": {
    "network": "tcp,udp",
    "security": "chacha20-poly1305",
    "settings": {
      "method": "chacha20-poly1305",
      "password": "your-password"
    }
  }
}
```

**Step 2: Create Host for Shadowsocks**

```json
{
  "remark": "Telegram Proxy - SS",
  "address": "your-server-ip",
  "port": 443,
  "protocol": "shadowsocks",
  "password": "your-password",
  "shadowsocks_method": "chacha20-poly1305",
  "network": "tcp"
}
```

**Step 3: Users Add to Telegram**

In Telegram:
1. Go to **Settings** → **Data and Storage** → **Proxy Settings**
2. Add Server:
   - **Type**: SOCKS5
   - **Server**: your-server-ip
   - **Port**: 443
   - **Username**: (leave empty)
   - **Password**: your-password

---

### Option 2: Standalone MTProto Proxy (Advanced)

For native MTProto support, deploy a separate MTProto proxy server:

**Installation:**

```bash
# Install MTProxy
git clone https://github.com/TelegramMessenger/MTProxy.git
cd MTProxy
make

# Generate secret
head -c 16 /dev/urandom | xxd -ps
# Output: your-16-byte-hex-secret

# Run MTProxy
./mtproto-proxy -u nobody -p 8888 -H 443 -S <secret> --aes-pwd proxy-secret proxy-multi.conf -M 1
```

**Configuration:**

```bash
# proxy-multi.conf
proxy-secret <your-secret>
proxy-tag <optional-promotion-tag>
```

**User Configuration:**

Share link format:
```
https://t.me/proxy?server=<ip>&port=443&secret=<secret>
```

---

### Option 3: Using VLESS/VMess with Telegram

Telegram also works with VLESS/VMess configured as SOCKS proxy:

**Create VLESS Inbound:**
```json
{
  "protocol": "vless",
  "tag": "telegram-vless",
  "port": 443,
  "settings": {
    "clients": [],
    "decryption": "none"
  },
  "streamSettings": {
    "network": "ws",
    "security": "tls"
  }
}
```

**Client Setup:**
- Configure VLESS client as local SOCKS proxy
- Point Telegram to localhost:1080 (SOCKS5)

---

## Setup Guide

### Quick Setup: Shadowsocks for Telegram

**1. Panel Configuration**

```bash
# Via Marzneshin API
curl -X POST "https://panel.example.com/api/inbounds" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "protocol": "shadowsocks",
    "tag": "ss-telegram",
    "config": "{\"network\": \"tcp,udp\", \"port\": 8388}"
  }'
```

**2. Create User**

```bash
curl -X POST "https://panel.example.com/api/users" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "username": "telegram_user",
    "data_limit": 10737418240,
    "expire_date": "2025-12-31T23:59:59"
  }'
```

**3. Assign to Inbound**

Link user to Shadowsocks inbound through services.

**4. Share Configuration**

Provide user with:
- Server IP
- Port (8388)
- Method (chacha20-poly1305)
- Password (from subscription)

---

## Client Configuration

### Telegram Desktop

1. Open Telegram Desktop
2. Go to **Settings** → **Advanced** → **Connection type**
3. Select **Use custom proxy**
4. Choose **SOCKS5**
5. Enter:
   - **Hostname**: your-server-ip
   - **Port**: 8388
   - **Username**: (leave empty for Shadowsocks)
   - **Password**: your-password

### Telegram Mobile (Android/iOS)

1. Open Telegram app
2. Go to **Settings** → **Data and Storage** → **Proxy Settings**
3. Tap **Add Proxy**
4. Select **SOCKS5**
5. Fill in details:
   - **Server**: your-server-ip
   - **Port**: 8388
   - **Password**: your-password

### Using MTProxy Link (if standalone MTProxy)

Simply click on the MTProxy link:
```
https://t.me/proxy?server=<ip>&port=443&secret=<secret>
```

Telegram will automatically configure the proxy.

---

## Best Practices

### 1. Performance Optimization

**Use UDP Support:**
```json
{
  "network": "tcp,udp"
}
```
Telegram voice/video calls use UDP.

**Optimize Shadowsocks Method:**
```
Recommended: chacha20-poly1305 (fast, secure)
Alternative: aes-256-gcm (wide support)
```

### 2. Security

**Use TLS When Possible:**
```json
{
  "security": "tls",
  "tlsSettings": {
    "serverName": "your-domain.com",
    "certificates": [...]
  }
}
```

**Strong Passwords:**
```bash
# Generate strong Shadowsocks password
openssl rand -base64 32
```

### 3. Availability

**Multiple Ports:**
Offer proxies on multiple ports:
- 443 (HTTPS)
- 80 (HTTP)
- 8080 (common)
- 8388 (Shadowsocks default)

**Geographic Diversity:**
Deploy proxies in multiple regions for better performance.

---

## Troubleshooting

### Problem: Telegram can't connect

**Symptoms:** "Connecting..." forever, timeout errors

**Diagnosis:**
```bash
# Test server reachability
telnet your-server-ip 8388

# Check if Shadowsocks is running
ss -tlnp | grep 8388

# Check Xray logs
journalctl -u marzneshin -f | grep shadowsocks
```

**Solutions:**
- Verify firewall allows port 8388
- Check Shadowsocks configuration
- Ensure correct password/method
- Try different port (443, 80)

---

### Problem: Slow connection in Telegram

**Symptoms:** Messages load slowly, media doesn't download

**Diagnosis:**
```bash
# Check server load
htop

# Monitor bandwidth
iftop -i eth0

# Check latency
ping telegram.org
```

**Solutions:**
- Enable UDP support for voice/video
- Use faster encryption (chacha20-poly1305)
- Check server bandwidth limits
- Consider server location (closer to users)

---

### Problem: Proxy works but voice calls don't

**Symptoms:** Messages work, but calls fail

**Solution:**
Ensure UDP is enabled:
```json
{
  "network": "tcp,udp"  // Not just "tcp"
}
```

---

## Limitations

### Marzneshin/Xray-core Limitations

1. **No Native MTProto**: Xray-core doesn't implement MTProto protocol natively
2. **No Promotion Tags**: Can't earn from Telegram sponsored channels
3. **Indirect Support**: Telegram works via SOCKS/Shadowsocks, not pure MTProto

### Workarounds

**For Native MTProto:**
- Deploy standalone MTProxy server alongside Marzneshin
- Use MTProxy for Telegram, Marzneshin for other traffic

**For Promotion:**
- Register MTProxy server with Telegram
- Get promotion tag from [@MTProxybot](https://t.me/MTProxybot)

---

## Comparison: MTProto vs Shadowsocks for Telegram

| Feature | MTProto Proxy | Shadowsocks |
|---------|---------------|-------------|
| **Telegram-Specific** | ✅ Yes | ❌ No (general purpose) |
| **Promotion Support** | ✅ Yes | ❌ No |
| **Setup Complexity** | 🟡 Medium | 🟢 Easy (built into Marzneshin) |
| **Performance** | 🟢 Excellent | 🟢 Excellent |
| **DPI Resistance** | 🟢 High | 🟢 High |
| **Multi-Use** | ❌ Telegram only | ✅ All traffic |
| **Xray Support** | ❌ No | ✅ Native |

**Recommendation**: Use **Shadowsocks via Marzneshin** for simplicity and multi-purpose use. Deploy **standalone MTProxy** only if you need promotion revenue or pure MTProto protocol.

---

## Advanced: Hybrid Setup

Combine Marzneshin with standalone MTProxy:

**Architecture:**
```
User
  ├─ MTProxy (port 443) → Telegram traffic → Revenue
  └─ Marzneshin (port 8443) → All other traffic → Full proxy
```

**Benefits:**
- Earn from Telegram promotion
- Use Marzneshin for comprehensive proxy management
- Separate Telegram and general traffic

**Setup:**

1. **Install MTProxy** (see Option 2 above)
2. **Configure Marzneshin** on different port
3. **Share Both**:
   - MTProxy link for Telegram users
   - Marzneshin subscription for general users

---

## Official MTProxy Resources

- [Official MTProxy GitHub](https://github.com/TelegramMessenger/MTProxy)
- [MTProxy Setup Guide](https://github.com/TelegramMessenger/MTProxy#building)
- [Telegram Proxy FAQ](https://telegram.org/faq#q-what-are-proxy-servers)
- [Register for Promotion](https://t.me/MTProxybot)

---

## Alternative: Telegram SOCKS5 Proxy

Telegram fully supports SOCKS5 proxies, which Marzneshin can provide:

**Setup:**

1. Configure any Marzneshin inbound (VLESS, VMess, Shadowsocks)
2. User sets up client with local SOCKS proxy
3. Point Telegram to `127.0.0.1:1080`

**Advantages:**
- Uses existing Marzneshin infrastructure
- No additional servers needed
- Works with all Marzneshin protocols

---

## Conclusion

While Marzneshin/Xray-core doesn't natively support MTProto proxy protocol, Telegram works excellently with:

1. **Shadowsocks** (recommended, built-in)
2. **VLESS/VMess** as SOCKS5 proxy
3. **Standalone MTProxy** (for native MTProto)

For most users, **Shadowsocks via Marzneshin** provides the best balance of:
- Easy setup
- Great performance
- DPI resistance
- Multi-purpose use

For operators seeking **promotion revenue** or **pure MTProto**, deploy a **standalone MTProxy server** alongside Marzneshin.

---

## Related Features

- [User Control Panel](./USER_CONTROL_PANEL_FEATURE.md)
- [Telegram Bot for Users](./TELEGRAM_BOT_FEATURE.md)
- [DNS over HTTPS](./DNS_OVER_HTTPS_FEATURE.md)
- [QUIC Protocol](./QUIC_PROTOCOL_FEATURE.md)

---

**Last Updated:** 2025-01-10
**Feature Status:** Supported via Shadowsocks/SOCKS5
**Native MTProto:** Not available in Xray-core
