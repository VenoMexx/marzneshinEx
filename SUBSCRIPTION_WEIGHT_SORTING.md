# Subscription Link Weight-Based Sorting

## Özellik

Subscription link'lerinde host'lar **weight değerine göre sıralanır**.

**Yüksek weight → Subscription'da önce gelir**

---

## Teknik Implementasyon

### Değişiklik

`app/db/crud.py` - `get_hosts_for_user()` fonksiyonuna weight sıralaması eklendi:

```python
def get_hosts_for_user(session, user_id):
    # ... query logic ...
    result_query = session.query(InboundHost).filter(
        # ... filters ...
    ).order_by(InboundHost.weight.desc())  # ← YENİ: Weight'e göre sırala (yüksek → düşük)

    return result_query.all()
```

**Sıralama Mantığı:**
- `order_by(InboundHost.weight.desc())` → Descending (büyükten küçüğe)
- Weight 10 olan host, weight 1 olan host'tan **önce** gelir

---

## Kullanım Senaryosu

### Örnek Konfigürasyon:

**Panel'de 3 host tanımlı:**

1. **Premium DE Server**
   - Address: `de1.example.com`
   - Port: 443
   - **Weight: 10** ⭐

2. **Standard FI Server**
   - Address: `fi1.example.com`
   - Port: 443
   - **Weight: 5**

3. **Backup US Server**
   - Address: `us1.example.com`
   - Port: 443
   - **Weight: 1**

### Subscription Link Sırası:

```
User subscription link:
https://panel.com/sub/testuser/TOKEN

Dönen linkler (sıralı):
1. vless://...@de1.example.com:443#Premium%20DE%20Server    ← Weight: 10 (önce)
2. vless://...@fi1.example.com:443#Standard%20FI%20Server   ← Weight: 5
3. vless://...@us1.example.com:443#Backup%20US%20Server     ← Weight: 1  (son)
```

**Client'ta görünüm:**
```
┌─────────────────────────────────────┐
│ Premium DE Server    (de1.example)  │ ← İlk seçili
│ Standard FI Server   (fi1.example)  │
│ Backup US Server     (us1.example)  │
└─────────────────────────────────────┘
```

Client'lar genellikle **ilk server'ı default olarak seçer** → Premium server otomatik kullanılır!

---

## Avantajları

### 1️⃣ Premium Server Önceliği
```
Weight 10 → Premium servers (hızlı, güvenilir)
Weight 5  → Standard servers (normal)
Weight 1  → Backup servers (yedek, yavaş)
```

Users get the **best server by default**!

### 2️⃣ Yük Dengeleme Kontrolü

Admin farklı server'lara farklı priority verebilir:

**Örnek 1: Tek premium server:**
```
DE1: Weight 10  ← %80 kullanıcı buraya bağlanır
FI1: Weight 5
US1: Weight 1
```

**Örnek 2: İki premium server:**
```
DE1: Weight 10  ← %40 kullanıcı
DE2: Weight 10  ← %40 kullanıcı
FI1: Weight 5   ← %20 kullanıcı
```

### 3️⃣ Failover Stratejisi

Client bağlanamayınca **sırayla** diğer server'lara geçer:

```
1. Try: Premium (weight 10) → Başarısız
2. Try: Standard (weight 5) → Başarısız
3. Try: Backup (weight 1)   → Başarılı ✅
```

---

## Test Senaryoları

### Test 1: Basit Sıralama

**Setup:**
```sql
INSERT INTO hosts (remark, address, port, weight) VALUES
  ('Server A', 'a.example.com', 443, 1),
  ('Server B', 'b.example.com', 443, 10),
  ('Server C', 'c.example.com', 443, 5);
```

**Beklenen subscription sırası:**
```
1. Server B (weight 10)
2. Server C (weight 5)
3. Server A (weight 1)
```

**Test:**
```bash
curl "https://panel.com/sub/testuser/TOKEN"

# Çıktı:
vless://...@b.example.com:443#Server%20B
vless://...@c.example.com:443#Server%20C
vless://...@a.example.com:443#Server%20A
```

### Test 2: Aynı Weight

**Setup:**
```sql
INSERT INTO hosts (remark, address, weight) VALUES
  ('Server X', 'x.example.com', 10),
  ('Server Y', 'y.example.com', 10),
  ('Server Z', 'z.example.com', 10);
```

**Beklenen davranış:**
- Hepsi aynı weight → Database insertion order'a göre sıralanır
- Veya ID'ye göre (implementation detail)

**Not:** Aynı weight'te random distribution için shuffle parametresi kullanılabilir.

### Test 3: Weight Güncelleme

**Setup:**
```sql
-- Başlangıç
Server A: weight = 1

-- Güncelleme
UPDATE hosts SET weight = 10 WHERE remark = 'Server A';
```

**Beklenen:**
- Server A artık subscription'da **en üstte** görünmeli
- Real-time değişiklik (DB update sonrası hemen etkili)

---

## API Davranışı

### Subscription Endpoints:

**GET** `/sub/{username}/{token}`
- Weight'e göre **otomatik sıralı** döner
- Admin müdahalesine gerek yok

**GET** `/sub/{username}/{token}?format=sing-box`
- Sing-box JSON config'de de **sıralı** outbounds

**GET** `/sub/{username}/{token}?shuffle=true`
- Weight sıralaması **önce** yapılır
- Sonra shuffle edilir (eğer settings'de aktifse)

---

## Shuffle ile İlişkisi

Weight sıralaması ve shuffle **bağımsız** çalışır:

### Senaryo 1: Shuffle OFF (default)
```python
configs = get_hosts_for_user(db, user_id)  # ← Weight'e göre sıralı
# Shuffle yapılmaz
# Dönen sıra: Weight'e göre
```

**Sonuç:**
```
1. Premium (weight 10)
2. Standard (weight 5)
3. Backup (weight 1)
```

### Senaryo 2: Shuffle ON
```python
configs = get_hosts_for_user(db, user_id)  # ← Weight'e göre sıralı
configs = shuffle(configs)                  # ← Karıştırılır
# Dönen sıra: Random
```

**Sonuç:**
```
1. Backup (weight 1)    ← Random
2. Premium (weight 10)
3. Standard (weight 5)
```

**Tavsiye:** Shuffle OFF kullan → Weight sıralaması etkili olsun

---

## Dashboard UX

### Host List Table (İsteğe Bağlı İyileştirme):

Weight kolonunu ekleyebilirsin:

```tsx
// dashboard/src/modules/hosts/tables/inbound-hosts/columns.tsx
{
    accessorKey: "weight",
    header: ({ column }) => <DataTableColumnHeader title={i18n.t('weight')} column={column} />,
    cell: ({ row }) => {
        const weight = row.getValue("weight") as number;
        return <span className="font-medium">{weight}</span>;
    },
}
```

**Görsel:**
```
┌───────────────────────────────────────────────────┐
│ Name              │ Address        │ Weight │ ... │
├───────────────────────────────────────────────────┤
│ Premium Server    │ de1.example    │ 10     │     │
│ Standard Server   │ fi1.example    │ 5      │     │
│ Backup Server     │ us1.example    │ 1      │     │
└───────────────────────────────────────────────────┘
```

Admin bir bakışta priority'leri görebilir.

---

## Migration Guide

### Mevcut Kullanıcılar İçin:

**Sorun yok!** Otomatik olarak çalışır:

1. ✅ Default weight: 1 (database schema'da `server_default="1"`)
2. ✅ Mevcut host'lar weight=1 ile devam eder
3. ✅ Yeni host'lara weight atayarak öncelik verebilirsin

**Adımlar:**

1. **Code güncelle** (bu commit)
2. **Restart panel** (`systemctl restart marzneshin`)
3. **Host'lara weight ata:**
   ```
   Panel → Hosts → Edit → Weight: 10 (Premium)
   ```
4. **Subscription test et:**
   ```bash
   curl "https://panel.com/sub/testuser/TOKEN"
   ```

---

## Performance

### Database Query:

**Öncesi:**
```sql
SELECT * FROM hosts WHERE ...;  -- Sırasız
```

**Sonrası:**
```sql
SELECT * FROM hosts WHERE ... ORDER BY weight DESC;  -- Sıralı
```

**Impact:**
- ✅ Minimal overhead (weight INDEX eklenebilir)
- ✅ User başına 1 kez çalışır (subscription generation'da)
- ✅ Caching yapılabilir (gelecekte)

### Index Önerisi (opsiyonel):

```sql
CREATE INDEX idx_hosts_weight ON hosts(weight DESC);
```

Ama genellikle host sayısı az olduğu için gerekli değil (<100 hosts/user).

---

## Örnek Kullanım Durumları

### 1. Coğrafi Önceliklendirme

```
DE1 (Germany): Weight 10  ← Europe users
FI1 (Finland): Weight 8
US1 (USA):     Weight 5
JP1 (Japan):   Weight 3   ← Uzak, yavaş
```

European users get best latency by default!

### 2. Bandwidth Önceliklendirme

```
10Gbps Server: Weight 10  ← Premium bandwidth
1Gbps Server:  Weight 5
100Mbps:       Weight 1   ← Backup only
```

### 3. Protocol Önceliklendirme

```
Reality (2087):  Weight 10  ← En güvenli
Hysteria2 (443): Weight 8   ← Hızlı
VLESS (443):     Weight 5   ← Standard
```

### 4. Load Balancing

**Multiple premium servers:**
```
Premium-DE1: Weight 10
Premium-DE2: Weight 10  ← Eşit dağılım
Premium-FI1: Weight 10
Standard-US: Weight 1   ← Backup
```

---

## Kod Akışı

```
┌─────────────────────────────────────────────────────┐
│ User Subscription Request                           │
│ GET /sub/username/token                             │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ app/utils/share.py                                  │
│ generate_subscription()                             │
│   ↓                                                 │
│ generate_user_configs()                             │
│   ↓                                                 │
│ get_hosts_for_user(db, user_id)                     │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ app/db/crud.py                                      │
│ get_hosts_for_user()                                │
│                                                     │
│ query = session.query(InboundHost)                  │
│         .filter(...)                                │
│         .order_by(InboundHost.weight.desc())  ← YENİ│
│         .all()                                      │
│                                                     │
│ Returns: [Host(weight=10), Host(5), Host(1)]       │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ for host in hosts:                                  │
│     config = create_config(host, ...)               │
│     configs.append(config)                          │
│                                                     │
│ subscription_handler.add_proxies(configs)           │
│ return subscription_handler.render(sort=True)       │
└─────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ User receives subscription (weight-sorted)          │
│                                                     │
│ vless://...@premium.com:443#Premium    ← Weight 10 │
│ vless://...@standard.com:443#Standard  ← Weight 5  │
│ vless://...@backup.com:443#Backup      ← Weight 1  │
└─────────────────────────────────────────────────────┘
```

---

## Özet

| Özellik | Durum |
|---------|-------|
| **Weight Sıralaması** | ✅ Implemented |
| **Yüksek weight → Önce** | ✅ DESC order |
| **Backward Compatible** | ✅ Default weight=1 |
| **Performance Impact** | ✅ Minimal |
| **UX Tooltip** | ✅ Weight field'da mevcut |
| **Dashboard Display** | ⏳ Optional (table column) |

**Sonuç:** Subscription link'lerinde host'lar artık **weight'e göre sıralanıyor**! 🎯

Users otomatik olarak **en yüksek weight'e sahip server**'ı kullanır → Premium experience! 🚀
