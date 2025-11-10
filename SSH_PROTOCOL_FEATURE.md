# SSH Protocol Support & Tunneling

## Overview

**SSH (Secure Shell) Protocol** support allows users to create secure tunnels for their traffic using SSH's built-in port forwarding capabilities. While Marzneshin doesn't natively implement SSH servers, this guide explains how SSH can be used alongside Marzneshin for enhanced security, compatibility, and tunneling scenarios.

## Table of Contents

- [What is SSH Tunneling](#what-is-ssh-tunneling)
- [Why Use SSH with Proxies](#why-use-ssh-with-proxies)
- [SSH Tunnel Types](#ssh-tunnel-types)
- [Integration with Marzneshin](#integration-with-marzneshin)
- [Setup Guides](#setup-guides)
- [Use Cases](#use-cases)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Comparison with Other Protocols](#comparison-with-other-protocols)

---

## What is SSH Tunneling

SSH (Secure Shell) tunneling uses SSH's port forwarding feature to create encrypted connections between local and remote machines.

### Key Concepts

**SSH Port Forwarding Types:**
1. **Local Port Forwarding** - Forward local port to remote server
2. **Remote Port Forwarding** - Forward remote port to local machine
3. **Dynamic Port Forwarding** - Create SOCKS proxy via SSH

### How It Works

```
Client → SSH Tunnel (Encrypted) → SSH Server → Destination
         ↑ Port 22 (or custom)    ↑ Port Forward
```

**Benefits:**
- ✅ Encrypted traffic (SSH encryption)
- ✅ Wide compatibility (SSH available everywhere)
- ✅ Flexible port forwarding
- ✅ SOCKS proxy capability
- ✅ File transfer (SCP/SFTP)

---

## Why Use SSH with Proxies

### Advantages

1. **Universal Availability**
   - SSH client on every Linux/Mac by default
   - Available on Windows (PuTTY, OpenSSH)
   - No special client software needed

2. **Strong Encryption**
   - Industry-standard cryptography
   - Perfect forward secrecy
   - Well-audited security

3. **Multi-Purpose**
   - Port forwarding
   - SOCKS proxy
   - File transfer
   - Remote shell access

4. **Bypass Restrictions**
   - SSH traffic looks legitimate
   - Often allowed through firewalls
   - Can use port 443 to mimic HTTPS

---

## SSH Tunnel Types

### 1. Local Port Forwarding

Forward local port to remote destination:

```bash
ssh -L [local_port]:[destination]:[remote_port] user@ssh-server
```

**Example:**
```bash
# Forward local port 8080 to remote web server
ssh -L 8080:localhost:80 user@ssh-server
# Access via: http://localhost:8080
```

---

### 2. Remote Port Forwarding

Forward remote port back to local machine:

```bash
ssh -R [remote_port]:[destination]:[local_port] user@ssh-server
```

**Example:**
```bash
# Expose local service on remote server
ssh -R 8080:localhost:3000 user@ssh-server
# Remote server port 8080 → your local port 3000
```

---

### 3. Dynamic Port Forwarding (SOCKS Proxy)

Create SOCKS proxy through SSH:

```bash
ssh -D [local_port] user@ssh-server
```

**Example:**
```bash
# Create SOCKS proxy on localhost:1080
ssh -D 1080 user@ssh-server
# Configure browser: SOCKS5 → localhost:1080
```

---

## Integration with Marzneshin

Marzneshin doesn't provide native SSH server functionality, but you can combine SSH with Marzneshin proxies for enhanced capabilities:

### Architecture Options

#### Option 1: SSH → Marzneshin Proxy

```
User → SSH Tunnel → VPS (SSH Server) → Marzneshin Proxy → Internet
       ↑ Encrypted           ↑ Local access to proxy
```

**Benefits:**
- Additional encryption layer
- Hide proxy traffic inside SSH
- Access local-only Marzneshin services

---

#### Option 2: Marzneshin Proxy → SSH

```
User → Marzneshin Proxy → Internet → SSH Server → Destination
       ↑ First layer                 ↑ Second layer
```

**Benefits:**
- Double-hop anonymity
- Proxy chain
- Bypass multiple restrictions

---

#### Option 3: Parallel Deployment

```
User
  ├─ SSH Tunnel (Port 22) → For SSH-specific needs
  └─ Marzneshin Proxy (Port 443) → For general proxy traffic
```

**Benefits:**
- Best of both worlds
- Use SSH for secure shell
- Use proxy for general internet

---

## Setup Guides

### Setup 1: Enable SSH Server on Your VPS

**Install OpenSSH Server:**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install openssh-server

# CentOS/RHEL
sudo yum install openssh-server

# Start SSH service
sudo systemctl start sshd
sudo systemctl enable sshd
```

**Configure SSH (`/etc/ssh/sshd_config`):**

```bash
# Security hardening
Port 22                          # Or custom port (e.g., 2222)
PermitRootLogin no               # Disable root login
PasswordAuthentication no        # Use key-based auth only
PubkeyAuthentication yes
AllowTcpForwarding yes           # Enable tunneling
GatewayPorts no                  # Security
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 60
ClientAliveCountMax 3

# Restart SSH
sudo systemctl restart sshd
```

---

### Setup 2: SSH Key Authentication

**Generate SSH Key (on client):**

```bash
# Generate Ed25519 key (recommended)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Or RSA key (wider compatibility)
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Keys saved to ~/.ssh/id_ed25519 and ~/.ssh/id_ed25519.pub
```

**Copy Key to Server:**

```bash
# Using ssh-copy-id
ssh-copy-id user@server-ip

# Or manually
cat ~/.ssh/id_ed25519.pub | ssh user@server-ip "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

**Test Connection:**

```bash
ssh user@server-ip
# Should login without password
```

---

### Setup 3: Create SOCKS Proxy via SSH

**Basic SOCKS Proxy:**

```bash
# Create SOCKS proxy on port 1080
ssh -D 1080 -C -N user@server-ip

# Flags:
# -D 1080  : Dynamic port forwarding (SOCKS)
# -C       : Compression
# -N       : No remote command (tunnel only)
```

**Background SOCKS Proxy:**

```bash
# Run in background
ssh -D 1080 -C -N -f user@server-ip

# -f : Background mode
```

**Auto-Reconnect SOCKS Proxy:**

```bash
# Create persistent tunnel with autossh
sudo apt install autossh

autossh -M 0 -D 1080 -C -N \
  -o "ServerAliveInterval 30" \
  -o "ServerAliveCountMax 3" \
  user@server-ip
```

**Configure Browser:**

1. Firefox:
   - Settings → Network Settings → Manual proxy
   - SOCKS Host: `localhost`, Port: `1080`
   - Select `SOCKS v5`
   - Enable "Proxy DNS when using SOCKS v5"

2. Chrome (via command line):
   ```bash
   google-chrome --proxy-server="socks5://localhost:1080"
   ```

---

### Setup 4: SSH + Marzneshin Combined

**Forward SSH to Access Marzneshin Locally:**

```bash
# Forward local port 8080 to Marzneshin panel
ssh -L 8080:localhost:8000 user@server-ip

# Access Marzneshin panel at: http://localhost:8080
```

**Access Marzneshin Proxy via SSH Tunnel:**

```bash
# Scenario: Marzneshin VLESS proxy on server port 8443
# Create tunnel to access proxy locally

ssh -L 8443:localhost:8443 user@server-ip

# Configure V2Ray client:
# Server: localhost
# Port: 8443
# (All traffic encrypted via SSH)
```

---

## Use Cases

### Use Case 1: Secure Shell Access to VPS

**Scenario:** Remotely manage Marzneshin panel server

**Setup:**
```bash
# Connect to server
ssh user@server-ip

# Manage Marzneshin
sudo systemctl status marzneshin
docker logs marzneshin
```

**Benefits:**
- Secure remote administration
- File transfer (SCP/SFTP)
- Log viewing and debugging

---

### Use Case 2: SOCKS Proxy for Censored Regions

**Scenario:** User needs simple proxy in restrictive country

**Setup:**
```bash
# Server-side: Enable SSH (done above)

# Client-side: Create SOCKS proxy
ssh -D 1080 -C -N user@server-ip

# Configure apps to use SOCKS5://localhost:1080
```

**Benefits:**
- No special client software
- SSH usually not blocked
- Works on any device with SSH client

---

### Use Case 3: Access Local-Only Marzneshin Panel

**Scenario:** Marzneshin panel bound to localhost only (security)

**Setup:**
```bash
# Marzneshin running on localhost:8000 (not exposed)

# Create SSH tunnel
ssh -L 8080:localhost:8000 user@server-ip

# Access panel via: http://localhost:8080
```

**Benefits:**
- Enhanced security (panel not publicly accessible)
- Access only via SSH tunnel
- Audit trail via SSH logs

---

### Use Case 4: Double-Hop Anonymity

**Scenario:** Maximum privacy with chained proxies

**Setup:**
```bash
# First hop: SSH SOCKS proxy
ssh -D 1080 user@first-server

# Second hop: Configure Marzneshin proxy to use first proxy
# In V2Ray/Xray client:
# Outbound → Use SOCKS5 localhost:1080 as first hop
```

**Benefits:**
- Two-layer anonymity
- Different jurisdictions
- Harder to trace

---

## Best Practices

### 1. Security Hardening

**Disable Password Authentication:**
```bash
# /etc/ssh/sshd_config
PasswordAuthentication no
PubkeyAuthentication yes
```

**Use Non-Standard Port:**
```bash
# Change from 22 to reduce automated attacks
Port 2222
```

**Limit User Access:**
```bash
# Allow only specific users
AllowUsers user1 user2

# Or allow only specific groups
AllowGroups sshusers
```

**Enable Fail2Ban:**
```bash
sudo apt install fail2ban

# Configure to block brute-force attempts
sudo systemctl enable fail2ban
```

---

### 2. Performance Optimization

**Enable Compression:**
```bash
# Client-side
ssh -C user@server

# Server-side (/etc/ssh/sshd_config)
Compression yes
```

**Use Faster Ciphers:**
```bash
# Modern, fast ciphers
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
```

**Multiplex Connections:**
```bash
# ~/.ssh/config
Host server-ip
    ControlMaster auto
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ControlPersist 600
```

---

### 3. Automation

**Auto-Reconnect SSH Tunnel:**

Create systemd service:

```ini
# /etc/systemd/system/ssh-tunnel.service
[Unit]
Description=SSH Tunnel to VPS
After=network.target

[Service]
User=yourusername
ExecStart=/usr/bin/autossh -M 0 -N -D 1080 -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" user@server-ip
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ssh-tunnel
sudo systemctl start ssh-tunnel
```

---

## Troubleshooting

### Problem: Connection refused

**Symptoms:** `ssh: connect to host X port 22: Connection refused`

**Diagnosis:**
```bash
# Check if SSH is running on server
sudo systemctl status sshd

# Check if port is open
sudo ss -tlnp | grep ssh

# Check firewall
sudo ufw status
```

**Solutions:**
- Start SSH service: `sudo systemctl start sshd`
- Allow SSH in firewall: `sudo ufw allow 22/tcp`
- Check cloud firewall rules (AWS Security Groups, etc.)

---

### Problem: Permission denied (publickey)

**Symptoms:** `Permission denied (publickey)`

**Diagnosis:**
```bash
# Check if public key is in authorized_keys
cat ~/.ssh/authorized_keys

# Check SSH key agent
ssh-add -l
```

**Solutions:**
```bash
# Add key to agent
ssh-add ~/.ssh/id_ed25519

# Fix permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# Re-copy key
ssh-copy-id user@server-ip
```

---

### Problem: Tunnel closes after idle time

**Symptoms:** SSH tunnel disconnects after period of inactivity

**Solution:**
```bash
# Client-side: Keep connection alive
ssh -D 1080 -o ServerAliveInterval=60 -o ServerAliveCountMax=3 user@server

# Server-side: /etc/ssh/sshd_config
ClientAliveInterval 60
ClientAliveCountMax 3
```

---

## Comparison with Other Protocols

| Feature | SSH Tunnel | VPN (Wireguard) | V2Ray/Xray | Shadowsocks |
|---------|-----------|-----------------|------------|-------------|
| **Setup Complexity** | 🟢 Easy | 🟡 Medium | 🟡 Medium | 🟢 Easy |
| **Performance** | 🟡 Good | 🟢 Excellent | 🟢 Excellent | 🟢 Excellent |
| **Encryption** | 🟢 Strong | 🟢 Strong | 🟢 Strong | 🟢 Strong |
| **Port Forwarding** | 🟢 Native | ❌ No | 🟡 Via config | ❌ No |
| **SOCKS Proxy** | 🟢 Native | ❌ No | 🟢 Yes | 🟢 Yes |
| **Shell Access** | 🟢 Native | ❌ No | ❌ No | ❌ No |
| **DPI Resistance** | 🟡 Medium | 🟡 Medium | 🟢 High | 🟢 High |
| **Universal Client** | 🟢 Built-in | 🟡 Install needed | 🟡 Install needed | 🟡 Install needed |
| **Multi-Use** | 🟢 Shell+Tunnel | 🟢 Full VPN | 🟢 Proxy | 🟢 Proxy |

**When to Use Each:**

- **SSH**: Remote administration, quick SOCKS proxy, port forwarding
- **VPN**: Full network tunnel, all traffic routing
- **V2Ray/Xray**: Advanced proxy, DPI evasion, protocol obfuscation
- **Shadowsocks**: Fast proxy, simple setup, good performance

---

## Advanced Configurations

### Multi-Hop SSH Tunnel

**Scenario:** Chain multiple SSH servers

```bash
# Jump through intermediate server
ssh -J user1@jump-server user2@final-server

# Or with ProxyJump in ~/.ssh/config:
Host final-server
    HostName final-server-ip
    User user2
    ProxyJump user1@jump-server
```

---

### SSH over SSL (Stunnel)

**Scenario:** Disguise SSH as HTTPS

**Setup Stunnel:**

```bash
# Server-side
sudo apt install stunnel4

# /etc/stunnel/stunnel.conf
[ssh-ssl]
accept = 443
connect = 127.0.0.1:22
cert = /etc/stunnel/stunnel.pem

# Client-side
[ssh-ssl]
client = yes
accept = 127.0.0.1:2222
connect = server-ip:443
```

**Connect:**
```bash
ssh -p 2222 user@localhost
# Actually connects to server-ip:443 via SSL
```

---

### SSH + Tor for Anonymity

**Combine SSH with Tor:**

```bash
# Install tor
sudo apt install tor

# Start tor
sudo systemctl start tor

# SSH via Tor
ssh -o ProxyCommand="nc -X 5 -x 127.0.0.1:9050 %h %p" user@server-onion-address.onion
```

---

## Limitations & Considerations

### SSH Limitations

❌ **Not Designed for High-Speed Proxying**
- SSH overhead can reduce throughput
- Better for occasional use, not 24/7 traffic

❌ **Single-Stream Performance**
- SSH tunnels are single TCP streams
- May be slower than multi-stream protocols

❌ **Server Resource Usage**
- Each SSH connection = separate process
- Many connections can stress server

### When SSH May Not Be Ideal

- High-bandwidth streaming (use VPN/proxy instead)
- Many concurrent users (use dedicated proxy)
- Mobile devices (battery drain from persistent SSH)

### Recommendations

✅ **Use SSH For:**
- Remote server administration
- Quick, temporary SOCKS proxy
- Port forwarding specific services
- Secure file transfers

✅ **Use Marzneshin/Xray For:**
- Permanent proxy service
- Many users
- High-performance requirements
- Advanced protocol features

---

## Integration Example: Complete Setup

**Scenario:** Marzneshin server with SSH for admin access

**1. Install Marzneshin:**
```bash
# Install Marzneshin (assuming Docker)
docker run -d --name marzneshin \
  -p 8000:8000 \
  -p 8443:8443 \
  gozargah/marzneshin
```

**2. Configure SSH:**
```bash
# Install SSH server
sudo apt install openssh-server

# Secure SSH config
sudo nano /etc/ssh/sshd_config
# Port 2222
# PasswordAuthentication no
# PermitRootLogin no

sudo systemctl restart sshd
```

**3. Access Marzneshin Panel via SSH:**
```bash
# From client machine
ssh -L 8080:localhost:8000 user@server-ip -p 2222

# Open browser: http://localhost:8080
```

**4. User Connections:**
- Admins: SSH tunnel to panel (secure)
- End users: Marzneshin proxy subscriptions (fast)

---

## Conclusion

While **SSH is not natively implemented in Marzneshin**, it serves as an excellent **complementary tool**:

**For Administrators:**
- Secure server access
- Safe panel administration
- Port forwarding for local-only services

**For Users:**
- Quick SOCKS proxy (no special client)
- Temporary secure tunnel
- Bypass restrictions in emergency

**Best Practice:**
Use **Marzneshin for general proxy services** and **SSH for administrative tasks**. They complement each other perfectly.

---

## Related Features

- [Telegram MTProto Proxy](./TELEGRAM_MTPROTO_PROXY_FEATURE.md)
- [QUIC Protocol Support](./QUIC_PROTOCOL_FEATURE.md)
- [DNS over HTTPS](./DNS_OVER_HTTPS_FEATURE.md)
- [User Control Panel](./USER_CONTROL_PANEL_FEATURE.md)

---

## References

- [OpenSSH Official Documentation](https://www.openssh.com/manual.html)
- [SSH Tunneling Guide](https://www.ssh.com/academy/ssh/tunneling)
- [Autossh Documentation](https://www.harding.motd.ca/autossh/)
- [SSH Security Best Practices](https://infosec.mozilla.org/guidelines/openssh)

---

**Last Updated:** 2025-01-10
**Feature Status:** Supported as system-level tool (not Marzneshin-native)
**Recommendation:** Use SSH for administration, Marzneshin for proxying
