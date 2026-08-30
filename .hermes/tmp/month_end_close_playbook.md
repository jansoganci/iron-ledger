# Görev: Ay Sonu Kapanış Operasyonel Playbook'u

## Rol
Sen kıdemli bir finans operasyonları danışmanısın (finance operations consultant). 20+ yıllık ay sonu kapanış (month-end close) deneyimin var; hem ABD GAAP hem Türkiye (VUK/KGK) mevzuatını biliyorsun.

## Görev
Orta ölçekli bir şirkette (50-200 çalışan, 2-5 kişilik finans ekibi) çalışan bir finans departmanı çalışanının gözünden, GERÇEK bir ay sonu kapanış sürecini gün gün, saat saat anlatan kapsamlı bir operasyonel playbook yaz.

## İstenen İçerik (bölüm bölüm)

### Bölüm 1: Kapanış takvimi (Close Calendar) — gün gün
- Ay sonundan itibaren Day 1'den Day 15'e kadar HANGİ GÜN HANGİ İŞ yapılır (soft close / hard close ayrımıyla)
- Her gün için: o günün görev listesi, kim yapar, hangi girdi lazım (hangi sistemden), hangi çıktı üretilir

### Bölüm 2: Görev envanteri — her görev için detay
Her görev için şu şablonu kullan:
- Görev adı
- Açıklama (ne yapılır, adımlar)
- Girdi kaynağı (ERP, banka ekstresi, e-fatura, bordro sistemi vs.)
- Ortalama süre (saat) — gerçekçi ol, küçük/orta şirket varsayımıyla
- Hangi rol yapar (yardımcı muhasebeci, genel muhasebe, mali müşavir/SMMM, finans müdürü)
- Sıklık (aylık / çeyreklik / yıllık)
- Yaygın hata / ağrı noktası (bu bölüm önemli — ürün fırsatı)

Kapsanacak görevler (liste sınırlayıcı değil, bunlardan az olmamalı):
1. Banka mutabakatı (tüm hesaplar)
2. Kasa sayımı ve mutabakatı
3. Cari hesap mutabakatı (müşteri + tedarikçi) — AR aging / AP aging
4. Tahsilat ve ödeme eşleştirme
5. Bordro tahakkuku ve mutabakatı
6. Amortisman kaydı (duran varlık)
7. Ön ödemeler / peşin ödenmiş giderler (prepaids) itfası
8. Gider tahakkukları (accruals) — dönemsellik
9. Kur farkı değerlemesi (FX revaluation) — dövizli hesaplar
10. Reeskont işlemleri (alacak/borç senetleri)
11. Stok sayımı / stok değerleme (eğer stok varsa)
12. KDV kontrolü ve beyanname hazırlığı (TR)
13. Muhtasar/Ba-Bs formları (TR)
14. Geçici vergi dönemi kontrolü (TR, çeyreklik)
15. Enflasyon düzeltmesi (TR, 2024+ zorunlu)
16. Gelir tahakkuku / revenue recognition kontrolü
17. Kapanış kayıtları (closing entries) — gelir/gider hesaplarının kapatılması
18. Mizan kontrolü (trial balance) — borç/alacak eşitliği
19. Yönetim raporları (P&L, bilanço, nakit akışı, KPI'lar)
20. Banka/hesap mutabakatı belgelerinin arşivlenmesi

### Bölüm 3: Süre ve ekip tablosu
- Toplam adam-saat: kapanış başına kaç saat harcanır (ekip büyüklüğüne göre: 2 kişi, 3-4 kişi, 5+ kişi)
- Hangi görev en çok zaman alıyor (toplam sürenin %'si olarak)
- Sıkışık günler (Day 1-3'te ne kadar yoğunluk)

### Bölüm 4: Otomasyon/agentic fırsat haritası (CRITICAL)
Her görevi şu sınıflara ayır:
- A) Tamamen otomatikleştirilebilir (deterministik, kural bazlı) — örn. mizan eşitliği kontrolü
- B) LLM/agent desteğiyle yarı otomatik (belge okuma, sınıflandırma, mutabakat önerisi) — ama insan onayı şart
- C) İnsan kararı şart (muhasebe politikası, yönetim onayı)
Her görev için: "agent bugün ne yapabilir, insan ne yapmalı" net olsun.

### Bölüm 5: Türkiye özel notları (kısa)
- TR'de kapanışın ABD'den farkları (KDV, enflasyon düzeltmesi, e-fatura/e-arşiv akışı, SMMM/YMM ilişkisi, yasal defter kapanış tasdiki)
- Türk muhasebeci (SMMM) için kapanışın gerçekte nasıl işlediği — müvekkil verisi toplama, excel mutabakat, beyanname süreleri (KDV ertesi ayın 26'sına kadar vs.)

### Bölüm 6: IronLedger ürünü için çıkarımlar (KISA)
IronLedger bugün: dosya yükle → GL + destekleyici dosyaları birleştir → tutarsızlık sınıflandır → LLM ile rapor yaz. Bu playbook'taki görevlerin hangileri IronLedger'ın şu anki yeteneğiyle örtüşüyor, hangileri eksik? 5-10 madde, madde madde.

## Çıktı formatı
- Markdown, TÜRKÇE, terminalde okunabilir
- Tablolar kullan (görev envanteri tablosu, takvim tablosu, saat dağılımı tablosu)
- Uzunluk: 400-700 satır arası — kapsamlı ama şişkin değil
- Dosyayı şu yola yaz: docs/MONTH_END_CLOSE_PLAYBOOK_TR.md (çalışma dizini iron-ledger repo kökü)

## Kalite kuralları
- Rakamlar gerçekçi olsun: orta ölçekli TR şirketinde banka mutabakatı 2-4 saat, mizan kontrolü 1-2 saat gibi somut aralıklar ver
- "ortalama" verirken küçük şirket (2 kişi) ve orta şirket (4-5 kişi) farkını belirt
- Süslü pazarlama dili yok — operasyonel, pratik, bir finans çalışanının gerçekten yaptığı işi anlat
