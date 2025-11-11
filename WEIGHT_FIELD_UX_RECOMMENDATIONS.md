# Weight Field UX İyileştirme Önerileri

## Mevcut Durum

Weight field'ı zaten var ve iyi bir konumda:
- **Konum**: Host Create/Edit Dialog → Address ve Port ile aynı satırda
- **Görünürlük**: CommonFields içinde, tüm protokollerde gösteriliyor
- **Default değer**: 1
- **Translation**: "Weight" (en.json)

## Sorun

Weight field'ı mevcut ama kullanıcılar:
- ❌ Ne işe yaradığını bilmiyor
- ❌ Subscription sıralamasını nasıl etkilediğini anlamıyor
- ❌ Host listesinde weight değerini göremiyorlar

---

## Önerilen İyileştirmeler

### ✅ 1. Tooltip/Açıklama Ekle (KOLAY - ÖNERİLEN)

**Neden:**
- Kullanıcılar weight'in subscription sıralaması için olduğunu anlamalı
- Hangi değerlerin geçerli olduğunu bilmeli (0-100? 1-1000?)
- Örnek kullanım durumları görmeli

**Implementasyon:**

`dashboard/src/modules/hosts/dialogs/mutation/fields/weight.tsx`:

```tsx
import {
    FormControl,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
    FormDescription,
    Input,
    HoverCard,
    HoverCardTrigger,
    HoverCardContent,
} from "@marzneshin/common/components";
import { useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { InfoCircledIcon } from "@radix-ui/react-icons";

export const WeightField = () => {
    const { t } = useTranslation();
    const form = useFormContext();
    return (
        <FormField
            control={form.control}
            name="weight"
            render={({ field }) => (
                <FormItem className="w-1/3">
                    <FormLabel className="flex items-center gap-1">
                        {t('weight')}
                        <HoverCard>
                            <HoverCardTrigger asChild>
                                <InfoCircledIcon className="h-3 w-3 text-muted-foreground cursor-help" />
                            </HoverCardTrigger>
                            <HoverCardContent className="w-80">
                                <div className="space-y-2">
                                    <h4 className="text-sm font-semibold">
                                        {t('page.hosts.weight.tooltip.title')}
                                    </h4>
                                    <p className="text-xs text-muted-foreground">
                                        {t('page.hosts.weight.tooltip.description')}
                                    </p>
                                    <div className="text-xs">
                                        <strong>{t('page.hosts.weight.tooltip.examples')}:</strong>
                                        <ul className="list-disc list-inside mt-1 space-y-1">
                                            <li>Weight 10 → {t('page.hosts.weight.tooltip.high-priority')}</li>
                                            <li>Weight 5 → {t('page.hosts.weight.tooltip.medium-priority')}</li>
                                            <li>Weight 1 → {t('page.hosts.weight.tooltip.low-priority')}</li>
                                        </ul>
                                    </div>
                                </div>
                            </HoverCardContent>
                        </HoverCard>
                    </FormLabel>
                    <FormControl>
                        <Input
                            type="number"
                            min={1}
                            max={100}
                            placeholder="1"
                            {...field}
                        />
                    </FormControl>
                    <FormDescription className="text-xs">
                        {t('page.hosts.weight.description')}
                    </FormDescription>
                    <FormMessage />
                </FormItem>
            )}
        />
    );
};
```

**Translation Eklemeleri:**

`dashboard/public/locales/en.json`:

```json
{
  "weight": "Weight",
  "page": {
    "hosts": {
      "weight": {
        "description": "Higher weight = higher priority in subscriptions",
        "tooltip": {
          "title": "Subscription Priority",
          "description": "Controls the order of hosts in subscription links. Higher weight values appear first. Useful for prioritizing faster or more reliable servers.",
          "examples": "Examples",
          "high-priority": "First in list (premium servers)",
          "medium-priority": "Middle of list (standard servers)",
          "low-priority": "Last in list (backup servers)"
        }
      }
    }
  }
}
```

**Görsel:**
```
┌─────────────────────────────────────────┐
│ Address                                 │
│ ┌─────────────────────────────────────┐ │
│ │ example.com                         │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘

┌──────────────┐  ┌──────────────┐
│ Port         │  │ Weight  ⓘ    │  ← Hover for tooltip
│ ┌──────────┐ │  │ ┌──────────┐ │
│ │ 443      │ │  │ │ 10       │ │
│ └──────────┘ │  │ └──────────┘ │
│              │  │ Higher = First│  ← Description
└──────────────┘  └──────────────┘
```

---

### ✅ 2. Host Table'da Weight Kolonu Göster (KOLAY)

**Neden:**
- Kullanıcılar mevcut host'ların weight değerlerini görebilmeli
- Subscription sıralamasını görmek için her host'u edit etmek zorunda kalmamalı

**Implementasyon:**

`dashboard/src/modules/hosts/tables/inbound-hosts/columns.tsx`:

```tsx
export const columns = (actions: ColumnActions<HostType>): ColumnDef<HostType>[] => ([
    {
        accessorKey: "remark",
        header: ({ column }) => <DataTableColumnHeader title={i18n.t('name')} column={column} />,
    },
    {
        accessorKey: "address",
        header: ({ column }) => <DataTableColumnHeader title={i18n.t('address')} column={column} />,
    },
    {
        accessorKey: "port",
        header: ({ column }) => <DataTableColumnHeader title={i18n.t('port')} column={column} />,
    },
    // ← YENİ: Weight kolonu ekle
    {
        accessorKey: "weight",
        header: ({ column }) => <DataTableColumnHeader title={i18n.t('weight')} column={column} />,
        cell: ({ row }) => {
            const weight = row.getValue("weight") as number;
            return (
                <div className="flex items-center gap-1">
                    <span className="font-medium">{weight}</span>
                    {weight >= 10 && (
                        <span className="text-xs text-green-500">●</span> // High priority indicator
                    )}
                </div>
            );
        },
    },
    {
        id: "actions",
        cell: ({ row }) => {
            return (
                <NoPropogationButton row={row} actions={actions}>
                    <DataTableActionsCell {...actions} row={row} />
                </NoPropogationButton>
            );
        },
    }
]);
```

**Görsel:**

```
┌────────────────────────────────────────────────────────────┐
│ Name            │ Address      │ Port │ Weight │ Actions  │
├────────────────────────────────────────────────────────────┤
│ Premium Server  │ de1.example  │ 443  │ 10 ●   │ [Edit]   │  ← High priority
│ Standard Server │ de2.example  │ 443  │ 5      │ [Edit]   │
│ Backup Server   │ fi1.example  │ 443  │ 1      │ [Edit]   │
└────────────────────────────────────────────────────────────┘
```

---

### ✅ 3. Visual Priority Indicator (ORTA - İYİLEŞTİRME)

**Neden:**
- Weight değerlerini renklerle/ikonlarla göstermek daha anlaşılır
- Kullanıcılar bir bakışta öncelikleri görebilir

**Implementasyon:**

Weight badge component:

```tsx
// dashboard/src/modules/hosts/components/weight-badge.tsx
import { cn } from "@marzneshin/common/utils";
import { Badge } from "@marzneshin/common/components";

interface WeightBadgeProps {
    weight: number;
}

export const WeightBadge = ({ weight }: WeightBadgeProps) => {
    const getPriorityLevel = (w: number) => {
        if (w >= 10) return { label: "High", variant: "success" };
        if (w >= 5) return { label: "Medium", variant: "warning" };
        return { label: "Low", variant: "secondary" };
    };

    const priority = getPriorityLevel(weight);

    return (
        <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{weight}</span>
            <Badge variant={priority.variant as any} className="text-xs">
                {priority.label}
            </Badge>
        </div>
    );
};
```

Table'da kullan:

```tsx
{
    accessorKey: "weight",
    header: ({ column }) => <DataTableColumnHeader title={i18n.t('weight')} column={column} />,
    cell: ({ row }) => {
        const weight = row.getValue("weight") as number;
        return <WeightBadge weight={weight} />;
    },
}
```

**Görsel:**

```
┌────────────────────────────────────────────────────────────┐
│ Name            │ Address      │ Port │ Weight      │ ...  │
├────────────────────────────────────────────────────────────┤
│ Premium Server  │ de1.example  │ 443  │ 10 [High]   │      │  ← Green badge
│ Standard Server │ de2.example  │ 443  │ 5  [Medium] │      │  ← Yellow badge
│ Backup Server   │ fi1.example  │ 443  │ 1  [Low]    │      │  ← Gray badge
└────────────────────────────────────────────────────────────┘
```

---

### 🚀 4. Drag-and-Drop Sıralama (İLERİ SEVİYE - GELECEKTEKİ İYİLEŞTİRME)

**Neden:**
- Weight değerlerini manuel girmek yerine sürükle-bırak daha kolay
- Visual olarak sıralamayı görmek daha sezgisel

**Implementasyon:**

`@dnd-kit/core` kullanarak:

```tsx
import { DndContext, closestCenter } from "@dnd-kit/core";
import { arrayMove, SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";

// Host listesini sürükle-bırak ile sırala
// Weight değerleri otomatik atanır (en üstte en yüksek)
```

**Görsel:**

```
┌────────────────────────────────────────────────────────────┐
│ ☰ Premium Server    de1.example   443   10    [Edit]      │  ← Draggable
│ ☰ Standard Server   de2.example   443   5     [Edit]      │
│ ☰ Backup Server     fi1.example   443   1     [Edit]      │
└────────────────────────────────────────────────────────────┘

Sürükle → Weight otomatik güncellenir
```

**Not:** Bu implementasyon daha karmaşık, şimdilik gerekli değil.

---

## Önerilen Uygulama Sırası

### Hemen Yapılabilecekler:

1. ✅ **Tooltip ekle** (30 dakika)
   - Weight field'ına InfoIcon + HoverCard ekle
   - Translation'ları ekle
   - Min/max değerler belirle

2. ✅ **Table'da göster** (15 dakika)
   - columns.tsx'e weight kolonu ekle
   - Basit display (sayı olarak)

### Sonraki Adımlar:

3. 🔧 **Visual indicator** (1 saat)
   - WeightBadge component yaz
   - Renk/badge sistemi ekle
   - Table'da kullan

4. 🚀 **Drag-drop** (4+ saat)
   - dnd-kit entegrasyonu
   - Otomatik weight assignment
   - Backend API güncellemesi

---

## Tavsiye Edilen Final UX

### Host Create/Edit Dialog:

```
┌─────────────────────────────────────────────────────────┐
│ Create Host                                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Remark                                                  │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Premium DE Server                                   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ Address                                                 │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ de1.example.com                                     │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌──────────────────────┐  ┌──────────────────────────┐ │
│ │ Port                 │  │ Weight  ⓘ                │ │
│ │ ┌──────────────────┐ │  │ ┌──────────────────────┐ │ │
│ │ │ 443              │ │  │ │ 10                   │ │ │
│ │ └──────────────────┘ │  │ └──────────────────────┘ │ │
│ │                      │  │ Higher = First in list   │ │
│ └──────────────────────┘  └──────────────────────────┘ │
│                                                         │
│ [ Accordion: Network Settings ]                         │
│ [ Accordion: Security Settings ]                        │
│                                                         │
│                             ┌─────────────────────────┐ │
│                             │ Submit                  │ │
│                             └─────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Host List Table:

```
┌────────────────────────────────────────────────────────────────┐
│ Hosts for VLESS Reality (2087)                                │
├────────────────────────────────────────────────────────────────┤
│ Name               │ Address        │ Port │ Priority │ ...   │
├────────────────────────────────────────────────────────────────┤
│ Premium DE Server  │ de1.example    │ 443  │ 10 [High]│ Edit  │
│ Standard FI Server │ fi1.example    │ 443  │ 5 [Med]  │ Edit  │
│ Backup US Server   │ us1.example    │ 443  │ 1 [Low]  │ Edit  │
└────────────────────────────────────────────────────────────────┘

💡 Tip: Higher weight values appear first in subscription links
```

---

## Kod Değişiklikleri Özeti

### Dosyalar:

1. ✏️ `dashboard/src/modules/hosts/dialogs/mutation/fields/weight.tsx`
   - InfoIcon + HoverCard ekle
   - FormDescription ekle
   - Min/max değerler

2. ✏️ `dashboard/src/modules/hosts/tables/inbound-hosts/columns.tsx`
   - Weight kolonu ekle
   - Badge/indicator ekle (opsiyonel)

3. ✏️ `dashboard/public/locales/en.json`
   - Weight tooltip translations
   - Description translations

4. 🆕 `dashboard/src/modules/hosts/components/weight-badge.tsx` (opsiyonel)
   - Priority badge component

---

## Test Senaryosu

### Kullanıcı Akışı:

1. **Host Oluştur:**
   - Panel → Hosts → Add Host
   - Weight field görünür (Address/Port ile aynı satırda)
   - ⓘ icon'a hover → Tooltip açıklama gösterir
   - Weight 10 gir → "Higher = First in list" description görünür

2. **Host Listesi:**
   - Panel → Hosts
   - Table'da Weight kolonu görünür
   - Weight değerleri badge ile gösterilir (High/Medium/Low)
   - Sorting: Weight'e göre sıralama yapılabilir

3. **Subscription Link:**
   - User subscription alır
   - Weight 10 olan host en üstte
   - Weight 5 olan host ortada
   - Weight 1 olan host en altta

---

## Özet

**Mevcut Durum:** ✅ Weight field var, konumu iyi (Address/Port ile aynı satırda)

**En Önemli İyileştirme:** 🌟 Tooltip/Açıklama ekle (kullanıcılar ne işe yaradığını anlamalı)

**İkincil İyileştirme:** ✅ Table'da göster (görünürlük artırır)

**Gelecek İyileştirme:** 🚀 Visual indicator ve drag-drop (kullanıcı deneyimini geliştirir)

**Tavsiye:** Tooltip eklemeyle başla - basit ama etkili! 🎯
