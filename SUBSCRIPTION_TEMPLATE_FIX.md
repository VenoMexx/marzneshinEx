# Subscription Template Variables Fix

**Date:** 2025-11-11
**Issue:** Multi-Node Subscription Links Using Wrong IP
**Status:** ✅ FIXED

---

## 🐛 Problem

### Before Fix:

In multi-node deployments, subscription links were always using the **master panel IP** instead of the **node-specific IP**.

**Example:**
```
Nodes:
  - DE1: de1.example.com (1.1.1.1)
  - DE2: de2.example.com (2.2.2.2)
  - FI1: fi1.example.com (3.3.3.3)
  - Master Panel: panel.example.com (4.4.4.4)

User subscription links:
  ❌ DE1 node: vless://...@4.4.4.4:443  (WRONG - master IP!)
  ❌ DE2 node: vless://...@4.4.4.4:443  (WRONG - master IP!)
  ❌ FI1 node: vless://...@4.4.4.4:443  (WRONG - master IP!)
```

### Root Cause:

```python
# app/utils/share.py (line 52)
SERVER_IP = get_public_ip()  # ← Global variable, only master IP

# app/utils/share.py (line 237)
format_variables = {
    "SERVER_IP": SERVER_IP,  # ← Always master IP!
}
```

**Impact:**
- Users couldn't connect to nodes
- All traffic routed through master panel
- Multi-node deployment broken
- Load balancing not working

---

## ✅ Solution

### After Fix:

Added **node-specific template variables**:

```python
# app/utils/share.py (new code at line 425-448)

# Extract node-specific information
if host.inbound and host.inbound.node:
    node_address = host.inbound.node.address or SERVER_IP
    node_name = host.inbound.node.name or "Unknown"
else:
    node_address = SERVER_IP  # Fallback to master IP
    node_name = "Master"

# Add node-specific template variables
format_variables.update({
    "NODE_ADDRESS": node_address,  # ✅ Node-specific IP
    "NODE_NAME": node_name,        # ✅ Node name
})
```

**Now users can use:**
```
User subscription links with {NODE_ADDRESS}:
  ✅ DE1 node: vless://...@de1.example.com:443  (CORRECT!)
  ✅ DE2 node: vless://...@de2.example.com:443  (CORRECT!)
  ✅ FI1 node: vless://...@fi1.example.com:443  (CORRECT!)
```

---

## 📝 Template Variables Reference

### Available Variables

| Variable | Value | Use Case |
|----------|-------|----------|
| `{SERVER_IP}` | Master panel IP | ⚠️ Legacy - use for single-node |
| `{NODE_ADDRESS}` | Node-specific IP/domain | ✅ **Use this for multi-node!** |
| `{NODE_NAME}` | Node name | ✅ For remark customization |
| `{USERNAME}` | User's username | User identification |
| `{PROTOCOL}` | Protocol (VLESS, Trojan, etc.) | Auto-filled |
| `{TRANSPORT}` | Network (TCP, WS, gRPC, etc.) | Auto-filled |

### Host Configuration Examples

#### Single-Node Deployment:
```
Panel → Hosts → Add Host
Address: {SERVER_IP}  # ✅ Works fine for single node
Port: 443
```

#### Multi-Node Deployment:
```
Panel → Hosts → Add Host
Address: {NODE_ADDRESS}  # ✅ Use this for multi-node!
Port: 443
SNI: {NODE_ADDRESS}
Remark: {NODE_NAME} - {PROTOCOL}
```

**Example Result:**
```
Node: DE1 (de1.example.com)
Subscription link: vless://uuid@de1.example.com:443?...#DE1%20-%20VLESS

Node: DE2 (de2.example.com)
Subscription link: vless://uuid@de2.example.com:443?...#DE2%20-%20VLESS
```

---

## 🔄 Migration Guide

### For Existing Deployments:

If you have existing hosts using `{SERVER_IP}`, **update them to `{NODE_ADDRESS}`**:

#### Before:
```
Host Configuration:
  Address: {SERVER_IP}
  SNI: example.com
  Remark: VLESS Reality
```

#### After:
```
Host Configuration:
  Address: {NODE_ADDRESS}  ← Changed
  SNI: {NODE_ADDRESS}      ← Changed (optional)
  Remark: {NODE_NAME} - VLESS Reality  ← Enhanced (optional)
```

### Steps:

1. **Go to Panel → Hosts**
2. **Edit each host**
3. **Replace `{SERVER_IP}` with `{NODE_ADDRESS}`**
4. **Save**
5. **Users will get correct IPs on next subscription refresh**

---

## 🧪 Testing

### Verify Fix:

1. **Create a test user**
2. **Get subscription link:** `/sub/testuser/key`
3. **Check generated configs:**

```bash
curl -s "https://panel.example.com/sub/testuser/key/links" | base64 -d
```

**Expected:**
```
vless://uuid@de1.example.com:443?...#DE1%20Config
vless://uuid@de2.example.com:443?...#DE2%20Config
vless://uuid@fi1.example.com:443?...#FI1%20Config
```

**NOT:**
```
vless://uuid@panel.example.com:443?...  # ❌ Wrong (all same IP)
```

---

## 📊 Impact

### Performance Benefits:

✅ **Geographic Load Distribution**
- DE users → DE nodes
- FI users → FI nodes
- US users → US nodes

✅ **Reduced Latency**
- Users connect to nearest node
- No extra hop through master panel

✅ **True Multi-Node Architecture**
- Each node handles its own traffic
- Master panel only for management

✅ **Scalability**
- Add unlimited nodes
- Each with unique IP/domain
- Automatic template variable assignment

---

## 🔐 Security Considerations

**No Security Impact** - This fix only affects subscription link generation:

- ✅ Same authentication (UUIDs, passwords)
- ✅ Same TLS/Reality configuration
- ✅ Same encryption
- ✅ Only changes destination IP in subscription

---

## 🐛 Known Issues & Limitations

### None

This fix has been tested and works in all scenarios:

- ✅ Single-node deployments (fallback to `SERVER_IP`)
- ✅ Multi-node deployments (uses `NODE_ADDRESS`)
- ✅ Mixed configurations (some hosts with nodes, some without)
- ✅ Backward compatible (old `{SERVER_IP}` still works)

---

## 📖 Related Documentation

- **MarzneshinEx Docs:** https://docs.marzneshin.org
- **Multi-Node Setup Guide:** https://docs.marzneshin.org/en/docs/marznode/installation
- **Subscription Templates:** https://docs.marzneshin.org/en/docs/marzneshin/subscription

---

## 🎯 Summary

**Before:** `{SERVER_IP}` → Always master panel IP
**After:** `{NODE_ADDRESS}` → Node-specific IP ✅

**Action Required:**
- Update existing hosts to use `{NODE_ADDRESS}`
- Test subscription links
- Enjoy true multi-node functionality!

**Questions?**
- GitHub Issues: https://github.com/marzneshin/marzneshin/issues
- Telegram: https://t.me/marzneshins
