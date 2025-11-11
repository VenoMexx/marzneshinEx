# ShadowTLS Subscription Generation Sorunu ve Çözümü

## Sorun

ShadowTLS inbound'ları panel'de düzgün çalışıyor ama subscription generation'da görünmüyor.

**Kök Neden:** ShadowTLS için standart bir URI scheme (`shadowtls://...`) formatı YOK.

## Teknik Analiz

### Desteklenen Protokoller vs ShadowTLS

| Protokol | URI Scheme | v2share Desteği | Standart Format |
|----------|------------|-----------------|-----------------|
| Shadowsocks | `ss://...` | ✅ | ✅ RFC-style |
| VMess | `vmess://...` | ✅ | ✅ Dokümante |
| VLESS | `vless://...` | ✅ | ✅ Dokümante |
| Trojan | `trojan://...` | ✅ | ✅ Dokümante |
| TUIC | `tuic://...` | ✅ | ✅ Dokümante |
| Hysteria2 | `hysteria2://...` | ✅ | ✅ Dokümante |
| **ShadowTLS** | ❌ YOK | ❌ | ❌ **Tanımsız** |

### v2share Kütüphanesi

**Versiyon:** `0.1.0b31` (6 Mart 2025 - EN GÜNCEL)

**Kod Analizi:**
```python
# v2share/data.py - to_link() method
# ShadowTLS handler YOK, ProtocolNotSupportedError fırlatıyor

def to_link(self):
    if self.protocol == "shadowsocks": ...
    elif self.protocol == "vmess": ...
    elif self.protocol == "vless": ...
    elif self.protocol == "tuic": ...
    # ... shadowtls YOK!
    else:
        raise ProtocolNotSupportedError
```

### ShadowTLS Paylaşım Yöntemleri

1. **sing-box JSON Config:**
```json
{
  "type": "shadowtls",
  "server": "example.com",
  "server_port": 4201,
  "version": 3,
  "password": "password123",
  "tls": {
    "enabled": true,
    "server_name": "www.google.com"
  }
}
```

2. **Surge Formatı:**
```
STLS = snell, 1.2.3.4, 443, psk=pwd1, shadow-tls-password=pwd2, shadow-tls-version=3
```

3. **Manuel Client Configuration**

---

## Çözüm Seçenekleri

### ✅ Seçenek 1: Sing-box JSON Config Export (ÖNERİLEN)

ShadowTLS için subscription **link** yerine **JSON config** sağla.

**장점:**
- ✅ v2share zaten sing-box config generation destekliyor
- ✅ Sing-box client'lar direk import edebilir
- ✅ Standart format (dokümante)
- ✅ Kod değişikliği gerekmez

**Nasıl Kullanılır:**

1. **Subscription URL Format Değişikliği:**
```bash
# Link format (çalışmaz):
https://panel.com/sub/user/token

# Sing-box format (çalışır):
https://panel.com/sub/user/token?format=sing-box
```

2. **Client Import:**
```bash
# sing-box client:
sing-box run -c subscription.json

# import command:
curl "https://panel.com/sub/user/token?format=sing-box" -o config.json
```

**Mevcut Durum Kontrolü:**

Marzneshin zaten sing-box formatını destekliyor:
```python
# app/utils/share.py:59-66
subscription_handlers: dict[str, Type[BaseConfig]] = {
    "links": LinksConfig,
    "xray": XrayConfig,
    "clash-meta": ClashMetaConfig,
    "clash": ClashConfig,
    "sing-box": SingBoxConfig,  # ← MEVCUT!
    "wireguard": WireGuardConfig,
}
```

**Test:**
```bash
# Panel'de ShadowTLS host'u olan bir user için:
curl "https://your-panel.com/sub/testuser/TOKEN?format=sing-box"

# Çıktı: sing-box JSON config (ShadowTLS dahil)
```

---

### 🔧 Seçenek 2: Custom URI Scheme (Standart Dışı)

Kendi `shadowtls://` formatını tanımla.

**Format Önerisi:**
```
shadowtls://password@host:port?version=3&sni=google.com&detour=ss-internal#remark
```

**Implementasyon:**

`app/utils/share.py` dosyasına ekle:

```python
def generate_shadowtls_link(host, password, format_variables) -> str:
    """
    Generate custom ShadowTLS URI (non-standard format)

    Format: shadowtls://password@host:port?version=3&sni=google.com#remark
    """
    from urllib.parse import quote, urlencode

    # Base credentials
    credentials = f"{quote(password)}"
    address = host.address.format_map(format_variables)
    port = host.port

    # Query parameters
    params = {}
    if host.shadowtls_version:
        params['version'] = host.shadowtls_version
    if host.sni:
        params['sni'] = host.sni.format_map(format_variables)
    if host.shadowsocks_method:
        params['method'] = host.shadowsocks_method

    # Remark
    remark = host.remark.format_map(format_variables)

    # Build URI
    query = f"?{urlencode(params)}" if params else ""
    link = f"shadowtls://{credentials}@{address}:{port}{query}#{quote(remark)}"

    return link
```

**v2share Patch:**

`create_config` fonksiyonunu değiştir:

```python
# app/utils/share.py:406
def create_config(host, key, format_variables, salt, user_id, next_hosts=None):
    # ... mevcut kod ...

    # ShadowTLS için özel işlem
    if protocol == "shadowtls":
        # Custom link generator kullan
        return generate_shadowtls_link(host, auth_password, format_variables)

    # Normal v2share flow
    data = V2Data(...)
    return data
```

**Dezavantajlar:**
- ⚠️ Client'lar tanımayabilir (standart değil)
- ⚠️ Manuel parse gerekir
- ⚠️ Bakım maliyeti yüksek

---

### 🚫 Seçenek 3: Links Formatından Hariç Tut

En basit ama en kısıtlı çözüm.

**Implementasyon:**

`app/utils/share.py` dosyasında filter ekle:

```python
def generate_subscription(...):
    # ... mevcut kod ...

    # ShadowTLS host'larını filtrele (sadece links formatında)
    if config_format == "links":
        configs = [
            c for c in configs
            if c.protocol != "shadowtls"
        ]

    # ... devam ...
```

**User Bilgilendirmesi:**

Panel UI'da uyarı göster:
```
⚠️ ShadowTLS subscription links desteklenmiyor.
   Lütfen sing-box JSON config formatını kullanın.

   Sing-box config: /sub/USERNAME/TOKEN?format=sing-box
```

---

## Önerilen Uygulama

### Kısa Vadeli (Hemen Uygulanabilir):

**1. Sing-box Format Kullanımını Teşvik Et:**

Panel dashboard'a bilgilendirme ekle:

```python
# app/templates/user_panel.html
<div class="protocol-info">
  <p><strong>ShadowTLS Users:</strong></p>
  <p>Please use sing-box JSON format for subscription:</p>
  <code>/sub/{{ username }}/{{ token }}?format=sing-box</code>
</div>
```

**2. API Documentation Güncelle:**

```markdown
## Subscription Formats

- **links**: One-click links (vmess://, vless://, ss://, etc.)
  - ⚠️ Does NOT support ShadowTLS

- **sing-box**: JSON config (ALL protocols including ShadowTLS)
  - ✅ Recommended for ShadowTLS users

- **clash**: YAML config (partial ShadowTLS support)
```

### Uzun Vadeli (v2share Katkısı):

**v2share Repository'ye PR Gönder:**

1. ShadowTLS URI scheme standardı öner
2. `to_link()` metoduna ShadowTLS handler ekle
3. Community ile standart belirle

**Örnek PR Başlığı:**
```
feat: Add ShadowTLS link generation support

Implements shadowtls:// URI scheme:
- Format: shadowtls://password@host:port?version=3&sni=domain#remark
- Compatible with sing-box clients
- Follows similar pattern to ss:// and tuic:// schemes
```

---

## Test Senaryosu

### Test 1: Sing-box Format (Çalışmalı)

```bash
# ShadowTLS host'u olan user için:
curl "https://panel.com/sub/testuser/TOKEN?format=sing-box" | jq .

# Beklenen çıktı:
{
  "outbounds": [
    {
      "type": "shadowtls",
      "tag": "shadowtls-4201",
      "server": "example.com",
      "server_port": 4201,
      "version": 3,
      "password": "password123",
      ...
    }
  ]
}
```

### Test 2: Links Format (Boş veya Filtrelenmiş)

```bash
curl "https://panel.com/sub/testuser/TOKEN?format=links"

# Beklenen çıktı (eğer sadece ShadowTLS varsa):
# (boş veya diğer protokoller)
```

### Test 3: Client Import

```bash
# Sing-box client ile import:
curl "https://panel.com/sub/testuser/TOKEN?format=sing-box" -o config.json
sing-box check -c config.json  # ← Config geçerli olmalı
sing-box run -c config.json    # ← Bağlantı çalışmalı
```

---

## Özet

| Çözüm | Uygulanabilirlik | Client Desteği | Standart Uyumluluk | Tavsiye |
|-------|------------------|----------------|-------------------|---------|
| **Sing-box JSON** | ✅ Hemen | ✅ Mükemmel | ✅ Standart | 🌟 ÖNERİLEN |
| **Custom URI** | 🔧 Patch gerekli | ⚠️ Kısıtlı | ❌ Standart dışı | ⚠️ Son çare |
| **Filtrele** | ✅ Basit | ❌ YOK | ✅ Problem yok | 💡 Geçici |

**En İyi Yaklaşım:**

1. ✅ **Sing-box JSON formatını kullanın** (subscription link yerine)
2. ✅ **User'ları bilgilendirin** (panel UI'da açıklama)
3. 🔄 **v2share'e katkı yapın** (uzun vadeli standart için)

---

## Hızlı Başlangıç

### Panel Kullanıcıları İçin:

**ShadowTLS Subscription Alma:**

```bash
# ❌ Çalışmaz (link format):
https://panel.com/sub/username/token

# ✅ Çalışır (sing-box format):
https://panel.com/sub/username/token?format=sing-box
```

**Sing-box Client Kurulumu:**

```bash
# sing-box client indir:
# https://github.com/SagerNet/sing-box/releases

# Config indir:
curl "https://panel.com/sub/username/token?format=sing-box" -o config.json

# sing-box çalıştır:
sing-box run -c config.json
```

**Android/iOS:**

- **sing-box** app indir
- **Subscription URL** ekle: `https://panel.com/sub/username/token?format=sing-box`
- **Format**: JSON seç
- **Import** tıkla

---

## Kaynaklar

- [sing-box ShadowTLS Dokümantasyonu](https://sing-box.sagernet.org/configuration/outbound/shadowtls/)
- [v2share GitHub Repository](https://github.com/khodedawsh/v2share)
- [ShadowTLS Protocol Specification](https://github.com/ihciah/shadow-tls/blob/master/docs/protocol-v3-en.md)
- [Marzneshin Subscription API](/api/docs#/subscription)
