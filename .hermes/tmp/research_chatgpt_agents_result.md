26 Ağustos 2026 itibarıyla ulaştığım sonuç: OpenAI, month-end close kullanımını açıkça tanıtıyor; fakat “Month-End Close” şablonunun tam sistem prompt’u, varsayılan araçları ve adım adım konfigürasyonu kamuya açık belgelerde yayımlanmamış. Bu nedenle aşağıda doğrulanmış kapsamı, genel finans örneklerinden ayırıyorum.

## 1. “Otonom Ajanlar” nedir?

- Güncel resmi adı büyük ölçüde **ChatGPT Workspace Agents**. ChatGPT’nin sol kenar çubuğundaki **Agents** bölümünde yaşar.
- Tekrarlanan iş akışları için talimat, model, dosya, hafıza, skill, uygulama/connector ve izinleri bir araya getiren, paylaşılabilir ajanlardır.
- Bir şablon seçilip araçları belirlenir; builder içinde özelleştirilir, test edilir ve özel, bağlantıyla veya kurum dizininde paylaşılabilir.
- Bulutta çalışabilir; zamanlanabilir, Slack’e eklenebilir veya API ile tetiklenebilir. OpenAI bunları “GPT’lerin evrimi” ve **Codex-powered** olarak tanımlıyor. [Workspace Agents duyurusu](https://openai.com/index/introducing-workspace-agents-in-chatgpt/), [Help Center](https://help.openai.com/en/articles/20001143/)

İlişkiler:

- **Eski ChatGPT agent mode:** Operator’un web kullanımı ile Deep Research’ü birleştiren, Temmuz 2025’te çıkan genel amaçlı çalışma moduydu. Ağustos 2026 itibarıyla kaldırılmış; uzun işlerde **ChatGPT Work** öneriliyor. [2025 duyurusu](https://openai.com/index/introducing-chatgpt-agent/), [güncel durum](https://help.openai.com/en/articles/11752874)
- **ChatGPT Work:** Tek seferlik veya uzun, çok adımlı bir işi tamamlayan genel çalışma ajanı. Workspace Agent ise belirli bir sürecin yapılandırılmış, tekrar kullanılabilir ve ekipçe paylaşılabilir sürümüdür.
- **Codex:** Workspace Agents’ın çalışma teknolojisinin bir parçasıdır; fakat Codex ürün yüzeyi hâlâ yazılım geliştirme ve teknik işler için ayrı tutuluyor. [Work–Codex ayrımı](https://help.openai.com/en/articles/20001275)
- **Projects:** Sohbet, dosya ve proje talimatlarını bir arada tutan bağlam konteyneridir. Ajan veya otomasyon motoru değildir; Work bir Project bağlamında çalışabilir.
- **Scheduled Tasks:** Belirli zamanda, tekrarlı veya olay tetiklemeli çalışma başlatır. Ajanın uzmanlık tanımı değil, çalıştırma mekanizmasıdır.
- **AgentKit:** Geliştiricilerin API üzerinde kendi ajan uygulamalarını oluşturduğu ayrı ürün ailesidir. Responses API, Agents SDK, Agent Builder ve ChatKit’i kapsıyordu. 6 Ekim 2025’te duyuruldu; görsel Agent Builder/Evals ürünlerinin kapatılacağı Haziran 2026’da açıklandı. Kod tabanlı akışlar için Agents SDK, doğal dille oluşturma için Workspace Agents öneriliyor. [AgentKit duyurusu](https://openai.com/index/introducing-agentkit/)

## 2. “Month-End Close” şablonu ne yapıyor?

Resmen doğrulanabilen çekirdek kapsam:

- Journal entry hazırlama
- Balance-sheet reconciliation
- Variance analysis
- İnceleme için dayanak girdileri ve control total’ları içeren workpaper üretme
- Kurumun iç politika ve süreçlerini takip etme

OpenAI bunları, kendi muhasebe ekibinin oluşturduğu Workspace Agent örneği olarak açıkça anlatıyor. “Dakikalar içinde” sonuç verdiğini, fakat ekip tarafından incelenecek çalışma kâğıtları ürettiğini söylüyor. [Workspace Agents duyurusu](https://openai.com/index/introducing-workspace-agents-in-chatgpt/)

OpenAI Academy’de ayrıca bir **Close workback plan** örneği bulunuyor:

- GL close
- Revenue review
- Accruals
- Reconciliations
- Reporting
- Review/adım sahipleri
- Day 0–Day 10 takvimi
- Yaygın hata noktaları

Ancak bu bir örnek prompt’tur; kamuya açık belgeler bunun tamamının hazır Workspace Agent şablonuna otomatik olarak gömülü olduğunu kanıtlamıyor. [Finance workflows](https://openai.com/academy/finance/)

Doğrulanmayan noktalar:

- Banka mutabakatının özel, deterministik bir modül olarak bulunması
- Accrual tutarlarını kendiliğinden hesaplayıp muhasebeleştirmesi
- ERP’ye otomatik journal posting
- Close checklist’inde kalıcı görev durumu/owner/SLA yönetimi
- Otomatik sign-off veya dönem kilitleme
- Şablonun tam prompt’u ve varsayılan connector listesi

## 3. Kimin için?

- Öncelikli hedef: muhasebe ekipleri, controller’lar, FP&A/finance operations ekipleri ve yönetilen Business/Enterprise/Edu çalışma alanları.
- OpenAI’nin örneği doğrudan kendi **accounting team**’ine dayanıyor.
- Tek kişilik küçük işletme sahibi için kullanılması mümkün olsa da şablonun özel olarak bu kitleye tasarlandığı doğrulanmadı.
- ChatGPT’deki üçüncü taraf **Double** uygulamasıyla karıştırılmamalı. Double; QuickBooks, Xero, NetSuite ve Sage Intacct bağlantıları sunan ayrı bir sağlayıcıdır; OpenAI’nin yerleşik ajan şablonu değildir.

## 4. Yetenek sınırları

- **Dosya:** Ajan tanımına dosya eklenebilir; Help Center ajan başına dosya başına 512 MB, toplam 10 GB sınırı belirtiyor.
- **Excel/CSV:** ChatGPT genel olarak `.xls`, `.xlsx` ve `.csv` okuyabilir; pandas/Python tabanlı hesaplama, dönüşüm ve analiz çalıştırabilir. Kod ve varsayımlar kullanıcı tarafından incelenmelidir. [Data analysis](https://help.openai.com/en/articles/8437071)
- **Veri kaynakları:** Yüklenen dosyalar, ajan dosyaları, kullanıcı/ajan hafızası ve etkinleştirilmiş Google Drive, SharePoint, Slack gibi uygulamalar; ayrıca özel MCP araçları.
- **ERP:** Varsayılan, evrensel bir ERP bağlantısı doğrulanmadı. NetSuite/QuickBooks gibi sistemlere erişim ancak uygun plugin, connector veya özel MCP verilirse mümkün olur.
- **Yazma/posting:** Connector yazma işlemleri varsayılan olarak kullanıcı onayı ister. Araç ve yetki verilmemişse ajan ERP’ye journal yazamaz.
- **Python ortamı:** Standart data-analysis Python ortamı dış web/API çağrısı yapamaz; dış veri yüklenmeli veya bir connector üzerinden sağlanmalıdır.
- **Kötü/eksik veri:** Karmaşık Excel düzenleri, taranmış tablolar, eksik hesap planı, yanlış dönem veya eksik kaynaklar güvenilirliği azaltır.

## 5. Ne zaman duyuruldu?

Kısa zaman çizgisi:

- **23 Ocak 2025:** Operator — tarayıcı kullanan ajan araştırma önizlemesi. [Duyuru](https://openai.com/index/introducing-operator/)
- **11 Mart 2025:** Responses API ve Agents SDK. [Duyuru](https://openai.com/index/new-tools-for-building-agents/)
- **17 Temmuz 2025:** Operator + Deep Research birleşerek ChatGPT agent mode oldu.
- **6 Ekim 2025:** AgentKit duyuruldu. Bu geliştirici platformudur; Month-End Close şablonunun çıkış duyurusu değildir.
- **22 Nisan 2026:** Workspace Agents duyurusu. Finans, satış ve pazarlama şablonlarından söz edildi; month-end close ajanının journal entry, reconciliation ve variance-analysis kapsamı burada gösterildi.
- **9 Temmuz 2026:** ChatGPT Work duyuruldu. OpenAI, finans ekiplerinin kaynak veri bulma, Excel/Sheets’e taşıma, mutabakat, sunum hazırlama ve sonuç kontrolüyle kapanışı hızlandırdığını belirtti. [ChatGPT Work duyurusu](https://openai.com/index/chatgpt-for-your-most-ambitious-work/)

Sonuç: Month-end close örneğinin esas duyurusu **AgentKit değil, Workspace Agents duyurusudur**. “Month-End Close” adlı şablon kartı için ayrı bir blog veya tam teknik spec bulamadım.

## 6. Finansal doğruluk garantisi var mı?

Hayır, kamuya açık bir finansal doğruluk garantisi yok.

- Workspace Agent, araçlarla güçlendirilmiş genel amaçlı bir LLM ajanıdır.
- Sayılar Python/pandas, spreadsheet formülleri veya bağlı araçlarla hesaplanabilir; fakat yayımlanmış şablon sözleşmesi hesapların her zaman deterministik kodla yapılacağını garanti etmiyor.
- OpenAI’nin iç örneğinde control total ve review workpaper’ları var. Bunun bütün kullanıcılara sunulan şablonda zorunlu bir numeric guardrail olduğu doğrulanmadı.
- AgentKit’teki “guardrails” daha çok PII, prompt injection ve güvenlik kontrolleridir; muhasebe rakamlarını bağımsız olarak doğrulayan finansal guardrail anlamına gelmez.
- OpenAI, ChatGPT’nin hata yapabileceğini ve önemli çıktıların doğrulanmasını öneriyor. Finans sayfası da hassas işlemlerde insan onayı ve nihai kararın finans ekibinde kalmasını vurguluyor. [Doğruluk uyarısı](https://help.openai.com/en/articles/8313428-does-chatgpt-tell-the-truth/), [Finance controls](https://openai.com/business/solutions/finance/)

## IronLedger ile karşılaştırma için kritik sorular

- GL, trial balance veya ERP export’u tek otoriter kaynak olarak mı kabul ediyor?
- Aynı dönem ve entity için veri bütünlüğü nasıl kanıtlanıyor?
- Hesaplamalar tamamen deterministik Python/formüllerle mi, yoksa LLM rakam üretebiliyor mu?
- Anlatıdaki her rakam kaynak değerlerle sonradan karşılaştırılıyor mu?
- Numeric guardrail zorunlu mu; başarısız olursa raporun kaydedilmesini engelliyor mu?
- Reconciliation için opening balance + activity = closing balance kontrolü var mı?
- Bank, intercompany, AR/AP ve balance-sheet mutabakatları ayrı tipler olarak sınıflandırılıyor mu?
- Exception’lar tutar, önemlilik, hesap, kaynak ve neden bazında sınıflandırılıyor mu?
- Accrual ve journal entry’ler yalnızca taslak mı; kim onaylıyor ve kim ERP’ye post ediyor?
- Debit/credit dengesi, dönem, para birimi ve entity kontrolleri var mı?
- Control total’lar dosya/worksheet seviyesinde kalıcı olarak saklanıyor mu?
- Account mapping dönemler arasında kalıcı ve versiyonlu mu?
- Kullanıcı düzeltmeleri sonraki döneme kontrollü mapping olarak mı taşınıyor, yoksa serbest “memory” olarak mı?
- PII, örnek satır çıkarılmadan ve LLM’e gitmeden önce temizleniyor mu?
- Kaynak satır → hesaplama → bulgu → anlatı için tam lineage var mı?
- Her çalıştırma immutable audit record oluşturuyor mu?
- Tenant/company izolasyonu uygulama ve veritabanı seviyesinde zorunlu mu?
- Şablon/mantık/model değişiklikleri versiyonlanıyor ve yeniden üretilebilir mi?
- Kullanılan eşikler ve materiality kuralları kullanıcı/şirket bazında açıkça tanımlı mı?
- ERP connector kesintisi, eksik veri ve schema değişikliği ayrı hata durumları mı?
- Rapor “verified” etiketi almadan önce hangi zorunlu kontroller geçiyor?
- Şablonun başarısı gerçek close verileri ve kasıtlı sayısal uyuşmazlıklarla eval ediliyor mu?