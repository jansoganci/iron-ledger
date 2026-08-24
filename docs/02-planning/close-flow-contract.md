# Close akışı ürün sözleşmesi

*Kod yok. Araştırma ([close-process-by-sector.md](../06-reports/close-process-by-sector.md)) ile ilk kod dilimi arasındaki köprü.*  
*24 Ağustos 2026.*

Ürünü pivot etmiyoruz. Direkt “checklist ekranı / closed status / yeni ajan” yazmıyoruz. Önce bu sözleşmeyi kilitle, sonra Sentinel’i kâğıt üzerinde yürüt, en son en küçük dilimi kodla.

---

## 1. Kilit kararlar

| Karar | Değer |
|-------|--------|
| Kullanıcı | Saha hizmeti ofis müdürü / fractional controller. Owner değil. Jargon bilmeyen SMB sahibi değil. |
| İş | 4–5 günde kapanış paketini müdüre iletmek. “AI rapor üretmek” değil. |
| İlk sektör | Kurulum + izleme (Sentinel tipi). İkinci: profesyonel hizmet. |
| Kaynak gerçeği | GL. Departman dosyası kanıt. |
| Ajan ne yapmaz | ERP’ye JE post, banka satır eşleştirme, ASC 606, stok değerleme, WIP. |
| Close bitti sayılır | Dönem kilitlendi + paket gitti. `complete` + e-posta yetmez. |
| Dil | Controller dili: GL, JE, cutoff, tie-out. “Jargon yok” kuralı bu kullanıcı için yanlış. |

Bu tablo tartışmalıysa kod yazma. Tartışma buradadır.

---

## 2. Bugünkü ürün ne yapıyor?

Gerçek sıra (kullanıcının gördüğü):

1. Login / şirket onboarding
2. `/upload` — dosya bırak, dönem seç, Analyze
3. Discovery onayı (gerekirse)
4. Mapping onayı (gerekirse)
5. Parse preview → Confirm
6. Comparison + Interpreter (arka plan)
7. `/report/:period` — anlatı, anomali kartları, recon kartları, mail, Excel

Run makinesi: `pending → parsing → discovering → mapping → awaiting_confirmation → comparing → generating → complete`. Terminal: `upload_failed`, `parsing_failed`, `guardrail_failed`. **`closed` yok.**

Rapor sayfası sırası (kod: `frontend/src/pages/ReportPage.tsx`): özet anlatı → anomaliler (geçen aya varyans) → recon bulguları (dosyalar arası). Recon, severity’ye göre yığılmış **bulgu listesi**; “5 kontrolden 3 temiz” değil.

Bu, close’un **Gün 4’ü önde, Gün 2’yi bulgu yığını olarak** gösteren bir asistan. Ofis müdürü “nereden başlarım / hangi dosya eksik / banka tamam mı / dönem kilitli mi” sorularına cevap almaz.

---

## 3. Hedef sıra (aynı motor, farklı iskelet)

Kullanıcının yaşaması gereken close, araştırma dokümanındaki günlerle birebir:

| Close günü | Üründe olması gereken | Bugün | İlk dilimde? |
|------------|------------------------|-------|----------------|
| 0 Kesim | Bu dönem için beklenen dosya listesi; hangisi geldi | Yok; rastgele N dosya | Hayır — ikinci dilim |
| 1 Nakit | “Banka/kart dışarıda tamam, teyit ettim” kutusu. Satır matching yok | Yok | Evet — tek checkbox + paket cümlesi |
| 2 Tie-out | 5 kontrol, her biri geçti/kaldı + istisna | Recon kart yığını | Evet — **asıl dilim** |
| 3 Açık madde | Önceki aydan dönmeyen timing / hâlâ açık missing JE | Yok | Hayır — tie-out durunca |
| 4 Flux | Tie-out’tan sonra, SMB eşiği | Var, erken ve $50k eşiği | Kısmen — raporda alta al, eşiği sonra |
| 5 Kilit | Sign-off → `closed`, Excel checklist + open items | `complete` + mail | Hayır — üçüncü dilim |

Bilinçli kesik: banka matching yok, ama “yapılmadı” da gizlenmez.

---

## 4. Sentinel kâğıt yürüyüşü (koddan önce kabul testi)

Hayali kullanıcı: Sentinel Secure ofis müdürü, 3 Nisan, Mart close, akşam owner araması.

**Getirdiği dosyalar (ürünün zaten bildiği şekil):**

- `sentinel_gl_mar_2026.xlsx` — GL
- `sentinel_payroll_mar_2026.xlsx`
- `sentinel_supplier_invoices_mar_2026.xlsx`
- `sentinel_contracts_mar_2026.xlsx`
- `sentinel_installation_payments_mar_2026.xlsx`

**Başarılı close, onun dilinde:**

1. “Mart için 5 kaynak dosya + GL yüklü. Banka recon’u QuickBooks’ta bitirdim, buraya teyit ettim.”
2. “5 bağlamadan 3’ü tutuyor. 2 istisna: CableMax faturası GL’de yok (`missing_je`); 3 iptal müşteri listede aktif (`stale_reference`).”
3. “Kurulumda %50 depozito timing — hata değil, Nisan’da döner.”
4. “Flux: izleme geliri düşmüş çünkü o 3 müşteri; G&A sakin. Travel yoksa saha için araç/yakıt bak.”
5. “Paketi indirdim, owner’a attım, dönemi kilitledim.”

**Başarısız close (bugünkü ürünün riski):**

- 32 recon kartı, 28’i `missing_je` — araç bozuk görünür.
- Anlatı en üstte, checklist yok.
- Banka hiç geçmez.
- “Verified” rozeti close bitmiş gibi durur; dönem kilitli değildir.

Kâğıt yürüyüş geçmeden tie-out UI’sı yazma. Demo dosyaları `Account` kolonu taşıyorsa yürüyüş “demo yalanı”dır; gerçek sözleşme listesi müşteri+ücret taşır. İlk kod diliminden önce netleştir: **dosya-seviyesi map (dosya toplamı → GL hesabı X) bu dilimin parçası mı?** Cevap evet olmalı, yoksa Sentinel gerçek dosyayla kırılır.

---

## 5. İlk kod dilimi (henüz yazma — tanım)

Tek cümle: **Raporu close checklist’e çevir; motoru değiştirme.**

Kapsam:

- Rapor sayfası sırası: (1) tie-out özeti 5/N, (2) istisnalar sınıfla, (3) flux/anlatı, (4) banka teyit satırı.
- Recon’u “hesap kartı yığını” değil “kontrol geçti/kaldı” olarak grupla. Grup anahtarı: bordro, tedarikçi, sözleşme, kurulum, yakıt — dosya etiketinden.
- Pakette bir cümle: banka Month Proof dışında.
- Materiality: consolidator’daki fiili `$100` tabanını dokümante edilen `$100 ve %5` kuralına çek; 32 gürültülü `missing_je`’yi kes. Comparison `$50k` eşiği bu dilimde zorunlu değil.

Dışarıda (bilerek):

- `closed` state, sign-off, dönem kilidi
- Beklenen dosya manifesti / Gün 0
- Önceki aydan open-item yaşlandırma
- Banka CSV
- Yeni ajan, yeni tablo, ERP

Çıkış kriteri: Sentinel 5 dosyasıyla ofis müdürü 60 saniyede “kaç kontrol kaldı, ne yapacağım” diyebilsin. 32 kart saymasın.

---

## 6. Şimdi yapılacaklar (kod değil)

Sıra:

1. Bu sözleşmeyi oku, tablo 1’e itiraz varsa yaz. İtiraz yoksa kilitli kabul et.
2. Sentinel dosyalarını kâğıtta 5 tie-out’a map et (hangi dosya → hangi GL satırı → beklenen sınıf). Demo `docs/demo_data/` şu an boşsa önce dosyaları repo’ya koy veya yürüyüşü mevcut Sentinel şemasıyla yaz.
3. Gerçek sözleşme Excel’inin kolonlarını bir kez listele (müşteri, ücret, aktif) — AccountMapper vs dosya-seviyesi toplam kararı.
4. Ancak ondan sonra dilim 1’i kodla.

Yapılmayacak: yeni sektör, quarterly’ye dokunmak, prompt’u “daha CFO” yapmak, banka recon motoru.
