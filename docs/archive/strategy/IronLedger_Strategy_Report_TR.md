# IronLedger: Ürün, Pazar ve Savunulabilirlik Raporu

**Tarih:** 17 Temmuz 2026  
**Pazar:** ABD, SMB ve alt mid-market finans ekipleri

## Yönetici kararı

IronLedger için gerçek bir problem ve ödeme potansiyeli var; ancak mevcut yönüyle ürün aynı anda **financial close, konsolidasyon, FP&A ve görsel modelleme** olmaya çalışırsa güçlü rakiplerin arasına sıkışır. En doğru başlangıç kategorisi **file-first close investigation and exception resolution**: finans ekibinin GL, banka, payroll, invoice, sözleşme ve diğer destek dosyalarını karşılaştırıp kapanışı engelleyen farkları kanıtlarıyla açıklayan, düzeltme öneren ve her ay aynı kuralları yeniden çalıştıran bir kontrol katmanı.

En önemli ürün kararı şudur: **GL otoriter kayıt olarak kalmalı.** Diğer dosyalar ayrı bir alternatif P&L üretmek için değil, GL bakiyelerini ve hareketlerini doğrulamak, eksik veya yanlış kayıtları bulmak ve taslak düzeltme/journal entry hazırlamak için kullanılmalı.

İlk hedef müşteri “2–15 kişilik her finans ekibi” değildir. Daha keskin ICP:

- ABD'de yaklaşık **$10M–$100M gelir/ARR** üreten büyüyen şirket,
- **3–10 kişilik accounting/finance ekibi**,
- QuickBooks Advanced, Sage Intacct veya erken dönem NetSuite kullanımı,
- en az **4 finansal veri kaynağı**,
- çoklu banka, ödeme kanalı, entity veya lokasyon,
- kapanış süresi **6+ iş günü**,
- her ay en az **10–20 saat veri toplama, reconciliation ve fark araştırması**.

Öncelikli dikeyler: e-commerce/marketplace, çok lokasyonlu hizmet şirketleri ve nispeten standart muhasebe politikalarına sahip büyüyen SaaS şirketleri. Çok karmaşık revenue recognition, kamu şirketi/SOX veya büyük global konsolidasyon ilk ürün kapsamı olmamalı.

**$499/ay mümkündür ama tek fiyat olarak değil, giriş paketi olarak.** Ürün ayda yalnızca altı saat junior çalışan zamanı kazandırıyorsa fiyat savunması zayıftır. En az 8–15 saat ekip zamanı, bir kapanış günü veya belirgin audit/review riski tasarrufu göstermelidir.

## Araştırma sınırı

Bu çalışma alanında veya konuşmaya eklenmiş erişilebilir IronLedger proje dosyası bulunmadı. Dolayısıyla aşağıdaki “mevcut durum” özeti konuşmada paylaşılan bilgilerden çıkarılmıştır; kod üzerinden doğrulanmış teknik audit değildir.

## 1. Mevcut ürün durumu

### Konuşma bağlamına göre çalışan yapı

- Excel, CSV, PDF, QuickBooks tarzı GL ve NetSuite XML-as-XLS gibi dosyaları okuma.
- PII temizleme ve Pandera doğrulaması.
- pandas ile deterministik hesaplama.
- Birden fazla kaynağı finansal çıktıda birleştirme.
- Sayı bazında dosya/satır provenance bilgisi.
- Missing journal, stale reference, misclassification ve timing/cutoff gibi discrepancy sınıfları.
- LLM'nin hesap yapmadığı, yalnızca açıklama yazdığı narrative guardrail.
- Dashboard ve üç sayfalı Excel çıktısı.

### Tasarlanmış fakat uygulanmadığı belirtilen yapı

- Haiku tabanlı AccountMapper.
- MappingReview arayüzü.
- RLS kapsamlı `account_mappings` tablosu.
- Uygulamadan önce Supabase migration numarası kontrolü.

### Henüz doğrulanmamış veya kapsamı net olmayan kritik kabiliyetler

- Dönemler arasında mapping/policy öğrenme ve effective-date yönetimi.
- Balance-sheet account reconciliation.
- One-to-many, many-to-one ve many-to-many transaction matching.
- Materiality, tolerance, timing window ve FX kuralları.
- Reviewer/approver ayrımı, sign-off ve close lock.
- Taslak journal entry, ERP write-back ve reversal yönetimi.
- Audit log, SOC 1/SOC 2 hazırlığı, veri saklama ve tenant isolation.
- Çoklu entity, intercompany ve currency.
- Bütçe, forecast, scenario versioning ve actual-vs-plan veri modeli.

## 2. Problem gerçekten var mı?

### Kanıt

Ledge'in 100 finans profesyoneliyle yaptığı 2025 çalışmada ekiplerin yarısı kapanışı beş iş gününden uzun sürede tamamlıyor; en fazla zaman alan iş reconciliation. Katılımcıların %94'ü close sırasında Excel kullanıyor, %50'si Excel'i yavaşlığın nedeni olarak gösteriyor ve ekiplerin çoğu close işlerinin %40'ından azını otomatikleştirmiş durumda. Cash reconciliation için bildirilen süre ayda 20–50 saat; çoğu ekip bunun için 3–5 sistem kullanıyor. Araştırmanın örneklemi 51–200 çalışandan başlayan şirketlerden geldiği için mikro-SMB kanıtı olarak kullanılmamalı. [Ledge close benchmark](https://www.ledge.co/content/month-end-close-benchmarks-for-2025)

2026 LiveFlow araştırmasını aktaran CFO Dive'a göre katılımcıların yaklaşık %80'i diğer sistem veya departmanlardan veri beklemeyi, yarısından fazlası platformlar arası reconciliation'ı kapanış gecikmesinin nedeni olarak gösterdi. Katılımcıların yalnızca %16'sı üç günden kısa sürede kapanış yapıyordu; AI kullanımı yazı ve analizde yaygınken operasyonel reconciliation ve categorization hâlâ büyük ölçüde manueldi. [CFO Dive / LiveFlow](https://www.cfodive.com/news/cfo-push-faster-month-end-close-stalled-data-bottlenecks-ai/819283/)

Güncel iş ilanları da problemi doğrudan doğruluyor. Örneğin bir Accounting Manager ilanı; Ramp, Stripe, banka, payroll, intercompany ve vendor verilerini uzlaştırmayı, journal entry hazırlamayı, beş günlük close hedefini, audit trail'i ve sürekli otomasyonu aynı rolde topluyor. [CSC Generation Accounting Manager ilanı](https://jobs.lever.co/cscgeneration-2/1728cda8-3d06-41e4-8b9b-aced8cc53d69)

### Çıkarım

Problem “rapor yazmak” değil; kapanış öncesindeki **veri toplama, substantiation, exception investigation, correction ve approval** zinciridir. Bu, IronLedger'ın ilk içgörüsünü doğruluyor.

### Karşı kanıt

- Küçük QuickBooks müşterileri için Intuit artık PDF banka ekstrelerini hesaplarla karşılaştırıp fark ve düzeltme öneren Accounting AI sunuyor. [QuickBooks Accounting AI](https://quickbooks.intuit.com/accounting-agent/)
- Numeric close checklist paketini kullanıcı başına aylık $30'dan başlatıyor. Dolayısıyla yalnızca checklist, görünürlük ve narrative için $499 zor savunulur. [Numeric pricing](https://www.numeric.io/pricing)
- Bazı küçük ekipler için altı saatlik aylık problem, yeni bir finans sistemini satın alma ve kurma maliyetinden daha küçüktür.

Sonuç: ihtiyaç var, fakat **kompleksite eşiğinin üstündeki şirketlerde** bütçeli ve acil hale geliyor.

## 3. En doğru müşteri ve satın alma dinamiği

| Unsur | Öneri |
|---|---|
| Ekonomik alıcı | Controller, VP Finance veya Head of Accounting |
| Günlük kullanıcı | Senior Accountant, Accounting Manager, Finance Operations |
| Şampiyon | Her ay dosyaları toplayıp reconciliation yapan kişi |
| Şirket profili | $10M–$100M gelir/ARR, 3–10 kişilik finans ekibi |
| Sistem profili | QBO Advanced/Intacct/erken NetSuite + banka + payroll + billing/PSP + Excel |
| Acı sinyali | 6+ gün close, 10+ saat preparation, tekrar eden reclass/accrual, audit desteği dağınık |
| Satın alma tetikleyicisi | Yeni entity, yeni ödeme kanalı, ERP geçişi, audit/financing hazırlığı, muhasebe çalışanı ayrılığı |
| Uygun olmayan müşteri | Tek entity, düşük işlem hacmi, dış muhasebeciyle basit cash-basis kayıt, ayda birkaç saat close işi |

“2–15 finans çalışanı” yardımcı bir filtre olabilir; esas ICP tanımı **kaynak ve close kompleksitesi** üzerinden yapılmalıdır.

İkinci test segmenti olarak 10–50 müşteriyi yöneten fractional CFO/accounting advisory firmaları denenebilir. Bu firmalar mapping ve close otomasyonunu birçok müşteride tekrar kullanabildiği için $499'dan daha yüksek ROI görebilir; fakat multi-tenant yapı ve mesleki sorumluluk beklentileri farklıdır. İlk ürün aynı anda iki segmente göre tasarlanmamalı.

## 4. Ürün konumlandırması

### Önerilen kategori

**AI-assisted Close Investigation & Exception Resolution**

### Positioning cümlesi

> IronLedger helps lean accounting teams close with confidence by reconciling the messy files around their GL, explaining every material exception with source evidence, and preparing review-ready corrections—without an enterprise implementation.

### Müşterinin ürünü işe alacağı iş

> “Her ay farklı dosyaları tekrar birleştirip neden uyuşmadıklarını aramak yerine, yalnızca gerçek istisnaları incelemek ve kapanışı kanıtlarıyla onaylamak istiyorum.”

### Temel iş akışı

1. GL/trial balance ana kayıt olarak alınır.
2. Banka, payroll, AP, billing/PSP, kontrat ve diğer destek kaynakları yüklenir veya bağlanır.
3. Kaynak kolonları önce şirketin Chart of Accounts'una, sonra reporting taxonomy'ye eşlenir.
4. Deterministik matching ve reconciliation çalışır.
5. İstisnalar materiality ve olası kök nedene göre sıralanır.
6. Her istisna kaynak satırları, kullanılan kural ve confidence ile açıklanır.
7. Sistem reclass/accrual/cutoff veya reference-data düzeltmesi önerir.
8. İnsan onayıyla close package ve taslak JE üretilir.
9. Onaylanan kurallar sonraki dönemde effective-date ve version ile yeniden çalışır.

## 5. Rakip haritası

### Doğrudan rakipler

| Ürün | Ana pazar ve iş | Güçlü taraf | IronLedger için anlamı |
|---|---|---|---|
| BlackLine | Enterprise reconciliation, close, consolidation ve controls | Derin kontrol, matching, audit ve global ölçek | Üst pazarda doğrudan yarışılmamalı; kurulum ve karmaşıklık küçük ekipler için boşluk yaratıyor. [BlackLine](https://www.blackline.com/products/financial-close/account-reconciliations/) |
| FloQast | Mid-market close orchestration ve Excel tabanlı reconciliation | Kullanıcı benimsemesi, checklist, ERP bağlantısı, audit-ready süreç | “Excel kullanan küçük ekip” alanı artık boş değil; bazı küçük ekipler maliyet/ölçekten şikâyet ediyor. [G2 reviews](https://www.g2.com/products/floqast/reviews) |
| Numeric | Modern close, reconciliation, flux ve reporting | Hızlı onboarding; $30/user checklist girişi; NetSuite data/flux | $499 paketin checklist'ten çok daha fazla execution sağlaması gerekir. [Numeric](https://www.numeric.io/pricing) |
| NetClose | NetSuite içinde close yönetimi | ERP-native deneyim | NetSuite-only müşteri için güçlü; IronLedger ERP bağımsız ve file-first olmalı. [NetClose](https://www.netgain.tech/lp/netclose) |
| Ledge | Mid-market/enterprise agentic close execution | Working papers, JE, continuous reconciliation, CSV, ERP/bank bağlantısı, audit trail; bir günde onboarding iddiası | IronLedger'ın en doğrudan tehdidi. Fark yalnızca “AI açıklıyor” olamaz. [Ledge pricing/capabilities](https://www.ledge.co/pricing) |
| Maxima | Enterprise agentic record-to-report | Finance graph, 150+ entegrasyon, JE/reconciliation/flux, transaction lineage ve policy | Ürün vizyonunun büyük ölçüde zaten pazara çıktığını gösteriyor; daha küçük müşteri ve çok dar workflow gerekir. [Maxima](https://www.maxima.ai/) |
| Rillet | Büyüyen şirketler için AI-native ERP | Ledger'ın kendisini ve close'u birlikte kontrol ediyor | ERP replacement tehdidi; IronLedger mevcut ERP'nin üstünde tarafsız kontrol katmanı olmalı. [Rillet](https://www.rillet.com/) |

### FP&A ve birleşik performance-management rakipleri

| Grup | Ürünler | Ne yapıyorlar | Sonuç |
|---|---|---|---|
| Enterprise EPM | Pigment, Anaplan, Workday Adaptive, SAP Analytics Cloud | Plan, budget, forecast, scenario, consolidation ve actual-vs-plan | Full budgeting engine'e erken girmek yanlış. Pigment artık actuals, legal consolidation ve planning'i aynı modelde birleştiriyor. [Pigment](https://www.pigment.com/use-case/financial-consolidation) |
| Mid-market FP&A | Cube, Datarails, Aleph, Vena, Planful, Drivetrain | Spreadsheet bağlantısı, data consolidation, modelleme, variance ve reporting | Canvas ve planning tek başına farklılaşma sağlamaz. [Aleph](https://www.getaleph.com/) · [Cube](https://www.cubesoftware.com/) · [Datarails](https://www.datarails.com/) |
| SMB analysis | Fathom, Syft | Ucuz reporting, consolidation, forecast ve actual-vs-budget | Basit P&L ve forecast için fiyat çıtasını aşağı çeker. Fathom tek şirket için $53/aydan başlıyor. [Fathom pricing](https://www.fathomhq.com/pricing) |

### Platform tehditleri

- Microsoft 365 Copilot Finance iki Excel veri setini uzlaştırabiliyor, reconciliation rule önerebiliyor ve variance analysis'i otonom çalıştırabiliyor. [Microsoft reconciliation](https://learn.microsoft.com/en-us/copilot/finance/reconcile/reconcile-data) · [Microsoft variance](https://learn.microsoft.com/en-us/copilot/finance/variance/analyze-variances)
- ChatGPT Work finans ekipleri için reconciliation, forecast update ve decision-ready reporting'i doğrudan ürün vaadi olarak sunuyor. [ChatGPT Work for Finance](https://openai.com/business/solutions/finance/)
- Claude ay sonu close dahil hazır finans agent şablonları ve Excel/Microsoft 365 entegrasyonları sunuyor. [Anthropic finance agents](https://www.anthropic.com/news/finance-agents)
- QuickBooks reconciliation ve categorization'ı kendi ledger'ının içine gömüyor. [QuickBooks Accounting AI](https://quickbooks.intuit.com/accounting-agent/)

Bu gelişmeler nedeniyle file parsing, kolon mapping önerisi, narrative yazımı, basit two-way reconciliation ve temel variance analizi üç yıl içinde commodity olacaktır.

## 6. Savunulabilirlik

### Zayıf veya geçici avantajlar

- “Claude kullanıyoruz.”
- Excel/PDF okuyabilme.
- US-GAAP kategorisine tek seferlik mapping.
- P&L narrative yazma.
- Sankey veya güzel canvas.
- İki tabloyu birbiriyle karşılaştırma.

### Birikerek güçlenen ürün varlıkları

1. **Şirkete özgü accounting policy graph:** Hangi işlem hangi koşulda hangi hesaba gider; cutoff, accrual, capitalization ve materiality politikaları.
2. **Versioned mapping memory:** Kullanıcının düzeltmeleri, effective dates, entity farkları ve nedenleri.
3. **Evidence graph:** Her bakiye, öneri ve narrative iddiasının kaynak satırı, kuralı ve onayı.
4. **Recurring workflow state:** Kim hazırladı, kim inceledi, hangi exception ertelendi, hangi JE post edildi.
5. **Correction outcomes:** Önerilen düzeltmelerden hangilerinin kabul/red edildiği ve sonraki dönem sonucu.
6. **Vertical templates ve benchmark:** Örneğin Stripe/Ramp/Shopify/QuickBooks kullanan e-commerce şirketi için hazır close logic.
7. **ERP write-back ve controls:** Draft JE, approval, segregation of duties ve immutable audit trail.

Genel AI modeli analiz edebilir; ancak şirket politikasının zaman içindeki onaylı uygulamasını, audit kanıtını ve dönemler arası operational state'i kendiliğinden sahiplenmez. IronLedger'ın moat'i model değil, bu kontrollü sistem olmalıdır.

## 7. AccountMapper için stratejik düzeltme

Doğrudan “messy source → US-GAAP category” mapping'i tek başına yeterli değildir ve şirketin gerçek Chart of Accounts yapısını kaybettirebilir. Önerilen katman:

1. Source field/value → normalized source concept
2. Normalized concept → company GL account / dimension
3. Company GL account → reporting taxonomy / US-GAAP line
4. Reporting line → management hierarchy / KPI / future planning driver

Her mapping confidence, evidence, author, approval, effective period, entity scope ve superseded version taşımalı. Böylece close, management reporting ve gelecekteki planning aynı semantik temel üzerinde çalışabilir.

## 8. Canvas kararı

Free-form canvas şu anda ana ürün değildir. İlk sürüm **operational lineage view** olmalı:

`Kaynak → normalize edilen kayıt → mapping rule → GL account → financial statement line → exception/variance`

Kullanıcı bir node'a tıkladığında kaynak satırlarını, kuralı, confidence'ı ve etkilenen toplamı görmeli. Mapping değiştirildiğinde sistem önce impact preview göstermeli; değişiklik kaydedildiğinde versioned rule oluşmalı ve gerekiyorsa reviewer approval istemeli.

Bu yapı gelecekte üç moda dönüşebilir:

- **Actual / Close:** Kaynak ve reconciliation akışı.
- **Plan / Forecast:** Driver ve assumption akışı.
- **Actual vs Plan:** Farkın hangi hesap ve operasyonel driver'dan geldiği.

Ancak ilk 12 ayda tam budgeting engine yerine yalnızca veri modelinde `scenario`, `version`, `period`, `entity` ve `driver` alanlarının hazırlanması yeterlidir.

## 9. Fiyatlandırma

ABD BLS verisine göre accountant/auditor medyan ücreti yıllık $81,680, financial manager medyanı $161,700. Yan hak ve overhead hariç kaba saatlik karşılıklar yaklaşık $39 ve $78'dir. Bu nedenle $499, yaklaşık **12.7 accountant saati** veya **6.4 financial-manager saati** değerindedir. [BLS accountants](https://www.bls.gov/ooh/business-and-financial/accountants-and-auditors.htm) · [BLS financial managers](https://www.bls.gov/ooh/management/financial-managers.htm)

Önerilen paketleme:

| Paket | Fiyat hipotezi | Kapsam |
|---|---:|---|
| Starter | $499/ay | 1 entity, 4 source, 3 active reconciliation workflow, unlimited reviewers, Excel close package |
| Growth | $999–$1,499/ay | 3–5 entity, daha fazla workflow, ERP sync, draft JE, approvals ve recurring monitors |
| Enterprise | Teklif | SSO, custom connector, advanced controls, high volume, SLA |

Seat pricing yerine entity + active workflow/source complexity daha mantıklıdır. Review ve approval katılımını koltuk ücretiyle cezalandırmamak gerekir. Ledge de aynı nedenle unlimited-seat platform pricing kullanıyor. [Ledge pricing](https://www.ledge.co/pricing)

Starter paketinin vaadi “dashboard” değil:

> İlk canlı kapanışta en az bir kritik reconciliation'ı tekrar çalışabilir hale getirmek, material exception listesini kanıtlarıyla üretmek ve sonraki aya hazır kural hafızası oluşturmak.

## 10. İlk 10 müşteri görüşmesi

1. $10M–$30M e-commerce şirketinde Controller.
2. Shopify/Stripe/Amazon kullanan marketplace Accounting Manager.
3. 3+ lokasyonlu hizmet şirketinde Head of Finance.
4. QBO Advanced'dan Intacct/NetSuite'e geçiş düşünen Controller.
5. NetSuite kullanan 3–5 kişilik SaaS accounting ekibi.
6. Her ay payroll journal ve accrual hazırlayan Senior Accountant.
7. Çoklu entity close yöneten Accounting Manager.
8. İlk audit veya debt financing hazırlığındaki VP Finance.
9. 10–25 müşterili fractional CFO firması sahibi.
10. FloQast/Numeric/BlackLine değerlendirmiş fakat almamış küçük ekip lideri.

Her görüşmede demo göstermeden önce son close'u ekran paylaşımıyla yeniden yürütmesi istenmeli. Sorular:

- Son kapanışta ilk hangi dosyayı açtınız, sonra ne yaptınız?
- En çok hangi iki kaynak uyuşmuyor?
- Farkı bulmak kaç saat sürdü ve kim yaptı?
- Hangi hatalar tekrar ediyor?
- Bu iş için bugün hangi araca/kişiye para ödüyorsunuz?
- Bir sistem öneri verdiğinde güvenmek için hangi kanıtı görmek zorundasınız?
- Son kapanışın bir bölümünü bizimle ücretli pilotta çalıştırır mısınız?

“$499 öder misiniz?” sorusundan çok gerçek veri, ücretli pilot ve ikinci ay yenilemesi önemlidir.

## 11. 90 günlük doğrulama planı

### Gün 1–15: Problem doğrulama

- Yukarıdaki 10 görüşmeyi tamamla.
- Her adaydan close süresi, manuel saat, kaynak sayısı ve en pahalı reconciliation'ı ölç.
- En az 5 adaydan anonim örnek dosya al.
- Tek dikey ve tek workflow seç.

### Gün 16–35: Concierge close investigation

- Üç design partner'ın gerçek geçmiş dönemini yarı manuel işle.
- Baseline: hazırlık saati, exception sayısı, çözüm süresi, yanlış öneri sayısı.
- Ürünün açıklamasından önce accounting logic ve kanıt gereksinimini öğren.

### Gün 36–65: Ürünleştirme

- Layered AccountMapper.
- Recurring mapping/policy memory.
- Exception inbox ve materiality sıralaması.
- Source-to-output lineage view.
- Accept/reject/correct feedback.
- Review-ready Excel close package.

### Gün 66–90: Ücretli tekrar

- En az üç müşteriye $499 ücretli pilot sat.
- Aynı müşteride ikinci ay aynı workflow'u tekrar çalıştır.
- Kurulum süresini ve kullanıcı müdahalesini ölç.
- Sadece kullanım değil, renewal veya yazılı satın alma taahhüdü al.

### Kill / pivot kriterleri

- 10 görüşmenin 5'inden azında ayda 10+ saatlik aynı tip problem varsa ICP değiştir.
- 10 adaydan 3'ten azı gerçek veri paylaşırsa güvenlik/onboarding önerisi yetersizdir.
- Üç müşteriden en az ikisi $499 ödemiyorsa fiyat veya problem değiştir.
- İlk review sonrası mapping acceptance %85'in altında kalırsa otomatik mapping vaadini düşür.
- Material exception precision %90'ın altında kalırsa AI sınıflandırmasını karar değil öneri olarak sınırla.
- İkinci ayda zaman tasarrufu 8 saatin veya close süresi etkisi bir günün altında kalırsa ürün değer önerisini yeniden seç.
- Ücretli pilotların %70'inden azı ikinci aya devam ederse budgeting geliştirmeye geçme.

## 12. On iki aylık yol haritası

| Dönem | İnşa edilecek | Faz kapısı |
|---|---|---|
| Ay 1–3 | Tek workflow, layered mapping, exception inbox, evidence lineage, Excel output | 3 ücretli pilot ve ikinci ay tekrar kullanım |
| Ay 4–6 | Recurring rules, reviewer approval, close package, QBO/Intacct veya tek ERP integration, draft JE | 10 ödeme yapan müşteri, aylık 8+ saat ölçülmüş tasarruf |
| Ay 7–9 | Multi-entity, role controls, immutable audit log, retention/security, vertical templates | Güçlü retention ve düşük onboarding maliyeti |
| Ay 10–12 | Read-only actual-vs-budget import, driver tagging ve canvas comparison mode | Müşterilerin en az %40'ının aynı talebi göstermesi |

Tam budgeting, workforce planning, scenario engine ve cash-flow planning ancak close ürününde güçlü retention kanıtlandıktan sonra ayrı bir faz olmalıdır.

## 13. İnşa edilmemesi gerekenler

- İlk aşamada tam FP&A/budgeting suite.
- Serbest sürükle-bırak finansal model canvas.
- ERP'den bağımsız ikinci bir “doğru ledger/P&L”.
- Kanıtsız causal narrative.
- İlk günden otomatik JE posting.
- Tüm sektörler için generic mapping.
- Sadece PDF/Excel parsing'i moat olarak görmek.
- Çok erken SAP/Oracle enterprise entegrasyonları.

PII'yi tamamen silmek de her durumda doğru değildir: payroll/vendor/customer kimliği reconciliation ve audit kanıtı için gerekli olabilir. Bunun yerine tokenization, encryption, field-level access, retention ve tenant isolation uygulanmalıdır.

## Nihai yatırım kararı

Bu ürün benim olsaydı sıradaki geliştirme **Financial Flow Canvas veya budgeting olmazdı**. Önce tek bir yüksek frekanslı reconciliation workflow'u uçtan uca ürünleştirirdim: GL'yi destek kaynaklarıyla karşılaştıran, material exception'ları doğru neden ve kanıtla sıralayan, kullanıcının mapping/policy düzeltmesini sonraki aya taşıyan ve review-ready correction/JE paketi üreten bir **Close Investigation Workspace**.

Canvas'ı yalnızca bu workspace'in lineage ve impact-review arayüzü olarak kurardım. Altındaki semantic modelde plan/actual/forecast ayrımını şimdiden destekler, fakat müşteriler close ürünü için düzenli ödeme yapana kadar budgeting motoru geliştirmezdim.

Reddedeceğim yön; IronLedger'ı “AI P&L dashboard + narrative + bütçe uygulaması” haline getirmek olurdu. Bu alan hem commodity AI tarafından hızla emiliyor hem de Pigment, Cube, Datarails, Microsoft ve diğer FP&A ürünleri tarafından yoğun şekilde işgal edilmiş durumda. IronLedger'ın kazanabileceği yer, **enterprise close araçlarının altında kalan ekipler için düşük kurulumlu, file-first, kanıtlı exception resolution** katmanıdır.