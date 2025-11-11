# Sing-box Inbound Manuel Konfigürasyon Kılavuzu

## Sorun
Marzneshin'de **Panel → Marznode → Sing-box** yönünde otomatik inbound sync mekanizması YOK.
Sadece **Marznode → Panel** yönünde sync var.

Database'de oluşturduğunuz inbound'lar sing-box'a otomatik eklenmez.

## Çözüm
Reality, TUIC, ShadowTLS inbound'larını **manuel olarak sing-box config'ine eklemeniz gerekiyor**.

---

## VLESS Reality (Port 2087) Konfigürasyonu

```json
{
  "type": "vless",
  "tag": "vless-reality-2087",
  "listen": "::",
  "listen_fields": {
    "listen": "::",
    "listen_port": 2087
  },
  "sniff": true,
  "sniff_override_destination": false,
  "domain_strategy": "prefer_ipv4",
  "users": [],
  "tls": {
    "enabled": true,
    "server_name": "www.google.com",
    "reality": {
      "enabled": true,
      "handshake": {
        "server": "www.google.com",
        "server_port": 443
      },
      "private_key": "YOUR_PRIVATE_KEY_HERE",
      "short_id": [
        "",
        "0123456789abcdef"
      ]
    }
  }
}
```

### Reality Keys Oluşturma:
```bash
# Marznode sunucusunda:
/usr/local/bin/sing-box generate reality-keypair

# Çıktı:
# PrivateKey: kJW...
# PublicKey: zMn...
```

**PrivateKey'i** sing-box config'e ekle
**PublicKey'i** panel'deki host ayarlarında kullanacaksın

---

## TUIC (Port 2096) Konfigürasyonu

```json
{
  "type": "tuic",
  "tag": "tuic-2096",
  "listen": "::",
  "listen_fields": {
    "listen": "::",
    "listen_port": 2096
  },
  "sniff": true,
  "sniff_override_destination": false,
  "users": [],
  "congestion_control": "bbr",
  "auth_timeout": "3s",
  "zero_rtt_handshake": false,
  "heartbeat": "10s",
  "tls": {
    "enabled": true,
    "server_name": "example.com",
    "alpn": [
      "h3"
    ],
    "certificate_path": "/var/lib/marznode/certs/fullchain.pem",
    "key_path": "/var/lib/marznode/certs/privkey.pem"
  }
}
```

### SSL Sertifikası Oluşturma (TUIC için gerekli):
```bash
# Certbot ile:
certbot certonly --standalone -d your-domain.com

# Sertifikaları kopyala:
mkdir -p /var/lib/marznode/certs
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /var/lib/marznode/certs/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem /var/lib/marznode/certs/
chown marznode:marznode /var/lib/marznode/certs/*
```

---

## ShadowTLS (Port 4201) Konfigürasyonu

```json
{
  "type": "shadowtls",
  "tag": "shadowtls-4201",
  "listen": "::",
  "listen_fields": {
    "listen": "::",
    "listen_port": 4201
  },
  "version": 3,
  "users": [],
  "handshake": {
    "server": "www.google.com",
    "server_port": 443
  },
  "strict_mode": true,
  "detour": "shadowsocks-internal"
}
```

ShadowTLS için ek bir **Shadowsocks inbound** gerekli (internal):
```json
{
  "type": "shadowsocks",
  "tag": "shadowsocks-internal",
  "listen": "127.0.0.1",
  "listen_fields": {
    "listen": "127.0.0.1",
    "listen_port": 4202
  },
  "network": "tcp",
  "method": "2022-blake3-aes-128-gcm",
  "password": "GENERATE_A_PASSWORD_HERE",
  "users": []
}
```

Password oluşturma:
```bash
openssl rand -base64 16
```

---

## Tam Sing-box Config Örneği

```json
{
  "log": {
    "level": "warn",
    "timestamp": true
  },
  "inbounds": [
    {
      "type": "hysteria2",
      "tag": "hysteria2-443",
      "listen": "::",
      "listen_fields": {
        "listen": "::",
        "listen_port": 443
      },
      "users": [],
      "up_mbps": 100,
      "down_mbps": 100,
      "tls": {
        "enabled": true,
        "alpn": ["h3"],
        "certificate_path": "/var/lib/marznode/certs/fullchain.pem",
        "key_path": "/var/lib/marznode/certs/privkey.pem"
      }
    },
    {
      "type": "vless",
      "tag": "vless-reality-2087",
      "listen": "::",
      "listen_fields": {
        "listen": "::",
        "listen_port": 2087
      },
      "users": [],
      "tls": {
        "enabled": true,
        "server_name": "www.google.com",
        "reality": {
          "enabled": true,
          "handshake": {
            "server": "www.google.com",
            "server_port": 443
          },
          "private_key": "YOUR_REALITY_PRIVATE_KEY",
          "short_id": ["", "0123456789abcdef"]
        }
      }
    },
    {
      "type": "tuic",
      "tag": "tuic-2096",
      "listen": "::",
      "listen_fields": {
        "listen": "::",
        "listen_port": 2096
      },
      "users": [],
      "congestion_control": "bbr",
      "auth_timeout": "3s",
      "zero_rtt_handshake": false,
      "heartbeat": "10s",
      "tls": {
        "enabled": true,
        "server_name": "your-domain.com",
        "alpn": ["h3"],
        "certificate_path": "/var/lib/marznode/certs/fullchain.pem",
        "key_path": "/var/lib/marznode/certs/privkey.pem"
      }
    },
    {
      "type": "shadowtls",
      "tag": "shadowtls-4201",
      "listen": "::",
      "listen_fields": {
        "listen": "::",
        "listen_port": 4201
      },
      "version": 3,
      "users": [],
      "handshake": {
        "server": "www.google.com",
        "server_port": 443
      },
      "strict_mode": true,
      "detour": "shadowsocks-internal"
    },
    {
      "type": "shadowsocks",
      "tag": "shadowsocks-internal",
      "listen": "127.0.0.1",
      "listen_fields": {
        "listen": "127.0.0.1",
        "listen_port": 4202
      },
      "network": "tcp",
      "method": "2022-blake3-aes-128-gcm",
      "password": "YOUR_SHADOWSOCKS_PASSWORD",
      "users": []
    }
  ],
  "outbounds": [
    {
      "type": "direct",
      "tag": "direct"
    }
  ]
}
```

---

## Adım Adım Uygulama

### 1. Config'i Düzenle
```bash
# Marznode sunucusunda:
nano /var/lib/marznode/sing-box.json
```

Yukarıdaki inbound'ları ekle.

### 2. Config'i Doğrula
```bash
/usr/local/bin/sing-box check -c /var/lib/marznode/sing-box.json
```

Hata varsa gösterecektir.

### 3. Sing-box'ı Restart Et
```bash
systemctl restart sing-box
```

### 4. Portların Açık Olduğunu Kontrol Et
```bash
ss -tulnp | grep -E "2087|2096|4201"
```

Çıktı:
```
udp   LISTEN 0   0   [::]:443    [::]:*    users:(("sing-box",pid=1234))
tcp   LISTEN 0   0   [::]:2087   [::]:*    users:(("sing-box",pid=1234))
udp   LISTEN 0   0   [::]:2096   [::]:*    users:(("sing-box",pid=1234))
tcp   LISTEN 0   0   [::]:4201   [::]:*    users:(("sing-box",pid=1234))
```

### 5. Marznode'u Restart Et (veya Resync)
```bash
systemctl restart marznode
```

Veya panel'den:
```
Panel → Nodes → [Node seç] → Resync
```

### 6. Panel'de İnbound'ları Kontrol Et
```bash
# Panel API:
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-panel.com/api/inbounds
```

Şimdi Reality, TUIC, ShadowTLS inbound'larını görmelisin.

### 7. Host Ekle
Panel → Inbounds → [Reality/TUIC/ShadowTLS seç] → Add Host

---

## Firewall Kuralları

```bash
# UFW:
ufw allow 2087/tcp
ufw allow 2096/udp
ufw allow 4201/tcp

# iptables:
iptables -A INPUT -p tcp --dport 2087 -j ACCEPT
iptables -A INPUT -p udp --dport 2096 -j ACCEPT
iptables -A INPUT -p tcp --dport 4201 -j ACCEPT
iptables-save > /etc/iptables/rules.v4
```

---

## Doğrulama

### Panel'de İnbound'lar Görünüyor mu?
```bash
# Panel database:
sqlite3 /var/lib/marzneshin/db.sqlite3 "SELECT tag, protocol FROM inbounds;"
```

### Sing-box Logları
```bash
journalctl -u sing-box -f
```

### Marznode Logları
```bash
journalctl -u marznode -f
```

---

## Önemli Notlar

1. **`users: []` boş bırakılmalı** - Marznode otomatik olarak user'ları yönetecek
2. **`tag` isimleri benzersiz olmalı** - Aynı tag'den iki tane olamaz
3. **Reality için public key'i panel'de kullan** - Host ayarlarında `reality_public_key` field'ına
4. **TUIC ve Hysteria2 SSL sertifikası gerektirir** - Let's Encrypt kullanın
5. **ShadowTLS internal Shadowsocks gerektirir** - İkisini birlikte ekleyin

---

## Alternatif: Panel'den Backend Config Düzenleme

Panel UI'dan da sing-box config'ini düzenleyebilirsiniz:

1. Panel → Nodes → [Node seç] → Backend Config
2. Sing-box JSON'unu düzenle
3. Save & Restart

Ancak bu yöntem risklidir - syntax hatası sing-box'ı bozabilir.

---

## Gelecek İyileştirme Önerisi

Panel'e **"Add Inbound"** özelliği eklenebilir:

1. Panel UI'dan inbound tanımlarsın
2. Panel otomatik olarak sing-box config'ini günceller
3. Backend'i restart eder
4. Database'e kaydeder

Ancak şu anda böyle bir özellik yok - manuel config gerekli.
